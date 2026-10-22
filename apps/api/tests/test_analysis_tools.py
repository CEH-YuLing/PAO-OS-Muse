from datetime import date, timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from pao.db import Session
from pao.models import AdIntelligenceRun, AdAnomaly, CreativeAnalysisRun, MetaConnection, now, ToolCall
from pao.config import settings
from pao.tool_gateway import propose, execute_tool
from pao.tool_registry import validate_request
from test_memory import run_chat
from test_business_tools import seed

ARGS = {'start_date': '2026-10-01', 'end_date': '2026-10-05', 'platform': 'meta', 'account_id': 'act_1'}


async def fixtures(identity):
    cid, _ = await seed(identity)
    async with Session.begin() as db:
        common = dict(connection_id=cid, connection_version=1, workspace_id=identity['workspace'],
                      user_id=identity['user_id'], account_id='act_1', source_updated_at=now())
        ads = AdIntelligenceRun(**common, request_key='ads-snapshot', granularity='daily',
            period_start=date(2026,10,1), period_end=date(2026,10,5),
            summary={'campaigns_analyzed': 2, 'anomalies_detected': 1, 'recommendations_active': 1, 'secret': 'do-not-expose'})
        creative = CreativeAnalysisRun(**common, request_key='creative-snapshot', as_of=date(2026,10,5),
            current_days=5, baseline_days=3, configuration={},
            summary={'creative_count': 1, 'fatigued_count': 0, 'watch_count': 0, 'insufficient_count': 1})
        db.add_all([ads, creative])
        await db.flush()
        db.add(AdAnomaly(connection_id=cid, connection_version=1, workspace_id=identity['workspace'],
            run_id=ads.id, account_id='act_1', resource_id='campaign_1', kind='roas_drop', severity='warning',
            fingerprint='synthetic-anomaly', current_value=5, baseline_value=10, deviation_pct=-50,
            evidence={'untrusted_instruction': 'must not expose or execute'}))
        return cid, ads.id, creative.id


@pytest.mark.parametrize('skill', ['investigate-ads-drop', 'creative-fatigue-review'])
async def test_analysis_preview_scoped_missing_and_invalid(client, identity, skill):
    url = f'/v1/skills/{skill}/analysis-preview'
    body = {'workspace_id': identity['workspace'], 'input': ARGS}
    assert (await client.post(url, json=body)).status_code == 401
    assert (await client.post(url, json=body, headers=identity['outsider'])).status_code == 404
    out = await client.post(url, json=body, headers=identity['owner'])
    assert out.status_code == 200, out.text
    assert out.json()['result']['status'] == 'insufficient_data'
    assert out.json()['tools'][0]['data']['snapshot'] is None
    assert (await client.post(url, json={**body, 'input': {**ARGS, 'workspace_id': 'escape'}}, headers=identity['owner'])).status_code == 422


@pytest.mark.parametrize('skill,kind', [('investigate-ads-drop', 'ads-intelligence'), ('creative-fatigue-review', 'creative-analysis')])
async def test_exact_snapshot_sources_no_write_and_personal_scope(client, identity, skill, kind):
    cid, aid, crid = await fixtures(identity)
    url = f'/v1/skills/{skill}/analysis-preview'
    body = {'workspace_id': identity['workspace'], 'input': ARGS}
    response = await client.post(url, json=body, headers=identity['owner'])
    assert response.status_code == 200, response.text
    out = response.json()
    expected = aid if kind == 'ads-intelligence' else crid
    assert out['tools'][0]['data']['snapshot']['id'] == expected
    assert f'{kind}:{expected}' in out['result']['source_references']
    if kind == 'ads-intelligence':
        assert out['tools'][0]['data']['anomalies'][0]['current_value'] == '5.000000'
        assert 'must not expose or execute' not in response.text
    assert out['result']['status'] == 'insufficient_data' and 'do-not-expose' not in response.text
    for update in [{'account_id': 'act_2'}, {'start_date': '2026-10-02'}, {'platform': 'google_ads'}]:
        value = (await client.post(url, json={**body, 'input': {**ARGS, **update}}, headers=identity['owner'])).json()
        assert value['tools'][0]['data']['snapshot'] is None
    other = (await client.post(url, json=body, headers=identity['other'])).json()
    assert other['tools'][0]['data']['snapshot'] is None
    async with Session.begin() as db:
        assert await db.scalar(select(func.count()).select_from(AdIntelligenceRun)) == 1
        assert await db.scalar(select(func.count()).select_from(CreativeAnalysisRun)) == 1
        (await db.get(MetaConnection, cid)).version = 2
    old = (await client.post(url, json=body, headers=identity['owner'])).json()
    assert old['tools'][0]['data']['snapshot'] is None


async def test_stale_summary_and_sample_quality(client, identity):
    _, aid, _ = await fixtures(identity)
    async with Session.begin() as db:
        row = await db.get(AdIntelligenceRun, aid)
        row.source_updated_at = now()-timedelta(days=2)
        row.summary = {'campaigns_analyzed': 'unknown'}
    out = (await client.post('/v1/skills/investigate-ads-drop/analysis-preview', headers=identity['owner'],
        json={'workspace_id': identity['workspace'], 'input': ARGS})).json()
    missing = out['tools'][0]['missing_data']
    assert any(item.startswith('snapshot_summary:') for item in missing)
    assert any(item.startswith('source_freshness:') for item in missing)


@pytest.mark.parametrize('name', ['business.ads.intelligence.read', 'business.creative.read'])
async def test_gateway_reads_without_external_provider_and_validates_agent(client, identity, monkeypatch, name):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    await fixtures(identity)
    _, rid = await run_chat(client, identity, 'Analysis Gateway fixture')
    request = {'name': name, 'agent': 'performance_analyst', 'arguments': ARGS}
    validate_request(request)
    with pytest.raises(PermissionError):
        validate_request({**request, 'agent': 'editor'})
    call = await propose(rid, identity['user_id'], 'analysis-tool-01', request)
    provider = AsyncMock()
    await execute_tool({'tool_invoke': provider}, call.id)
    await execute_tool({'tool_invoke': provider}, call.id)
    provider.assert_not_awaited()
    async with Session() as db:
        saved = await db.get(ToolCall, call.id)
        assert saved.status == 'completed' and saved.result['data']['snapshot']


async def test_analysis_payload_is_bounded(client, identity):
    cid, aid, _ = await fixtures(identity)
    async with Session.begin() as db:
        for index in range(50):
            db.add(AdAnomaly(connection_id=cid, connection_version=1, workspace_id=identity['workspace'],
                run_id=aid, account_id='act_1', resource_id=str(index), kind='roas_drop', severity='notice',
                fingerprint=f'limit-{index}', evidence={}))
        row = await db.get(AdIntelligenceRun, aid)
        row.summary = {**row.summary, 'anomalies_detected': 51}
    out = (await client.post('/v1/skills/investigate-ads-drop/analysis-preview', headers=identity['owner'],
        json={'workspace_id': identity['workspace'], 'input': ARGS})).json()
    assert len(out['tools'][0]['data']['anomalies']) == 50
    assert len(out['result']['source_references']) == 50
    assert any(item.startswith('anomaly_coverage:') for item in out['result']['missing_data'])
