"""Native fixed-Echo terminal fencing, NOT real Goal/queue-drain acceptance."""
import asyncio
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func,text
from temporalio.exceptions import ApplicationError

from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,StudioEvent,StudioCommand,GoalCommand,TaskAttempt,Member
from pao.modules.goals import cancel_recovery
from pao.modules.studio import step_jobs as jobs
from test_goal_admission import goal_gates
from test_goal_iterations import iteration_gates
from test_goal_cancel_recovery import cancelled


async def native_cancel(client,identity,monkeypatch):
    # Native DB claim/recover are real; parent projection and command ACKs are
    # explicit fixtures inherited from cancelled(), not real transport evidence.
    return await cancelled(client,identity,monkeypatch,reserved=True,claimed=True)


async def test_native_cancel_concurrent_releases_once_without_resume(client,identity,iteration_gates,monkeypatch):
    row,data,command=await native_cancel(client,identity,monkeypatch)
    settings().goal_iterations_enabled=False;settings().goal_admission_enabled=False
    ident='p63-'+row['execution_id']
    values=await asyncio.gather(*(cancel_recovery.reconcile_cancelled_native(data,ident) for _ in range(2)))
    assert values[0]==values[1] and values[0]['known_no_effect'] is False and not values[0]['resumed']
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id']);version=saved.version
        assert saved.status=='manual_review' and saved.sequence==2 and saved.reserved_cost_microusd==0
        assert saved.state['reserved_cost_microusd']==0 and saved.state['checks']==[]
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        events=list(await db.scalars(select(GoalEvent).where(GoalEvent.action=='cancelled_native_reconciled')))
        assert len(events)==1
        proof=events[0].data['proof']
        assert proof['queue_ack_verified'] is False and proof['native_finish_fenced'] is True
        assert len(proof['claimed_steps'])==1 and len(proof['unclaimed_step_ids'])==1
        first=command['steps'][0]
        claimed=await db.get(StudioEvent,jobs.event_id(first['execution_id'],'claimed'))
        attempt=await db.get(TaskAttempt,first['execution_id'])
        token=claimed.data['token'];input_value=attempt.input
    # A late native worker commit cannot change the anchored cancellation.
    assert (await jobs.finish(command['plan_id'],first['step_id'],first['execution_id'],token,input_value))['status']=='cancelled'
    await cancel_recovery.reconcile_cancelled_native(data,ident)
    async with Session() as db: assert (await db.get(GoalExecution,row['execution_id'])).version==version


@pytest.mark.parametrize('kind',['missing_attempt','status','result','scope','input','snapshot','finished',
    'permission','parent_ack','child_ack','lease','bool_snapshot'])
async def test_native_cancel_invalid_evidence_holds_reservation(client,identity,iteration_gates,monkeypatch,kind):
    row,data,command=await native_cancel(client,identity,monkeypatch)
    async with Session.begin() as db:
        attempt=await db.get(TaskAttempt,command['steps'][0]['execution_id'])
        if kind=='missing_attempt':await db.delete(attempt)
        elif kind=='status':attempt.status='running'
        elif kind=='result':attempt.result={'cost':0,'forged':True}
        elif kind=='scope':attempt.task_id=command['steps'][1]['execution_id']
        elif kind=='input':attempt.input={'text':'forged'}
        elif kind=='snapshot':attempt.skill_snapshot={'dry_run':True}
        elif kind=='bool_snapshot':
            # ORM Python equality considers True == 1 and can suppress this
            # update. Persist the distinct JSON number for a real DB probe.
            await db.execute(text("UPDATE task_attempts SET skill_snapshot=jsonb_set(skill_snapshot::jsonb,'{dry_run}','1'::jsonb)::json WHERE id=:id"),
                {'id':attempt.id})
        elif kind=='finished':attempt.finished_at=None
        elif kind=='permission':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif kind in ('parent_ack','child_ack'):
            model=GoalCommand if kind=='parent_ack' else StudioCommand
            (await db.scalar(select(model).where(model.operation=='cancel'))).status='pending'
    if kind=='lease':monkeypatch.setattr(jobs,'LEASE_SECONDS',0)
    with pytest.raises((ApplicationError,HTTPException)):
        await cancel_recovery.reconcile_cancelled_native(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='cancelled_native_reconciled'))==0


async def test_no_claim_cannot_be_promoted_to_claimed_ack(client,identity,iteration_gates,monkeypatch):
    row,data,_=await cancelled(client,identity,monkeypatch,reserved=True)
    with pytest.raises(ApplicationError,match='claim_missing'):
        await cancel_recovery.reconcile_cancelled_native(data,'p63-'+row['execution_id'])
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


@pytest.mark.parametrize('kind',['extra','wrong_workflow','wrong_envelope'])
async def test_native_closed_contract(client,identity,iteration_gates,monkeypatch,kind):
    row,data,_=await native_cancel(client,identity,monkeypatch)
    ident='p63-'+row['execution_id']
    if kind=='extra':data={**data,'queue_ack':True}
    elif kind=='wrong_workflow':ident='p63-'+str(uuid4())
    else:data={'envelope':{**data['envelope'],'execution_id':str(uuid4())}}
    with pytest.raises(ApplicationError):await cancel_recovery.reconcile_cancelled_native(data,ident)
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


async def test_unknown_claim_never_becomes_cancelled_cost_zero(client,identity,iteration_gates,monkeypatch):
    from datetime import timedelta
    from pao.models import StudioExecution,now
    from pao.modules.studio import durable
    from test_goal_recovery import stopped
    from test_durable_admission import state
    row,data=await stopped(client,identity,monkeypatch,with_result=False,cancel=True)
    plan_id=row['initial_proposal']['plan_id']
    async with Session() as db:command=(await db.get(StudioExecution,plan_id)).command
    value={'plan_id':plan_id,'snapshot':{'sha256':command['snapshot_hash']}}
    await durable.project_state(state(value,1,'running'))
    first=command['steps'][0];args=(plan_id,first['step_id'],first['execution_id'])
    await jobs.reserve(*args);await jobs.claim(*args)
    future=now()+timedelta(seconds=jobs.LEASE_SECONDS+1)
    monkeypatch.setattr(jobs,'now',lambda:future)
    assert (await jobs.recover(*args))['error_code']=='worker_lost_unknown'
    # Deliberately contradictory parent/child ACK/projection fixtures cannot
    # erase the actual immutable UNKNOWN native outcome.
    assert (await client.post('/v1/studio/executions/'+plan_id+'/cancel',headers=identity['owner'],
        json={'request_key':str(uuid4())})).status_code==200
    async with Session.begin() as db:
        (await db.get(StudioExecution,plan_id)).cancel_requested=True
        for model in (GoalCommand,StudioCommand):
            item=await db.scalar(select(model).where(model.operation=='cancel'))
            item.status='delivered';item.attempts=1;item.delivered_at=now()
    await durable.project_state(state(value,2,'cancelled',cancel_requested=True,reason='requested'))
    with pytest.raises(ApplicationError,match='goal_cancel_'):
        await cancel_recovery.reconcile_cancelled_native(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        outcome=await db.get(StudioEvent,jobs.event_id(first['execution_id'],'outcome'))
        assert outcome.data['error_code']=='worker_lost_unknown'


async def test_native_wrapper_rejects_untrusted_origin(monkeypatch):
    from types import SimpleNamespace
    from pao.modules.goals import iterations
    info=SimpleNamespace(workflow_type='untrusted',workflow_namespace=settings().temporal_namespace,
        task_queue=settings().workflow_temporal_task_queue,workflow_id='p63-'+str(uuid4()))
    monkeypatch.setattr(iterations.activity,'info',lambda:info)
    with pytest.raises(ApplicationError,match='origin_invalid'):
        await cancel_recovery.reconcile_cancelled_native_activity({})


async def test_real_arq_late_finish_keeps_native_cancellation(client,identity,iteration_gates,monkeypatch):
    import signal
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.worker import create_worker,func as arq_func
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix
    from pao.models import StudioExecution,now
    from pao.modules.studio import durable
    from test_goal_recovery import stopped
    from test_durable_admission import state
    from test_studio_arq_bridge import close_worker
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:p63-claimed-cancel:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    ready=asyncio.Event();release=asyncio.Event()
    async def paused_echo(ctx,plan_id,step_id,execution_id):
        claimed=await jobs.claim(plan_id,step_id,execution_id)
        assert claimed['claimed'] is True
        ready.set()
        await release.wait()
        return await jobs.finish(plan_id,step_id,execution_id,claimed['token'],claimed['input'])
    class EchoWorker:
        functions=[arq_func(paused_echo,name='p63_test_echo')]
        redis_settings=config
        queue_name=queue
        health_check_key=queue+':health'
        handle_signals=False
        max_jobs=1
        keep_result=30
        max_tries=1
        poll_delay=.05
        job_timeout=20
    runner=create_worker(EchoWorker);running=asyncio.create_task(runner.async_run())
    job_id=None
    try:
        row,data=await stopped(client,identity,monkeypatch,with_result=False,cancel=True)
        plan_id=row['initial_proposal']['plan_id']
        async with Session() as db:command=(await db.get(StudioExecution,plan_id)).command
        value={'plan_id':plan_id,'snapshot':{'sha256':command['snapshot_hash']}}
        await durable.project_state(state(value,1,'running'))
        first=command['steps'][0];args=(plan_id,first['step_id'],first['execution_id'])
        await jobs.reserve(*args)
        job_id='p63-cancel:'+first['execution_id']
        job=await redis.enqueue_job('p63_test_echo',*args,_job_id=job_id)
        await asyncio.wait_for(ready.wait(),10)
        assert (await client.post('/v1/studio/executions/'+plan_id+'/cancel',headers=identity['owner'],
            json={'request_key':str(uuid4())})).status_code==200
        # Parent/child command delivery remains fixture, not real Temporal ACK.
        async with Session.begin() as db:
            for model in (GoalCommand,StudioCommand):
                item=await db.scalar(select(model).where(model.operation=='cancel'))
                item.status='delivered';item.attempts=1;item.delivered_at=now()
        assert (await jobs.recover(*args))['status']=='cancelled'
        await durable.project_state(state(value,2,'cancelled',cancel_requested=True,reason='requested'))
        result=await cancel_recovery.reconcile_cancelled_native(data,'p63-'+row['execution_id'])
        assert result['known_no_effect'] is False and result['reserved_cost_microusd']==0
        release.set()
        assert (await job.result(timeout=10))['status']=='cancelled'
        async with Session() as db:
            assert await db.scalar(select(func.count(TaskAttempt.id)))==1
            event=await db.get(StudioEvent,jobs.event_id(first['execution_id'],'outcome'))
            assert event.data['status']=='cancelled' and 'output' not in event.data
            assert (await db.get(Goal,row['goal_id'])).status=='draft'
    finally:
        release.set();runner.handle_sig(signal.SIGTERM)
        try:await asyncio.wait_for(running,10)
        except asyncio.CancelledError:pass
        await close_worker(runner)
        if job_id:
            await redis.delete(*(prefix+job_id for prefix in
                (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.delete(queue,queue+':health')
        await redis.aclose()
