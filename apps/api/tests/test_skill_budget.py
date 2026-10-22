import asyncio
import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select
from pao import runtime, skills
from pao.config import settings
from pao.db import Session
from pao.models import Run, ToolCall
from pao.skill_router import SKILL_TOOLS
from test_memory import run_chat
from test_skill_router import mock_gateway

COMMAND = 'Điều tra hiệu quả quảng cáo giảm meta act_1 từ 2026-10-01 đến 2026-10-05'


async def test_pinned_timeout_stops_before_second_tool(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    original = skills.REGISTRY['investigate-ads-drop']
    monkeypatch.setitem(skills.REGISTRY, 'investigate-ads-drop', original.model_copy(update={'timeout_seconds': 1}))
    _, rid = await run_chat(client, identity, COMMAND)
    execute = runtime.execute_tool

    async def first_then_wait(ctx, call_id):
        await execute(ctx, call_id)
        # Alter registry after snapshot capture. Pinned deadline stays 1s.
        monkeypatch.setitem(skills.REGISTRY, 'investigate-ads-drop', original)
        await asyncio.sleep(3)

    monkeypatch.setattr(runtime, 'execute_tool', first_then_wait)
    start = asyncio.get_running_loop().time()
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    assert asyncio.get_running_loop().time() - start < 3
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'skill_timeout'
        assert not run.response and not run.execution_plan.get('skill_result')
        assert run.execution_plan['skill_snapshot']['timeout_seconds'] == 1
        assert run.execution_plan['resource_guard']['timeout_seconds'] == 1
        assert len(list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))) == 1


async def test_tool_count_budget_is_checked_before_dispatch(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    monkeypatch.setitem(SKILL_TOOLS, 'investigate-ads-drop', ('business.kpi.read',) * 3)
    _, rid = await run_chat(client, identity, COMMAND)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'skill_tool_budget'
        assert list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid))) == []


async def test_output_budget_fails_without_truncated_success(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    monkeypatch.setattr(runtime, 'analysis_response', lambda *args: ('x' * 32001, {}))
    _, rid = await run_chat(client, identity, COMMAND)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'skill_output_budget'
        assert not run.response and not run.execution_plan.get('skill_result')


async def test_deadline_during_read_never_leaves_running_call(client, identity, monkeypatch):
    from pao import tool_gateway
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    spec = skills.REGISTRY['investigate-ads-drop']
    monkeypatch.setitem(skills.REGISTRY, 'investigate-ads-drop', spec.model_copy(update={'timeout_seconds': 1}))

    async def blocked_read(*args):
        await asyncio.sleep(3)

    monkeypatch.setattr(tool_gateway, 'read_kpi', blocked_read)
    _, rid = await run_chat(client, identity, COMMAND)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert run.status == 'failed' and run.error_code == 'skill_timeout'
        assert not run.response and len(calls) == 1
        assert calls[0].status == 'unknown' and calls[0].error_code == 'execution_interrupted'
