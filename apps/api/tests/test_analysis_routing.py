import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select
from pao.models import Run, ToolCall, AdReport
from pao.db import Session
from pao.config import settings
from pao.runtime import execute_run
from pao.tool_registry import validate_request
from pydantic import ValidationError
from test_analysis_tools import fixtures, ARGS
from test_skill_router import mock_gateway
from test_memory import run_chat


@pytest.mark.parametrize('label,skill,names', [
    ('Điều tra hiệu quả quảng cáo giảm', 'investigate-ads-drop', ['business.kpi.read', 'business.ads.intelligence.read']),
    ('Đánh giá creative fatigue', 'creative-fatigue-review', ['business.creative.read', 'business.ads.intelligence.read']),
])
async def test_chief_analysis_coordinated_tools_sources_replay(client, identity, monkeypatch, label, skill, names):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, aid, crid = await fixtures(identity)
    # Same workspace/user but another account must not leak into scoped KPI.
    async with Session.begin() as db:
        original = await db.scalar(select(AdReport))
        values = {col.name: getattr(original, col.name) for col in AdReport.__table__.columns
                  if col.name not in ('id', 'created_at', 'request_key', 'account_id')}
        db.add(AdReport(**values, account_id='act_2', request_key='other-account-fixture'))
    _, rid = await run_chat(client, identity, f'{label} meta act_1 từ 2026-10-01 đến 2026-10-05')
    gateway = mock_gateway()
    await execute_run({'gateway': gateway}, rid)
    await execute_run({'gateway': gateway}, rid)
    gateway.stream.assert_not_called()
    gateway.plan.assert_not_awaited()
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'completed', run.error_code
        assert run.execution_plan['skill_route']['skill_id'] == skill
        assert run.execution_plan['skill_result']['status'] == 'insufficient_data'
        assert 'act_2' not in run.response and 'do-not-expose' not in run.response
        assert f'ads-intelligence:{aid}' in run.execution_plan['skill_result']['source_references']
        if skill == 'creative-fatigue-review':
            assert f'creative-analysis:{crid}' in run.execution_plan['skill_result']['source_references']
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid).order_by(ToolCall.created_at)))
        assert [item.name for item in calls] == names
        assert len(calls) == 2 and all(item.status == 'completed' for item in calls)
        assert all(item.arguments == ARGS for item in calls)


@pytest.mark.parametrize('platform,account', [('meta', 'act_1'), ('google_ads', '1234567890')])
async def test_analysis_command_without_connector_never_fabricates(client, identity, monkeypatch, platform, account):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, f'Điều tra hiệu quả quảng cáo giảm {platform} {account} từ 2026-10-01 đến 2026-10-05')
    await execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'completed'
        result = run.execution_plan['skill_result']
        assert result['status'] == 'insufficient_data' and result['source_references'] == []
        assert 'không sửa Ads' in run.response


def test_kpi_account_pair_and_schema_are_strict():
    request = {'name': 'business.kpi.read', 'agent': 'performance_analyst', 'arguments': ARGS}
    assert validate_request(request).arguments == ARGS
    for args in [{key: value for key, value in ARGS.items() if key != 'platform'},
                 {key: value for key, value in ARGS.items() if key != 'account_id'},
                 {**ARGS, 'workspace_id': 'escape'}]:
        with pytest.raises(ValidationError):
            validate_request({**request, 'arguments': args})
