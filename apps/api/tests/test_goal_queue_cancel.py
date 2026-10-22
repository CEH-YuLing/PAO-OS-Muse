"""Real child ARQ abort + Goal DB proof; parent Temporal ACKs are fixtures."""
import asyncio
import signal
from uuid import uuid4
import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix,abort_jobs_ss
from sqlalchemy import select,func
from fastapi import HTTPException
from temporalio.exceptions import ApplicationError
from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,GoalCommand,StudioExecution,StudioCommand,StudioEvent,TaskAttempt,Member,now
from pao.modules.goals import cancel_recovery
from pao.modules.studio import durable,arq_bridge as bridge,queue_cancel
from test_goal_admission import goal_gates
from test_goal_iterations import iteration_gates
from test_goal_recovery import stopped
from test_durable_admission import state
from test_studio_arq_bridge import close_worker


async def drained(client,identity,monkeypatch,claimed):
    row,data=await stopped(client,identity,monkeypatch,with_result=False,cancel=True)
    async with Session() as db:
        child=await db.get(StudioExecution,row['initial_proposal']['plan_id']);command=child.command
    value={'plan_id':child.id,'snapshot':{'sha256':command['snapshot_hash']}}
    await durable.project_state(state(value,1,'running'))
    step=command['steps'][0];args=(child.id,step['step_id'],step['execution_id'])
    await bridge.jobs.reserve(*args)
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:goal-cancel:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    started=asyncio.Event();original=bridge.jobs.claim
    async def paused(*args):
        result=await original(*args)
        assert result['claimed'] is True
        started.set()
        await asyncio.Event().wait()
        return result
    if claimed:monkeypatch.setattr(bridge.jobs,'claim',paused)
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
        job_timeout=20
    job_id='p62:'+args[2];runner=None;running=None
    try:
        await redis.enqueue_job('execute_studio_echo',*args,_job_id=job_id,_defer_by=None if claimed else 60)
        if claimed:
            runner=create_worker(EchoWorker);running=asyncio.create_task(runner.async_run())
            await asyncio.wait_for(started.wait(),10)
        assert (await client.post('/v1/studio/executions/'+child.id+'/cancel',headers=identity['owner'],
            json={'request_key':str(uuid4())})).status_code==200
        if not claimed:
            runner=create_worker(EchoWorker);running=asyncio.create_task(runner.async_run())
        ack=await queue_cancel.cancel_queue_step(redis,*args,timeout_seconds=3)
        assert ack['queue_ack_verified'] is True,ack
        # Explicit parent/child transport fixtures, NOT real Temporal ACKs.
        async with Session.begin() as db:
            for model in (GoalCommand,StudioCommand):
                item=await db.scalar(select(model).where(model.operation=='cancel'))
                item.status='delivered';item.attempts=1;item.delivered_at=now()
        await durable.project_state(state(value,2,'cancelled',cancel_requested=True,reason='requested'))
        return row,data,command,ack
    finally:
        if runner:
            runner.handle_sig(signal.SIGTERM)
            try:await asyncio.wait_for(running,10)
            except asyncio.CancelledError:pass
            await close_worker(runner)
        await redis.delete(*(prefix+job_id for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.zrem(abort_jobs_ss,job_id)
        await redis.delete(queue,queue+':health');await redis.aclose()


@pytest.mark.parametrize('claimed',[False,True])
async def test_real_queue_goal_reconcile_once(client,identity,iteration_gates,monkeypatch,claimed):
    row,data,command,ack=await drained(client,identity,monkeypatch,claimed)
    settings().goal_admission_enabled=False;settings().goal_iterations_enabled=False
    results=await asyncio.gather(*(cancel_recovery.reconcile_cancelled_queue(data,'p63-'+row['execution_id']) for _ in range(2)))
    assert results[0]==results[1] and results[0]['queue_ack_verified'] is True
    assert results[0]['known_no_effect'] is (not claimed) and results[0]['resumed'] is False
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='manual_review' and saved.sequence==2 and saved.reserved_cost_microusd==0
        version=saved.version
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        events=list(await db.scalars(select(GoalEvent).where(GoalEvent.action=='cancelled_queue_reconciled')))
        assert len(events)==1 and events[0].data['proof']['queue_acks'][0]['ack_id']==ack['ack_id']
        assert await db.scalar(select(func.count(TaskAttempt.id)))==int(claimed)
    await cancel_recovery.reconcile_cancelled_queue(data,'p63-'+row['execution_id'])
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).version==version


@pytest.mark.parametrize('kind',['permission','parent_ack','child_ack','attempt'])
async def test_real_ack_not_enough_without_goal_evidence(client,identity,iteration_gates,monkeypatch,kind):
    row,data,command,ack=await drained(client,identity,monkeypatch,True)
    async with Session.begin() as db:
        if kind=='permission':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif kind in ('parent_ack','child_ack'):
            model=GoalCommand if kind=='parent_ack' else StudioCommand
            (await db.scalar(select(model).where(model.operation=='cancel'))).status='pending'
        else:(await db.get(TaskAttempt,command['steps'][0]['execution_id'])).status='running'
    with pytest.raises((HTTPException,ApplicationError)):
        await cancel_recovery.reconcile_cancelled_queue(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='cancelled_queue_reconciled'))==0


async def test_no_queue_ack_holds_goal_reservation(client,identity,iteration_gates,monkeypatch):
    from test_goal_cancel_recovery import cancelled
    row,data,command=await cancelled(client,identity,monkeypatch,reserved=True,claimed=True)
    with pytest.raises((HTTPException,ApplicationError)):
        await cancel_recovery.reconcile_cancelled_queue(data,'p63-'+row['execution_id'])
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
