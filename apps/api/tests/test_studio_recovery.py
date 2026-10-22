"""Actual abrupt ARQ process exit on isolated Redis15; no live process stopped."""
import asyncio
import os
import subprocess
import sys
from uuid import uuid4
from arq import create_pool
from arq.connections import RedisSettings
from arq.constants import job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix
import pytest
from sqlalchemy import select, func
from pao.config import settings
from pao.db import Session
from pao.models import TaskAttempt
from pao.modules.studio import arq_bridge as bridge
from test_durable_admission import gates
from test_studio_step_jobs import ready

CODE = '''
import asyncio,os
from arq.worker import Worker
from arq.connections import RedisSettings
from pao.config import settings
from pao.modules.studio import arq_bridge as bridge
async def execute_studio_echo(ctx,*args):
    if os.environ['STUDIO_CRASH_POINT']=='claim':
        claimed=await bridge.jobs.claim(*args)
        assert claimed['claimed']
        os._exit(91)
    result=await bridge.execute_studio_echo(ctx,*args)
    if os.environ['STUDIO_CRASH_POINT']=='redelivery':
        assert result=={'status':'completed','duplicate':True}
        return
    assert result['status']=='completed'
    os._exit(92)
async def main():
    worker=Worker([execute_studio_echo],redis_settings=RedisSettings.from_dsn(settings().redis_url),
        queue_name=os.environ['STUDIO_TEST_QUEUE'],health_check_key=os.environ['STUDIO_TEST_QUEUE']+':health',
        burst=True,max_burst_jobs=1,handle_signals=False,max_tries=1,poll_delay=.05,job_timeout=20)
    await worker.async_run()
asyncio.run(main())
'''

@pytest.mark.parametrize('point', ['claim','receipt'])
async def test_real_arq_process_exit_and_db_reconciliation(client, identity, gates, point):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await bridge.jobs.reserve(*args)
    config = RedisSettings.from_dsn(settings().redis_url); assert config.database == 15
    queue = 'pao-test:p62-death:' + uuid4().hex
    redis = await create_pool(config, default_queue_name=queue)
    jid = 'p62:' + ident
    env = {**os.environ, 'STUDIO_TEST_QUEUE': queue, 'STUDIO_CRASH_POINT': point,
        'STUDIO_ENABLED':'true', 'WORKFLOW_PLANNING_ENABLED':'true',
        'WORKFLOW_DURABLE_ENABLED':'true', 'TEMPORAL_ENABLED':'true'}
    try:
        assert await redis.enqueue_job('execute_studio_echo', *args, _job_id=jid)
        result = await asyncio.to_thread(subprocess.run, [sys.executable,'-c',CODE],
            env=env, timeout=25, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert result.returncode == (91 if point=='claim' else 92), result.stderr.decode(errors='replace')
        if point == 'claim':
            assert (await bridge.jobs.recover(*args))['status'] == 'running'
            # Real lease clock, not timestamp mutation or injected clock.
            for _ in range(65):
                result = await bridge.jobs.recover(*args)
                if result['status']=='failed': break
                await asyncio.sleep(1)
            assert result['status']=='failed' and result['error_code']=='worker_lost_unknown'
        else:
            assert await bridge.jobs.recover(*args) == {'status':'completed'}
            assert (await bridge.verified_receipt(*args))['status']=='completed'
            # A restarted ARQ subprocess receives the same execution envelope.
            # A distinct transport ID deliberately bypasses Redis dedup so the
            # immutable DB receipt, not the queue, must prevent another claim.
            # Separate isolated transport queue avoids waiting on the dead
            # process's ARQ in-progress lock; it does not bypass the DB claim.
            assert await redis.enqueue_job('execute_studio_echo',*args,_job_id=jid+':redelivery',_queue_name=queue+':redelivery')
            replay=await asyncio.to_thread(subprocess.run,[sys.executable,'-c',CODE],
                env={**env,'STUDIO_CRASH_POINT':'redelivery','STUDIO_TEST_QUEUE':queue+':redelivery'},timeout=25,
                stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            assert replay.returncode==0,replay.stderr.decode(errors='replace')
        async with Session() as db:
            assert await db.scalar(select(func.count(TaskAttempt.id))) == 1
    finally:
        await redis.delete(queue,queue+':health',queue+':redelivery',queue+':redelivery:health',*(prefix+jid for prefix in
            (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.delete(*(prefix+jid+':redelivery' for prefix in
            (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()
