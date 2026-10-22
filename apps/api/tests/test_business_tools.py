from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy import select, func
from pao.db import Session
from pao.models import AdReport, MetaConnection, Task, Workspace, Member, now

PERIOD = {'start_date': '2026-10-01', 'end_date': '2026-10-05'}
URL = '/v1/skills/daily-business-brief/preview'


async def seed(identity, **changes):
    async with Session.begin() as db:
        from pao.integrations import ads_apps
        app_context=await ads_apps.resolve(db,identity['workspace'],'meta')
        conn = MetaConnection(workspace_id=identity['workspace'], user_id=identity['user_id'],
                              status='connected', expires_at=now()+timedelta(hours=1),app_binding=app_context.binding)
        db.add(conn)
        await db.flush()
        fields = dict(connection_id=conn.id, connection_version=1, workspace_id=identity['workspace'],
                      user_id=identity['user_id'], account_id='act_1', request_key='preview-source', kind='weekly',
                      period_start=date(2026,10,1), period_end=date(2026,10,5), currency='VND',
                      timezone='Asia/Ho_Chi_Minh', attribution='fixture', spend=Decimal('10'),
                      revenue=Decimal('30'), purchases=Decimal('2'), coverage_days=5, expected_days=5,
                      data_through=date(2026,10,5), source_updated_at=now())
        fields.update(changes)
        report = AdReport(**fields)
        db.add(report)
        await db.flush()
        return conn.id, report.id


async def preview(client, identity, headers=None, **changes):
    return await client.post(URL, headers=headers or identity['owner'],
                             json={'workspace_id': identity['workspace'], 'input': PERIOD, **changes})


async def test_preview_requires_auth_scope_and_valid_input(client, identity):
    assert (await client.post(URL, json={'workspace_id': identity['workspace'], 'input': PERIOD})).status_code == 401
    assert (await preview(client, identity, headers=identity['outsider'])).status_code == 404
    assert (await preview(client, identity, input={**PERIOD, 'workspace_id': 'escape'})).status_code == 422
    assert (await preview(client, identity, input={**PERIOD, 'end_date': '2025-01-01'})).status_code == 422
    assert (await preview(client, identity, agent='editor')).status_code == 422


async def test_missing_connector_is_not_fabricated_and_viewer_can_read(client, identity):
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        member.role = 'viewer'
    response = await preview(client, identity)
    assert response.status_code == 200, response.text
    out = response.json()
    assert out['read_only'] is True and out['result']['status'] == 'insufficient_data'
    assert out['tools'][0]['data']['created_in_period'] == 0
    assert out['tools'][1]['data']['reports'] == []
    assert any(value.startswith('meta_connection:') for value in out['result']['missing_data'])


async def test_preview_sources_period_and_no_writes(client, identity):
    _, report_id = await seed(identity)
    async with Session.begin() as db:
        foreign = Workspace(name='Foreign')
        db.add(foreign)
        await db.flush()
        for wid, created in [(identity['workspace'], datetime(2026,10,1,tzinfo=timezone.utc)),
                             (identity['workspace'], datetime(2026,10,6,tzinfo=timezone.utc)),
                             (foreign.id, datetime(2026,10,1,tzinfo=timezone.utc))]:
            db.add(Task(workspace_id=wid, title='Do not expose title', created_by=identity['user_id'],
                        status='ready', created_at=created))
    async with Session() as db:
        before = [await db.scalar(select(func.count()).select_from(model)) for model in (Task, AdReport, MetaConnection)]
    first = await preview(client, identity)
    second = await preview(client, identity)
    assert first.status_code == second.status_code == 200
    out = first.json()
    assert out['tools'][0]['data']['created_in_period'] == 1
    report = out['tools'][1]['data']['reports'][0]
    assert report['report_id'] == report_id and report['platform_reported_revenue'] == '30.000000'
    assert f'ad-report:{report_id}' in out['result']['source_references']
    assert 'Do not expose title' not in first.text
    assert out['result'] == second.json()['result']
    assert out['result']['status'] == 'insufficient_data'  # not verified business revenue
    other = (await preview(client, identity, headers=identity['other'])).json()
    assert other['tools'][1]['data']['reports'] == []  # personal connector scope
    async with Session() as db:
        after = [await db.scalar(select(func.count()).select_from(model)) for model in (Task, AdReport, MetaConnection)]
    assert before == after


async def test_partial_null_and_old_connection_version_are_missing(client, identity):
    cid, _ = await seed(identity, revenue=None, coverage_days=2, data_through=date(2026,10,2))
    out = (await preview(client, identity)).json()
    assert out['tools'][1]['data']['reports'][0]['platform_reported_revenue'] is None
    assert any(value.startswith('report_coverage:') for value in out['result']['missing_data'])
    assert any(value.startswith('report_metrics:') for value in out['result']['missing_data'])
    async with Session.begin() as db:
        (await db.get(MetaConnection, cid)).version = 2
    out = (await preview(client, identity)).json()
    assert out['tools'][1]['data']['reports'] == []


async def test_latest_snapshot_per_account_and_exact_period(client, identity):
    cid, old_id = await seed(identity)
    async with Session.begin() as db:
        old = await db.get(AdReport, old_id)
        values = {col.name: getattr(old, col.name) for col in AdReport.__table__.columns
                  if col.name not in ('id', 'created_at', 'request_key')}
        newer = AdReport(**{**values, 'spend': Decimal('20')}, request_key='newer', created_at=now()+timedelta(seconds=1))
        wrong = AdReport(**{**values, 'period_start': date(2026,9,30)}, request_key='wrong-period')
        db.add_all([newer, wrong])
        await db.flush()
        newer_id = newer.id
    out = (await preview(client, identity)).json()
    rows = out['tools'][1]['data']['reports']
    assert len(rows) == 1 and rows[0]['report_id'] == newer_id and rows[0]['spend'] == '20.000000'


async def test_database_enforces_read_only_and_timeout_is_safe(client, identity, monkeypatch):
    from pao import skill_api

    async def accidental_write(db, who, wid, arguments):
        db.add(Workspace(name='Must not persist'))
        await db.flush()

    monkeypatch.setattr(skill_api, 'daily_brief_preview', accidental_write)
    with pytest.raises(DBAPIError):
        await preview(client, identity)
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Workspace).where(Workspace.name == 'Must not persist')) == 0

    async def slow(*args):
        raise TimeoutError()

    monkeypatch.setattr(skill_api, 'daily_brief_preview', slow)
    assert (await preview(client, identity)).status_code == 504
