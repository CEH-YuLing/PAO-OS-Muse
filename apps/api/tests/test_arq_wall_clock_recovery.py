"""Opt-in real ARQ/Redis kill/restart, real lease clock (about 3 minutes)."""
import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings
from arq.constants import job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Run, RunEvent, ToolCall, ToolAudit
from test_memory import run_chat

pytestmark = [pytest.mark.skipif(os.environ.get('PAO_ARQ_WALL_CLOCK_TESTS') != '1',
                               reason='Opt in to real-clock ARQ acceptance with PAO_ARQ_WALL_CLOCK_TESTS=1'),
              pytest.mark.usefixtures('accounted_runs')]
HARNESS = Path(__file__).with_name('_arq_recovery_worker.py')
COMMAND = 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05'


async def spawn(mode, queue):
    env = {**os.environ, 'DATABASE_URL': os.environ['PAO_TEST_DATABASE_URL'],
           'PAO_TEST_ARQ_FAULT': mode, 'PAO_TEST_ARQ_QUEUE': queue,
           'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    return await asyncio.create_subprocess_exec(sys.executable, str(HARNESS), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)


async def kill(process):
    if process and process.returncode is None:
        process.kill()
        await asyncio.wait_for(process.wait(), 10)


@pytest.mark.parametrize('fault', ['between', 'during'])
async def test_real_arq_outbox_loss_and_wall_clock_crash_recovery(client, identity, fault, capsys):
    redis_settings = RedisSettings.from_dsn(settings().redis_url)
    assert redis_settings.database == 15, 'Refuse non-test Redis'
    queue = f'pao-test:arq-recovery:{uuid4()}'
    redis = await create_pool(redis_settings, default_queue_name=queue)
    first = second = None
    rid = None
    known_jobs = set()
    try:
        _, rid = await run_chat(client, identity, COMMAND)
        job_id = f'run:{rid}'
        known_jobs.add(job_id)
        # Lose only this API-created test job, not Redis service/data generally.
        # Committed PostgreSQL queued run must survive and be dispatched again.
        await redis.zrem('arq:queue', job_id)
        await redis.delete(job_key_prefix + job_id)
        assert not await redis.exists(job_key_prefix + job_id)
        first = await spawn(fault, queue)
        marker = await asyncio.wait_for(first.stdout.readline(), 20)
        assert marker.strip() == b'FAULT_READY', 'ARQ worker did not reach fault boundary'
        async with Session() as db:
            run = await db.get(Run, rid)
            assert run.status == 'running' and not run.response
            pinned = run.execution_plan['skill_snapshot']
            calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
            assert len(calls) == 1
            assert calls[0].status == ('completed' if fault == 'between' else 'running')
            known_jobs.add(f'tool:{calls[0].id}')
        assert await redis.exists(in_progress_key_prefix + job_id), 'Job not claimed by real ARQ'
        await kill(first)
        assert first.returncode != 0
        started = asyncio.get_running_loop().time()
        second = await spawn('recover', queue)
        deadline = started + 115
        recovered = False
        while asyncio.get_running_loop().time() < deadline:
            assert second.returncode is None, 'Recovery worker exited unexpectedly'
            async with Session() as db:
                run = await db.get(Run, rid)
                calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
                if (run.status == 'failed' and len(calls) == 1 and
                        calls[0].status == ('completed' if fault == 'between' else 'unknown')):
                    recovered = True
                    break
            await asyncio.sleep(1)
        elapsed = asyncio.get_running_loop().time() - started
        assert recovered, 'Real-clock recovery exceeded 115s acceptance bound'
        assert elapsed >= (65 if fault == 'between' else 85), 'Lease clock was bypassed'
        async with Session() as db:
            run = await db.get(Run, rid)
            assert run.error_code == 'worker_lost' and not run.response
            assert run.execution_plan['skill_snapshot'] == pinned and not run.execution_plan.get('skill_result')
            calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
            assert len(calls) == 1
            if fault == 'during': assert calls[0].error_code == 'worker_lost'
            events = list(await db.scalars(select(RunEvent.type).where(RunEvent.run_id == rid)))
            assert events.count('run.started') == 1 and events.count('run.failed') == 1
            assert 'run.completed' not in events and 'response.completed' not in events
            audit = list(await db.scalars(select(ToolAudit.event).where(ToolAudit.run_id == rid)))
            assert audit.count('tool.proposed') == 1 and audit.count('tool.started') == 1
        with capsys.disabled():
            print(f'\nPASS real ARQ/Redis {fault}: recovered after {elapsed:.2f}s real clock, one tool claim')
    finally:
        await kill(first)
        await kill(second)
        # Delete only UUID-scoped queue and its known test job keys. Never FLUSHDB.
        known_jobs.update(item.decode() if isinstance(item, bytes) else item
                          for item in await redis.zrange(queue, 0, -1))
        keys = [queue, queue + ':health-check']
        for job_id in known_jobs:
            keys.extend(prefix + job_id for prefix in (job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix))
        await redis.delete(*keys)
        await redis.aclose()
