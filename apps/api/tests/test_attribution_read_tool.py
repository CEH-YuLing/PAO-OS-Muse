from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError
from pao.auth import Principal
from pao.config import settings
from pao.db import Session
from pao.models import AttributionRun, AttributionMetric, AttributionSource, MetaConnection, ToolCall, now
from pao.business_tools import read_attribution
from pao.tool_gateway import propose, execute_tool
from test_business_tools import seed
from test_memory import run_chat

ARGS = {'start_date': '2026-10-01', 'end_date': '2026-10-05', 'platform': 'meta', 'account_id': 'act_1'}
URL = '/v1/skills/investigate-ads-drop/attribution-preview'


async def fixture(identity):
    cid, _ = await seed(identity)
    async with Session.begin() as db:
        source = AttributionSource(connection_id=cid, connection_version=1, workspace_id=identity['workspace'],
            account_id='act_1', kind='orders', name='Fixture', currency='USD', timezone='UTC',
            updated_by=identity['user_id'], updated_at=now()-timedelta(minutes=1))
        db.add(source); await db.flush()
        run = AttributionRun(connection_id=cid, connection_version=1, workspace_id=identity['workspace'],
            user_id=identity['user_id'], account_id='act_1', request_key='read-fixture',
            period_start=date(2026,10,1), period_end=date(2026,10,5), discrepancy_threshold_pct=25,
            source_updated_at=now(), summary={'campaigns_analyzed': 1,
            'unattributed': {'analytics': 0, 'leads': 0, 'orders': 2}, 'secret': 'do-not-expose'})
        db.add(run); await db.flush()
        metric = AttributionMetric(run_id=run.id, campaign_id='123', currency='USD', platform_revenue=1000,
            actual_revenue=700, actual_orders=7, tracking_status='watch', revenue_discrepancy_pct=42,
            evidence={'source_ids': [source.id], 'order_source_connected': True, 'secret': 'do-not-expose'})
        db.add(metric); await db.flush()
        return cid, run.id, metric.id, source.id


async def preview(client, identity, **changes):
    return await client.post(URL, headers=identity['owner'],
        json={'workspace_id': identity['workspace'], 'input': {**ARGS, **changes}})


async def test_preview_auth_scope_validation_and_missing(client, identity):
    body = {'workspace_id': identity['workspace'], 'input': ARGS}
    assert (await client.post(URL, json=body)).status_code == 401
    assert (await client.post(URL, json=body, headers=identity['outsider'])).status_code == 404
    out = await preview(client, identity)
    assert out.status_code == 200 and out.json()['result']['status'] == 'insufficient_data'
    assert (await preview(client, identity, workspace_id='untrusted')).status_code == 422
    assert (await preview(client, identity, end_date='2026-09-01')).status_code == 422
    google = await preview(client, identity, platform='google_ads', account_id='123')
    assert google.status_code == 200 and 'Google Ads' in google.text


async def test_preview_exact_period_personal_scope_and_no_writes(client, identity):
    _, rid, mid, _ = await fixture(identity)
    out = await preview(client, identity)
    assert out.status_code == 200, out.text
    data = out.json(); tool = data['tools'][0]
    assert tool['data']['snapshot']['id'] == rid and tool['data']['totals_combined'] is False
    metric = tool['data']['metrics'][0]
    assert metric['platform_reported_revenue'] == '1000.000000'
    assert metric['attributed_paid_order_revenue'] == '700.000000'
    assert metric['attributed_paid_order_count'] == 7
    assert tool['data']['verified_business_revenue'] is False
    assert 'actual_revenue' not in metric and 'secret' not in out.text and 'do-not-expose' not in out.text
    assert data['result']['source_references'] == [f'attribution-run:{rid}', f'attribution-metric:{mid}']
    assert any(reason.startswith('unattributed_coverage:') for reason in tool['missing_data'])
    other = await client.post(URL, headers=identity['other'], json={'workspace_id': identity['workspace'], 'input': ARGS})
    assert other.status_code == 200 and other.json()['tools'][0]['data']['snapshot'] is None
    assert (await preview(client, identity, account_id='act_2')).json()['tools'][0]['data']['snapshot'] is None
    assert (await preview(client, identity, start_date='2026-09-30')).json()['tools'][0]['data']['snapshot'] is None
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AttributionRun)) == 1
        assert await db.scalar(select(func.count()).select_from(AttributionMetric)) == 1


@pytest.mark.parametrize('condition', ['disabled', 'source_changed', 'foreign_source', 'no_orders', 'old_connection', 'expired'])
async def test_invalid_source_never_promotes_zero_to_business_revenue(client, identity, condition):
    cid, rid, mid, sid = await fixture(identity)
    async with Session.begin() as db:
        source = await db.get(AttributionSource, sid)
        metric = await db.get(AttributionMetric, mid)
        if condition == 'disabled': source.enabled = False
        if condition == 'source_changed': source.version = 2; source.updated_at = now()+timedelta(seconds=1)
        if condition == 'foreign_source': source.account_id = 'act_2'
        if condition == 'no_orders': metric.evidence = {'order_source_connected': False, 'source_ids': [sid]}; metric.actual_revenue = 0
        if condition == 'old_connection': (await db.get(MetaConnection, cid)).version = 2
        if condition == 'expired': (await db.get(MetaConnection, cid)).expires_at = now()-timedelta(seconds=1)
    tool = (await preview(client, identity)).json()['tools'][0]
    if condition in ('old_connection', 'expired'):
        assert tool['data']['snapshot'] is None
    else:
        assert tool['data']['metrics'][0]['attributed_paid_order_revenue'] is None
        assert tool['data']['metrics'][0]['attributed_paid_order_count'] is None
    assert tool['data']['verified_business_revenue'] is False


async def test_gateway_attribution_is_read_only_version_bound_and_no_provider(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    await fixture(identity)
    _, rid = await run_chat(client, identity, 'Attribution fixture')
    call = await propose(rid, identity['user_id'], 'attribution-read-01',
                         {'name': 'business.attribution.read', 'arguments': ARGS})
    provider = AsyncMock()
    await execute_tool({'tool_invoke': provider}, call.id)
    provider.assert_not_awaited()
    async with Session() as db:
        saved = await db.get(ToolCall, call.id)
        assert saved.status == 'completed' and saved.result['status'] == 'insufficient_data'
    async with Session.begin() as db:
        await db.execute(text('SET TRANSACTION READ ONLY'))
        await read_attribution(db, Principal(identity['user_id'], 0), identity['workspace'], ARGS)
        with pytest.raises(DBAPIError):
            await db.execute(text("UPDATE attribution_metrics SET actual_revenue=0"))


async def test_bounds_keep_missing_revenue_warning_and_separate_currencies(client, identity):
    _, rid, _, sid = await fixture(identity)
    async with Session.begin() as db:
        run = await db.get(AttributionRun, rid)
        run.summary = {'campaigns_analyzed': 51, 'unattributed': {'analytics': 0, 'leads': 0, 'orders': 0}}
        run.source_updated_at = now()-timedelta(days=2)
        for index in range(50):
            db.add(AttributionMetric(run_id=rid, campaign_id=str(1000+index), currency='VND',
                actual_revenue=900, tracking_status='insufficient',
                evidence={'source_ids': [sid], 'order_source_connected': True, 'instruction': 'must-not-expose'}))
    response = await preview(client, identity)
    assert response.status_code == 200
    result = response.json(); tool = result['tools'][0]
    assert len(tool['data']['metrics']) == 49 and len(tool['source_references']) == 50
    assert len(result['result']['missing_data']) <= 20
    assert tool['data']['totals_combined'] is False
    assert all(row['attributed_paid_order_revenue'] is None for row in tool['data']['metrics'] if row['currency'] == 'VND')
    assert any(reason.startswith('metric_coverage:') for reason in tool['missing_data'])
    assert any(reason.startswith('verified_business_revenue:') for reason in tool['missing_data'])
    assert 'must-not-expose' not in response.text


async def test_latest_exact_snapshot_selected_not_different_period(client, identity):
    cid, old_id, _, _ = await fixture(identity)
    async with Session.begin() as db:
        common = dict(connection_id=cid, connection_version=1, workspace_id=identity['workspace'],
            user_id=identity['user_id'], account_id='act_1', discrepancy_threshold_pct=25, source_updated_at=now())
        newer = AttributionRun(**common, request_key='new-exact', period_start=date(2026,10,1),
            period_end=date(2026,10,5), created_at=now()+timedelta(seconds=1), summary={})
        wrong = AttributionRun(**common, request_key='new-wrong-period', period_start=date(2026,9,30),
            period_end=date(2026,10,5), created_at=now()+timedelta(seconds=2), summary={})
        db.add_all([newer, wrong]); await db.flush(); expected = newer.id
    tool = (await preview(client, identity)).json()['tools'][0]
    assert tool['data']['snapshot']['id'] == expected and expected != old_id
    assert tool['data']['metrics'] == [] and tool['status'] == 'insufficient_data'
