"""Real child API/outbox/Temporal/activity/ARQ abort; no Goal parent claim."""
import asyncio
import signal
from datetime import timedelta
from uuid import uuid4
import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix,abort_jobs_ss
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker,Replayer
from sqlalchemy import select,func
from pao.config import ROOT,settings
from pao.db import Session
from pao.models import StudioEvent,StudioCommand,TaskAttempt,Task,Run
from pao.modules.studio import durable,arq_bridge as bridge,queue_cancel
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as W
from test_durable_admission import gates,plan,start,BASE
from test_studio_arq_bridge import close_worker


@pytest.mark.parametrize('worker_available,late_signal',[(True,False),(False,False),(True,True)])
async def test_real_temporal_cancel_drains_or_holds_unknown(client,identity,gates,monkeypatch,worker_available,late_signal):
    drained=asyncio.Event()
    original_drain=bridge.DryRunBridge.drain
    async def tracked_drain(self,args):
        result=await original_drain(self,args)
        if result.get('queue_ack_verified') is True:drained.set()
        return result
    monkeypatch.setattr(bridge.DryRunBridge,'drain',tracked_drain)
    async def deliver(row,item):
        if late_signal and item.operation=='cancel':
            # Force the actual native abort ACK before Temporal sees its signal.
            # No mocked queue/DB/Temporal result and no relaxed final assertion.
            await asyncio.wait_for(drained.wait(),10)
            await asyncio.sleep(.5)
        return await durable.Gateway.deliver(durable.gateway,row,item)
    monkeypatch.setattr(durable.gateway,'deliver',deliver)
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:temporal-cancel:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    started=asyncio.Event();original=bridge.jobs.claim
    async def paused(*args):
        result=await original(*args)
        assert result['claimed'] is True
        started.set()
        await asyncio.Event().wait()
        return result
    monkeypatch.setattr(bridge.jobs,'claim',paused)
    class EchoWorker:
        functions=[bridge.execute_studio_echo]
        redis_settings=config
        queue_name=queue
        health_check_key=queue+':health'
        handle_signals=False
        allow_abort_jobs=True
        max_jobs=1
        keep_result=30
        max_tries=1
        poll_delay=.05
        job_timeout=30
    runner=None;running=None;value=None
    directory=ROOT/'.runtime'/('p63-child-cancel-'+uuid4().hex);directory.mkdir()
    from temporal_fixture import cached_binary
    binary=cached_binary(ROOT)
    temporal_queue='p63-child-cancel-'+uuid4().hex
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',temporal_queue)
    try:
        if worker_available:
            runner=create_worker(EchoWorker);running=asyncio.create_task(runner.async_run())
        async with await WorkflowEnvironment.start_local(ui=False,dev_server_existing_path=binary,
                dev_server_database_filename=str(directory/'temporal.sqlite')) as env:
            monkeypatch.setattr(durable.gateway,'client',env.client)
            adapter=bridge.DryRunBridge(redis,require_queue_ack=True)
            async with Worker(env.client,task_queue=temporal_queue,workflows=[W],
                    activities=[durable.project_state,adapter.step],graceful_shutdown_timeout=timedelta(seconds=2)):
                value=await plan(client,identity)
                _,response=await start(client,identity,value,timeout_seconds=60)
                assert response.status_code==202
                assert await durable.dispatch_commands()==1
                handle=env.client.get_workflow_handle('p62-'+value['plan_id'])
                url=BASE+'/executions/'+value['plan_id']
                for _ in range(150):
                    row=(await client.get(url,headers=identity['owner'])).json()
                    if row['status']=='waiting_approval':break
                    await asyncio.sleep(.1)
                else:raise AssertionError(row)
                response=await client.post(url+'/decision',headers=identity['owner'],json={
                    'request_key':str(uuid4()),'version':row['version'],'step_id':'first','decision':'approve'})
                assert response.status_code==200
                assert await durable.dispatch_commands()==1
                job_id='p62:'+value['task_ids'][0]
                if worker_available:await asyncio.wait_for(started.wait(),15)
                else:
                    for _ in range(150):
                        if await redis.zscore(queue,job_id) is not None:break
                        await asyncio.sleep(.1)
                    else:raise AssertionError('activity never enqueued')
                key=str(uuid4())
                response=await client.post(url+'/cancel',headers=identity['owner'],json={'request_key':key})
                assert response.status_code==200
                assert await durable.dispatch_commands()==1
                result=await asyncio.wait_for(handle.result(),25)
                assert result['status'] in ('cancelled','manual_review')
                if worker_available:assert result['status']=='cancelled'
                async with Session() as db:
                    command=await db.scalar(select(StudioCommand).where(StudioCommand.operation=='cancel'))
                    assert command.status=='delivered' and command.attempts==1 and command.delivered_at
                    ack=await db.get(StudioEvent,queue_cancel.ack_id(value['task_ids'][0]))
                    if worker_available:
                        assert ack and ack.data['ack']=='arq_aborted'
                        assert ack.data['queue_drained'] is True
                        attempt=await db.get(TaskAttempt,value['task_ids'][0])
                        assert attempt.status=='cancelled'
                    else:assert ack is None
                    assert await db.scalar(select(func.count(Run.id)))==0
                    assert all(task.status=='draft' for task in await db.scalars(select(Task)))
                if worker_available:
                    assert await redis.zscore(queue,job_id) is None
                    assert not await redis.exists(in_progress_key_prefix+job_id)
                else:assert await redis.zscore(queue,job_id) is not None
                # Duplicate HTTP cancellation never schedules another native attempt.
                assert (await client.post(url+'/cancel',headers=identity['owner'],json={'request_key':key})).status_code==200
                assert await durable.dispatch_commands()==0
                history=await handle.fetch_history()
            await Replayer(workflows=[W]).replay_workflow(history)
            (directory/'history.json').write_text(history.to_json(),encoding='utf-8')
    finally:
        if runner:
            runner.handle_sig(signal.SIGTERM)
            try:await asyncio.wait_for(running,10)
            except asyncio.CancelledError:pass
            await close_worker(runner)
        if value:
            for ident in value['task_ids']:
                job_id='p62:'+ident
                await redis.delete(*(prefix+job_id for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
                await redis.zrem(abort_jobs_ss,job_id)
        await redis.delete(queue,queue+':health');await redis.aclose()


async def test_strict_drain_cannot_invent_user_cancel(client,identity,gates):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from pao.models import StudioExecution
    from test_studio_step_jobs import ready
    value,ident=await ready(client,identity)
    args=(value['plan_id'],'first',ident)
    await bridge.jobs.reserve(*args)
    adapter=bridge.DryRunBridge(SimpleNamespace(default_queue_name='pao-test:no-access'),require_queue_ack=True)
    with pytest.raises(HTTPException):await adapter.drain(args)
    async with Session() as db:
        assert (await db.get(StudioExecution,value['plan_id'])).cancel_requested is False
        assert await db.get(StudioEvent,queue_cancel.ack_id(ident)) is None
        assert await db.get(StudioEvent,bridge.jobs.event_id(ident,'outcome')) is None
