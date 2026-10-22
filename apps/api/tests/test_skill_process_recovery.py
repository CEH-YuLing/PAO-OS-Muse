"""Real child-process kill/restart with controlled lease clock on pao_test."""
import asyncio
import os
from pathlib import Path
import sys

import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select

from pao.db import Session
from pao.models import AgentRun, Run, RunEvent, ToolCall
from test_memory import run_chat

HARNESS = Path(__file__).with_name('_skill_crash_process.py')
COMMAND = 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05'


async def start_process(mode, run_id):
    env = {**os.environ, 'DATABASE_URL': os.environ['PAO_TEST_DATABASE_URL'],
           'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    return await asyncio.create_subprocess_exec(
        sys.executable, str(HARNESS), mode, run_id, env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)


@pytest.mark.parametrize('fault_point', ['between', 'during'])
async def test_os_kill_and_fresh_process_recovery(client, identity, fault_point):
    _, rid = await run_chat(client, identity, COMMAND)
    process = await start_process(fault_point, rid)
    try:
        marker = await asyncio.wait_for(process.stdout.readline(), 15)
        assert marker.strip() == b'FAULT_READY', 'Child did not reach fault boundary'
        async with Session() as db:
            run = await db.get(Run, rid)
            assert run.status == 'running' and not run.response
            pinned = run.execution_plan['skill_snapshot']
            calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
            assert len(calls) == 1
            assert calls[0].status == ('completed' if fault_point == 'between' else 'running')
        process.kill()  # Real OS termination, not coroutine cancellation.
        await asyncio.wait_for(process.wait(), 10)
        assert process.returncode != 0
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

    recovery = await start_process('recover', rid)
    try:
        out, err = await asyncio.wait_for(recovery.communicate(), 20)
        assert recovery.returncode == 0, err.decode('utf-8', errors='replace')
        assert b'RECOVERY_DONE' in out
    finally:
        if recovery.returncode is None:
            recovery.kill()
            await recovery.wait()
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'worker_lost'
        assert not run.response and not run.execution_plan.get('skill_result')
        assert run.execution_plan['skill_snapshot'] == pinned
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert len(calls) == 1  # No second tool, no repeated first tool.
        assert calls[0].status == ('completed' if fault_point == 'between' else 'unknown')
        if fault_point == 'during':
            assert calls[0].error_code == 'worker_lost'
        agents = list(await db.scalars(select(AgentRun).where(AgentRun.run_id == rid)))
        assert agents and all(agent.status == 'failed' for agent in agents)
        events = list(await db.scalars(select(RunEvent).where(RunEvent.run_id == rid)
                                      .order_by(RunEvent.seq)))
        kinds = [event.type for event in events]
        assert kinds.count('run.failed') == 1 and 'run.completed' not in kinds
        assert 'response.completed' not in kinds
        assert len({event.seq for event in events}) == len(events)
