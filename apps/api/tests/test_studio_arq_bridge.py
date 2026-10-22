"""Real Temporal + ARQ + Redis15 + API/DB; fixed synthetic echo only."""
import asyncio
import signal
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from datetime import timedelta
from uuid import uuid4
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from arq.constants import job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker, Replayer
from sqlalchemy import select, func
from pao.db import Session
from pao.config import ROOT, settings
from temporal_fixture import cached_binary
from pao.models import TaskAttempt, Task, Run, StudioEvent
from pao.modules.studio import durable, arq_bridge as bridge
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as W
from test_durable_admission import plan, start, BASE, gates
from test_studio_step_jobs import ready


async def close_worker(worker):
    if not hasattr(signal, 'SIGUSR1'):
        worker.handle_sig(signal.SIGTERM); worker._handle_signals = True
    await worker.close()


async def test_real_temporal_arq_two_steps_and_receipt_replay(client, identity, gates, monkeypatch):
    # gates mocks delivery; restore the actual gateway for this integration.
    monkeypatch.setattr(durable.gateway, 'deliver', durable.Gateway.deliver.__get__(durable.gateway))
    config = RedisSettings.from_dsn(settings().redis_url); assert config.database == 15
    queue = 'pao-test:p62c:' + uuid4().hex
    redis = await create_pool(config, default_queue_name=queue)
    class EchoWorker:
        functions = [bridge.execute_studio_echo]
        redis_settings = config
        queue_name = queue
        health_check_key = queue + ':health'
        handle_signals = False
        max_jobs = 1
        keep_result = 0
        max_tries = 1
        poll_delay = .05
        job_timeout = 20
    runner = create_worker(EchoWorker); running = asyncio.create_task(runner.async_run())
    value = None
    directory = ROOT / '.runtime' / ('p62c-bridge-' + uuid4().hex); directory.mkdir()
    binary = cached_binary(ROOT)
    temporal_queue = 'p62c-' + uuid4().hex
    monkeypatch.setattr(settings(), 'workflow_temporal_task_queue', temporal_queue)
    try:
        async with await WorkflowEnvironment.start_local(ui=False,
                dev_server_existing_path=binary,
                dev_server_database_filename=str(directory / 'temporal.sqlite')) as env:
            monkeypatch.setattr(durable.gateway, 'client', env.client)
            class FailFirstEnqueue:
                calls = 0
                async def enqueue_job(self, *args, **kwargs):
                    self.calls += 1
                    if self.calls == 1:
                        async with Session() as db:
                            assert await db.scalar(select(func.count(TaskAttempt.id))) == 0
                        raise RedisConnectionError('synthetic transient disconnect')
                    return await redis.enqueue_job(*args, **kwargs)
            flaky = FailFirstEnqueue()
            activity_bridge = bridge.DryRunBridge(flaky)
            async with Worker(env.client, task_queue=temporal_queue, workflows=[W],
                    activities=[durable.project_state, activity_bridge.step],
                    graceful_shutdown_timeout=timedelta(seconds=2)):
                value = await plan(client, identity)
                _, response = await start(client, identity, value, timeout_seconds=60)
                assert response.status_code == 202
                assert await durable.dispatch_commands() == 1
                handle = env.client.get_workflow_handle('p62-' + value['plan_id'])
                for key in ('first', 'second'):
                    for _ in range(150):
                        response = await client.get(BASE + '/executions/' + value['plan_id'], headers=identity['owner'])
                        row = response.json()
                        if row['status'] == 'waiting_approval' and row['state'].get('current_step') == key:
                            break
                        await asyncio.sleep(.1)
                    else:
                        raise AssertionError(row)
                    decision = {'request_key': str(uuid4()), 'version': row['version'], 'step_id': key, 'decision': 'approve'}
                    response = await client.post(BASE + '/executions/' + value['plan_id'] + '/decision',
                        json=decision, headers=identity['owner'])
                    assert response.status_code == 200
                    assert await durable.dispatch_commands() == 1
                result = await asyncio.wait_for(handle.result(), 35)
                assert result['status'] == 'completed'
                assert flaky.calls >= 3
                for key, ident in zip(('first', 'second'), value['task_ids']):
                    assert (await bridge.verified_receipt(value['plan_id'], key, ident))['status'] == 'completed'
                async with Session() as db:
                    assert await db.scalar(select(func.count(TaskAttempt.id)).where(TaskAttempt.status == 'completed')) == 2
                    assert await db.scalar(select(func.count(StudioEvent.id)).where(StudioEvent.action == 'p62_step_outcome')) == 2
                    assert await db.scalar(select(func.count(Run.id))) == 0
                    assert all(task.status == 'draft' for task in await db.scalars(select(Task)))
                history = await handle.fetch_history()
            await Replayer(workflows=[W]).replay_workflow(history)
            (directory / 'history.json').write_text(history.to_json(), encoding='utf-8')
    finally:
        runner.handle_sig(signal.SIGTERM)
        try:
            await asyncio.wait_for(running, 10)
        except asyncio.CancelledError:
            pass  # expected shutdown of the continuous ARQ polling task
        await close_worker(runner)
        if value:
            for ident in value['task_ids']:
                await redis.delete(*(prefix + 'p62:' + ident for prefix in
                    (job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix)))
        await redis.delete(queue)
        await redis.aclose()


async def test_duplicate_arq_delivery_no_second_claim(client, identity, gates):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await bridge.jobs.reserve(*args)
    result = await bridge.execute_studio_echo({}, *args)
    assert result['status'] == 'completed'
    assert await bridge.execute_studio_echo({}, *args) == {'status': 'completed', 'duplicate': True}
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 1


async def test_cancel_drain_flags_off_before_delivery(client, identity, gates):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await bridge.jobs.reserve(*args)
    settings().workflow_durable_enabled = False
    result = await bridge.cancel_and_drain(*args)
    assert result == {'status': 'cancelled', 'known_no_effect': True}
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0


async def test_activity_cancel_drains_reserved_without_worker(client, identity, gates, monkeypatch):
    value, ident = await ready(client, identity)
    arrived = asyncio.Event()
    class QueueWithoutWorker:
        async def enqueue_job(self, *args, **kwargs):
            arrived.set()
    monkeypatch.setattr(bridge.activity, 'heartbeat', lambda *args: None)
    task = asyncio.create_task(bridge.DryRunBridge(QueueWithoutWorker()).step({
        'plan_id': value['plan_id'], 'step_id': 'first', 'execution_id': ident}))
    await asyncio.wait_for(arrived.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await bridge.jobs.recover(value['plan_id'], 'first', ident) == {'status': 'cancelled'}
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0


async def test_adapter_failure_is_committed_not_orphan_claim(client, identity, gates, monkeypatch):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await bridge.jobs.reserve(*args)
    def invalid(*args):
        raise ValueError('synthetic incompatible output')
    monkeypatch.setattr(bridge.jobs, 'fixture_echo', invalid)
    assert await bridge.execute_studio_echo({}, *args) == {'status': 'failed', 'error_code': 'invalid_fixture_result'}
    assert await bridge.jobs.recover(*args) == {'status': 'failed'}
