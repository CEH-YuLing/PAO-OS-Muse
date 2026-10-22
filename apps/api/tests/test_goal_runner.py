"""Real API/Postgres/Temporal/ARQ/Redis15, fixed Echo; no provider calls."""
import asyncio,signal
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from temporalio.worker import Worker,Replayer
from temporalio.exceptions import ApplicationError
from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,StudioExecution,StudioEvent,TaskAttempt,Run,Member
from pao.modules.goals import runner
from pao.modules.goals.runner_workflow import PaoGoalRunnerWorkflow as W
from pao.modules.goals.runner_transport import RunnerDispatcher,RunnerGateway
from pao.modules.studio import durable,arq_bridge as bridge
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as Child
from test_goal_admission import draft,goal_gates
from test_goal_iterations import iteration_gates
from test_goal_temporal_kernel import temporal
from test_studio_arq_bridge import close_worker


@pytest.fixture
def runner_gates(monkeypatch,iteration_gates):
    for key in ('goal_runner_enabled','workflow_dispatch_enabled','workflow_worker_enabled'):
        monkeypatch.setattr(settings(),key,True)


async def admission(client,identity,**changes):
    goal,p,_,body=await draft(client,identity)
    body['policy']['max_elapsed_seconds']=300
    body['proposal']['max_duration_seconds']=60
    body['success_criteria']=[{'field':'text','rule':'equals','value':changes.get('target','Target reached')}]
    if 'iterations' in changes:body['policy']['max_iterations']=changes['iterations']
    preview=await client.post('/v1/goals/'+goal['id']+'/dry-run-admission-preview',headers=identity['owner'],json={k:v for k,v in body.items() if k!='confirmation_hash'})
    assert preview.status_code==200,preview.text
    body['confirmation_hash']=preview.json()['confirmation_hash']
    result=await client.post('/v1/goals/'+goal['id']+'/dry-run-runners',headers=identity['owner'],json=body)
    assert result.status_code==201,result.text
    return goal,p,result.json(),body


async def read(client,identity,row):
    r=await client.get('/v1/goal-executions/'+row['execution_id'],headers=identity['owner'])
    assert r.status_code==200,r.text;return r.json()


async def wait(client,identity,row,status):
    for _ in range(300):
        value=await read(client,identity,row)
        if value['status']==status:return value
        if value['status'] in ('manual_review','deadline_exceeded','cancelled') and value['status']!=status:
            pytest.fail('Unexpected runner state: '+str(value['state']))
        await asyncio.sleep(.1)
    pytest.fail('Runner did not reach '+status+'; latest='+str(value['state']))


async def approve(client,identity,row):
    value=await wait(client,identity,row,'waiting_approval')
    r=await client.post('/v1/goal-executions/'+row['execution_id']+'/decision',headers=identity['owner'],json={
        'request_key':str(uuid4()),'version':value['version'],'proposal_hash':value['state']['proposal_hash'],'decision':'approve'})
    assert r.status_code==200,r.text


async def approve_steps(client,identity,plan_id):
    approved=set()
    for _ in range(300):
        r=await client.get('/v1/studio/executions/'+plan_id,headers=identity['owner'])
        if r.status_code==404:await asyncio.sleep(.1);continue
        assert r.status_code==200,r.text
        value=r.json();step=value['state'].get('current_step')
        if value['status']=='completed':return
        if value['status']=='waiting_approval' and step not in approved:
            response=await client.post('/v1/studio/executions/'+plan_id+'/decision',headers=identity['owner'],json={
                'request_key':str(uuid4()),'version':value['version'],'step_id':step,'decision':'approve'})
            assert response.status_code==200,response.text;approved.add(step)
        if value['status'] in ('cancelled','manual_review'):pytest.fail('Child stopped: '+str(value['state']))
        await asyncio.sleep(.1)
    pytest.fail('Child not completed')


@asynccontextmanager
async def stack(env,monkeypatch):
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:goal-runner:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    task_queue='p63r-'+uuid4().hex
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',task_queue)
    monkeypatch.setattr(durable.gateway,'client',env.client)
    monkeypatch.setattr(durable.gateway,'deliver',durable.Gateway.deliver.__get__(durable.gateway))
    class Echo:
        functions=[bridge.execute_studio_echo];redis_settings=config;queue_name=queue
        health_check_key=queue+':health';handle_signals=False;allow_abort_jobs=True
        max_jobs=1;keep_result=60;max_tries=1;poll_delay=.05;job_timeout=30
    arq=create_worker(Echo);job=asyncio.create_task(arq.async_run())
    adapters=runner.RunnerActivities(redis);transport=RunnerDispatcher(RunnerGateway(env.client))
    async def dispatch():
        while True:
            await transport.dispatch();await durable.dispatch_commands();await asyncio.sleep(.05)
    dispatch_task=asyncio.create_task(dispatch())
    def worker():return Worker(env.client,task_queue=task_queue,workflows=[W,Child],
        activities=[runner.poll_activity,runner.launch_activity,runner.finish_activity,runner.stop_activity,
            runner.uncertain_activity,adapters.reconcile,durable.project_state,bridge.DryRunBridge(redis,require_queue_ack=True).step],
        graceful_shutdown_timeout=timedelta(seconds=2))
    try:yield worker,redis
    finally:
        dispatch_task.cancel();await asyncio.gather(dispatch_task,return_exceptions=True)
        arq.handle_sig(signal.SIGTERM)
        try:await asyncio.wait_for(job,10)
        except asyncio.CancelledError:pass
        await close_worker(arq)
        await redis.delete(queue,queue+':health');await redis.aclose()


async def test_real_runner_two_iterations_replan_receipts_and_replay(client,identity,runner_gates,temporal,monkeypatch):
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            goal,p,row,_=await admission(client,identity)
            await approve(client,identity,row);await approve_steps(client,identity,p['plan_id'])
            value=await wait(client,identity,row,'waiting_replan')
            assert value['reserved_cost_microusd']==0 and value['state']['iteration']==1
            workflow=p['snapshot']['workflow'];base='/v1/studio/definitions/'+workflow['definition_id']
            draft={'version_id':workflow['version_id'],'request_key':str(uuid4()),'input':{'text':'Target reached'}}
            preview=await client.post(base+'/plan-preview',headers=identity['owner'],json=draft)
            assert preview.status_code==200,preview.text
            new=await client.post(base+'/plans',headers=identity['owner'],json={**draft,'confirmation_hash':preview.json()['sha256']})
            assert new.status_code==201,new.text
            p2=new.json();body={'request_key':str(uuid4()),'version':value['version'],'proposal':{
                'plan_id':p2['plan_id'],'snapshot_hash':p2['snapshot']['sha256'],'cost_ceiling_microusd':5,'max_duration_seconds':60}}
            response=await client.post('/v1/goal-executions/'+row['execution_id']+'/proposal',headers=identity['owner'],json=body)
            assert response.status_code==200,response.text
            # Duplicate proposal cannot reserve or execute a second child.
            assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/proposal',headers=identity['owner'],json=body)).status_code==200
            await approve(client,identity,row);await approve_steps(client,identity,p2['plan_id'])
            final=await wait(client,identity,row,'completed')
            assert final['state']['iteration']==2 and final['reserved_cost_microusd']==0
            handle=env.client.get_workflow_handle('p63-'+row['execution_id'])
            assert (await asyncio.wait_for(handle.result(),15))['status']=='completed'
            history=await handle.fetch_history()
            assert sum(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)==2
            await Replayer(workflows=[W]).replay_workflow(history)
            for ident in (p['plan_id'],p2['plan_id']):
                await Replayer(workflows=[Child]).replay_workflow(await env.client.get_workflow_handle('p62-'+ident).fetch_history())
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id)))==4
        assert await db.scalar(select(func.count(Run.id)))==0
        assert (await db.get(Goal,goal['id'])).status=='draft'  # Echo never completes a business Goal.
        saved=await db.get(GoalExecution,row['execution_id']);await runner.reconstruct(db,saved)
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='runner_launch'))==2


@pytest.mark.parametrize('rollback',[False,True])
async def test_real_runner_cold_worker_and_cancel_waiting_child(client,identity,runner_gates,temporal,monkeypatch,rollback):
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,p,row,_=await admission(client,identity)
            await approve(client,identity,row)
            for _ in range(150):
                async with Session() as db:child=await db.get(StudioExecution,p['plan_id'])
                if child and child.status=='waiting_approval':break
                await asyncio.sleep(.1)
            assert child.status=='waiting_approval'
        # No browser/worker present when authorized cancellation is committed.
        r=await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],json={'request_key':str(uuid4())})
        assert r.status_code==200,r.text
        if rollback:settings().goal_runner_enabled=False;settings().goal_admission_enabled=False
        async with worker():
            handle=env.client.get_workflow_handle('p63-'+row['execution_id'])
            result=await asyncio.wait_for(handle.result(),25)
            assert result['status']=='cancelled' and result['reserved_cost_microusd']==0
            history=await handle.fetch_history()
            assert sum(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)==1
            await Replayer(workflows=[W]).replay_workflow(history)
    async with Session() as db:assert await db.scalar(select(func.count(TaskAttempt.id)))==0


async def test_runner_disabled_does_not_upgrade_legacy(client,identity,iteration_gates):
    goal,_,url,body=await draft(client,identity)
    assert (await client.post('/v1/goals/'+goal['id']+'/dry-run-runners',headers=identity['owner'],json=body)).status_code==503
    legacy=await client.post(url,headers=identity['owner'],json=body);assert legacy.status_code==201
    settings().goal_runner_enabled=True
    settings().workflow_worker_enabled=True;settings().workflow_dispatch_enabled=True
    assert (await client.post('/v1/goals/'+goal['id']+'/dry-run-runners',headers=identity['owner'],json=body)).status_code==409


async def test_runner_projection_tamper_fails_closed(client,identity,runner_gates):
    _,_,row,_=await admission(client,identity)
    # Transport fixture only for this boundary test; end-to-end is above.
    from pao.models import GoalCommand,now
    async with Session.begin() as db:
        start=await db.scalar(select(GoalCommand));start.status='delivered';start.attempts=1;start.delivered_at=now()
    await runner.poll(row['execution_id'],'p63-'+row['execution_id'])
    async with Session.begin() as db:
        saved=await db.get(GoalExecution,row['execution_id']);saved.state={**saved.state,'iteration':9}
    with pytest.raises(ApplicationError,match='goal_runner_projection_changed'):
        await runner.poll(row['execution_id'],'p63-'+row['execution_id'])


async def test_real_runner_cancel_claimed_arq_drains_ack(client,identity,runner_gates,temporal,monkeypatch):
    env,_=temporal;started=asyncio.Event();original=bridge.jobs.claim
    async def paused(*args):
        result=await original(*args)
        if result['claimed']:
            started.set();await asyncio.Event().wait()
        return result
    monkeypatch.setattr(bridge.jobs,'claim',paused)
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,p,row,_=await admission(client,identity)
            await approve(client,identity,row)
            for _ in range(200):
                r=await client.get('/v1/studio/executions/'+p['plan_id'],headers=identity['owner'])
                if r.status_code==200 and r.json()['status']=='waiting_approval':break
                await asyncio.sleep(.1)
            value=r.json()
            response=await client.post('/v1/studio/executions/'+p['plan_id']+'/decision',headers=identity['owner'],json={
                'request_key':str(uuid4()),'version':value['version'],'step_id':'first','decision':'approve'})
            assert response.status_code==200,response.text
            await asyncio.wait_for(started.wait(),15)
            response=await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],json={'request_key':str(uuid4())})
            assert response.status_code==200,response.text
            result=await asyncio.wait_for(env.client.get_workflow_handle('p63-'+row['execution_id']).result(),30)
            assert result['status']=='cancelled' and result['reserved_cost_microusd']==0
            async with Session() as db:
                attempt=await db.scalar(select(TaskAttempt));assert attempt.status=='cancelled'
                assert await db.scalar(select(func.count(StudioEvent.id)).where(StudioEvent.action=='p62_step_queue_cancel_ack'))==1


async def test_real_runner_iteration_ceiling_stops_without_second_child(client,identity,runner_gates,temporal,monkeypatch):
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,p,row,_=await admission(client,identity,iterations=1)
            await approve(client,identity,row);await approve_steps(client,identity,p['plan_id'])
            result=await asyncio.wait_for(env.client.get_workflow_handle('p63-'+row['execution_id']).result(),20)
            assert result['status']=='budget_exhausted' and result['iteration']==1 and result['reserved_cost_microusd']==0
            history=await env.client.get_workflow_handle('p63-'+row['execution_id']).fetch_history()
            assert sum(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)==1


async def test_launch_retry_same_owner_only_and_authority_loss(client,identity,runner_gates,monkeypatch):
    _,p,row,_=await admission(client,identity)
    from pao.models import GoalCommand,now
    from pao.modules.goals.runner_transport import RunnerDispatcher
    class Transport:
        async def deliver(self,*args):pass
    transport=RunnerDispatcher(Transport())
    await transport.dispatch();await runner.poll(row['execution_id'],'p63-'+row['execution_id'])
    await approve(client,identity,row);await transport.dispatch()
    state=await runner.poll(row['execution_id'],'p63-'+row['execution_id'])
    assert state['state']['status']=='running'
    commands=await asyncio.gather(*(runner.launch(row['execution_id'],'p63-'+row['execution_id'],'owned-run',1) for _ in range(2)))
    assert commands[0]==commands[1]
    with pytest.raises(ApplicationError,match='goal_runner_launch_owner_changed'):
        await runner.launch(row['execution_id'],'p63-'+row['execution_id'],'other-run',1)
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    from fastapi import HTTPException
    with pytest.raises(HTTPException):await runner.launch(row['execution_id'],'p63-'+row['execution_id'],'owned-run',1)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='runner_launch'))==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


async def test_real_runner_lost_launch_ack_reuses_intent_not_child(client,identity,runner_gates,temporal,monkeypatch):
    from temporalio import activity
    original=runner.launch_activity;calls=0
    @activity.defn(name='p63r_launch')
    async def lose_once(data:dict):
        nonlocal calls
        command=await original(data);calls+=1
        if calls==1:raise ApplicationError('synthetic_commit_without_ack')
        return command
    monkeypatch.setattr(runner,'launch_activity',lose_once)
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,p,row,_=await admission(client,identity,target='Fixture planning')
            await approve(client,identity,row);await approve_steps(client,identity,p['plan_id'])
            result=await asyncio.wait_for(env.client.get_workflow_handle('p63-'+row['execution_id']).result(),20)
            assert result['status']=='completed' and calls==2
            history=await env.client.get_workflow_handle('p63-'+row['execution_id']).fetch_history()
            assert sum(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)==1
            await Replayer(workflows=[W]).replay_workflow(history)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='runner_launch'))==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==2


async def test_real_runner_missing_queue_ack_retains_ceiling(client,identity,runner_gates,temporal,monkeypatch):
    from pao.modules.studio import queue_cancel
    async def unknown(*args,**kw):return {'status':'unknown','queue_ack_verified':False}
    monkeypatch.setattr(queue_cancel,'cancel_queue_step',unknown)
    started=asyncio.Event();original=bridge.jobs.claim
    async def paused(*args):
        result=await original(*args)
        if result['claimed']:started.set();await asyncio.Event().wait()
        return result
    monkeypatch.setattr(bridge.jobs,'claim',paused)
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,p,row,_=await admission(client,identity);await approve(client,identity,row)
            for _ in range(200):
                r=await client.get('/v1/studio/executions/'+p['plan_id'],headers=identity['owner'])
                if r.status_code==200 and r.json()['status']=='waiting_approval':break
                await asyncio.sleep(.1)
            value=r.json()
            assert (await client.post('/v1/studio/executions/'+p['plan_id']+'/decision',headers=identity['owner'],json={
                'request_key':str(uuid4()),'version':value['version'],'step_id':'first','decision':'approve'})).status_code==200
            await asyncio.wait_for(started.wait(),15)
            assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],json={'request_key':str(uuid4())})).status_code==200
            result=await asyncio.wait_for(env.client.get_workflow_handle('p63-'+row['execution_id']).result(),30)
            assert result['status']=='manual_review' and result['reserved_cost_microusd']==5
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='runner_launch'))==1


async def test_launch_rechecks_revoked_approver_not_only_owner(client,identity,runner_gates):
    _,_,row,_=await admission(client,identity)
    class Transport:
        async def deliver(self,*args):pass
    transport=RunnerDispatcher(Transport())
    await transport.dispatch();value=await runner.poll(row['execution_id'],'p63-'+row['execution_id'])
    async with Session.begin() as db:
        approver=await db.scalar(select(Member).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        approver.role='admin';approver_id=approver.user_id
    current=await read(client,identity,row)
    response=await client.post('/v1/goal-executions/'+row['execution_id']+'/decision',headers=identity['other'],json={
        'request_key':str(uuid4()),'version':current['version'],'proposal_hash':current['state']['proposal_hash'],'decision':'approve'})
    assert response.status_code==200,response.text
    await transport.dispatch();await runner.poll(row['execution_id'],'p63-'+row['execution_id'])
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],approver_id))).role='viewer'
    from fastapi import HTTPException
    with pytest.raises(HTTPException):await runner.launch(row['execution_id'],'p63-'+row['execution_id'],'owned-run',1)
    async with Session() as db:
        assert (await db.get(Member,(identity['workspace'],identity['user_id']))).role=='owner'
        assert await db.scalar(select(func.count(StudioExecution.id)))==0


async def test_real_runner_partial_child_cancel_verifies_completed_prefix(client,identity,runner_gates,temporal,monkeypatch):
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,p,row,_=await admission(client,identity);await approve(client,identity,row)
            first=False
            for _ in range(200):
                response=await client.get('/v1/studio/executions/'+p['plan_id'],headers=identity['owner'])
                if response.status_code==404:await asyncio.sleep(.1);continue
                value=response.json()
                if value['status']=='waiting_approval' and value['state']['current_step']=='first' and not first:
                    r=await client.post('/v1/studio/executions/'+p['plan_id']+'/decision',headers=identity['owner'],json={
                        'request_key':str(uuid4()),'version':value['version'],'step_id':'first','decision':'approve'})
                    assert r.status_code==200,r.text;first=True
                if value['status']=='waiting_approval' and value['state']['current_step']=='second':break
                await asyncio.sleep(.1)
            assert value['state']['completed_steps']==['first']
            response=await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],json={'request_key':str(uuid4())})
            assert response.status_code==200,response.text
            result=await asyncio.wait_for(env.client.get_workflow_handle('p63-'+row['execution_id']).result(),25)
            assert result['status']=='cancelled' and result['reserved_cost_microusd']==0
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id)))==1
        assert (await db.scalar(select(TaskAttempt))).status=='completed'


async def test_real_runner_idle_timer_deadline_without_browser_or_poll_storm(client,identity,runner_gates,temporal,monkeypatch):
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            goal,p,_,body=await draft(client,identity)
            body['policy']['max_elapsed_seconds']=6;body['proposal']['max_duration_seconds']=1
            preview=await client.post('/v1/goals/'+goal['id']+'/dry-run-admission-preview',headers=identity['owner'],json={k:v for k,v in body.items() if k!='confirmation_hash'})
            assert preview.status_code==200,preview.text
            body['confirmation_hash']=preview.json()['confirmation_hash']
            response=await client.post('/v1/goals/'+goal['id']+'/dry-run-runners',headers=identity['owner'],json=body)
            assert response.status_code==201,response.text
            row=response.json();handle=env.client.get_workflow_handle('p63-'+row['execution_id'])
            # The dispatcher creates it; wait for immutable initial state first.
            await wait(client,identity,row,'waiting_approval')
            result=await asyncio.wait_for(handle.result(),15)
            assert result['status']=='deadline_exceeded' and result['reserved_cost_microusd']==0
            history=await handle.fetch_history()
            polls=[e for e in history.events if e.HasField('activity_task_scheduled_event_attributes') and
                e.activity_task_scheduled_event_attributes.activity_type.name=='p63r_poll']
            assert len(polls)==2  # Initial state + exact deadline, no one-second idle loop.
            assert not any(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)
            await Replayer(workflows=[W]).replay_workflow(history)
