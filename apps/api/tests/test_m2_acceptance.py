import asyncio
import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select
from pao import runtime, tool_gateway
from pao.config import settings
from pao.db import Session
from pao.models import Run, ToolCall, Member
from pao.skill_router import analysis_response, select_skill, tool_plan
from pao.skills import evaluate_result, snapshot
from test_memory import run_chat
from test_skill_router import mock_gateway

COMMAND = 'Điều tra hiệu quả quảng cáo giảm meta act_1 từ 2026-10-01 đến 2026-10-05'


@pytest.mark.parametrize('change', ['cancel', 'revoke'])
async def test_stop_between_tools_never_dispatches_second(client, identity, monkeypatch, change):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, COMMAND)
    original = runtime.execute_tool

    async def first_then_stop(ctx, call_id):
        await original(ctx, call_id)
        async with Session.begin() as db:
            if change == 'cancel':
                (await db.get(Run, rid)).cancel_requested = True
            else:
                (await db.get(Member, (identity['workspace'], identity['user_id']))).role = 'viewer'

    monkeypatch.setattr(runtime, 'execute_tool', first_then_stop)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == ('cancelled' if change == 'cancel' else 'failed')
        assert not run.response and not run.execution_plan.get('skill_result')
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert len(calls) == 1 and calls[0].name == 'business.kpi.read'


async def test_failed_second_tool_is_not_success_and_redacts_errors(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)

    async def broken(*args):
        raise RuntimeError('synthetic-sensitive-detail-must-not-leak')

    monkeypatch.setattr(tool_gateway, 'read_intelligence', broken)
    _, rid = await run_chat(client, identity, COMMAND)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and not run.response
        assert 'synthetic-sensitive' not in str(run.execution_plan)
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert sorted(call.status for call in calls) == ['completed', 'failed']
        assert all('synthetic-sensitive' not in str(call.result) for call in calls)


async def test_runtime_observes_dispatcher_claim_without_duplicate_calls(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    original = runtime.execute_tool
    jobs = []

    async def other_executor(ctx, call_id):
        # Simulate a dispatcher owning execution while inline returns early.
        async def later():
            await asyncio.sleep(.15)
            await original(ctx, call_id)
        jobs.append(asyncio.create_task(later()))

    monkeypatch.setattr(runtime, 'execute_tool', other_executor)
    _, rid = await run_chat(client, identity, COMMAND)
    try:
        await runtime.execute_run({'gateway': mock_gateway()}, rid)
    finally:
        await asyncio.gather(*jobs)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'completed', run.error_code
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert len(calls) == 2 and all(call.status == 'completed' for call in calls)


def test_source_budget_keeps_all_roots_and_unknown_is_not_zero():
    selection = select_skill('Đánh giá creative fatigue meta act_1 từ 2026-10-01 đến 2026-10-05')
    results = [
        {'tool': 'business.creative.read', 'data': {'features': []}, 'missing_data': [],
         'source_references': ['creative-analysis:root'] + [f'creative-feature:{i}' for i in range(49)]},
        {'tool': 'business.ads.intelligence.read', 'data': {'anomalies': [{
            'id': 'unknown', 'kind': 'roas_drop', 'current_value': None, 'baseline_value': None, 'deviation_pct': None}]},
         'missing_data': [f'missing-{i}' for i in range(40)],
         'source_references': ['ads-intelligence:root', 'ad-anomaly:unknown']},
    ]
    response, result = analysis_response(selection, results)
    assert 'chưa biết' in response and 'None%' not in response and 'deviation 0%' not in response
    assert len(result['source_references']) == 50 and len(result['missing_data']) <= 20
    assert 'ads-intelligence:root' in result['source_references']
    assert 'creative-analysis:root' in result['source_references']
    assert 'ad-anomaly:unknown' in result['source_references']
    evaluate_result(snapshot(selection['skill_id']), result)


def test_runtime_tool_plan_never_escapes_skill_allowlist(monkeypatch):
    from pao.skill_router import SKILL_TOOLS
    selection = select_skill(COMMAND)
    monkeypatch.setitem(SKILL_TOOLS, 'investigate-ads-drop', ('email.mock_send',))
    with pytest.raises(PermissionError):
        tool_plan(selection)
