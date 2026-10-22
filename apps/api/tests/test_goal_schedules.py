"""Shared scheduler -> real bounded Goal parent, no provider/live data writes."""
import asyncio,json,os,sys
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import StudioSchedule,GoalScheduleSlot,GoalExecution,GoalCommand,GoalEvent,Goal,Member,TaskAttempt,StudioExecution,Run,now
from pao.modules.schedules import store,dispatcher,goals
from pao.modules.goals import runner
from pao.modules.goals.evidence import verify_admission
from test_goal_admission import draft,goal_gates
from test_goal_iterations import iteration_gates
from test_goal_runner import runner_gates,stack,approve,approve_steps,wait
from test_goal_temporal_kernel import temporal
from pao.modules.goals.runner_workflow import PaoGoalRunnerWorkflow
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow
from temporalio.worker import Replayer

BASE='/v1/schedules/goals'

@pytest.fixture
def schedule_gates(monkeypatch,runner_gates):
    for key in ('studio_schedule_manager_enabled','studio_schedule_dispatch_enabled'):
        monkeypatch.setattr(settings(),key,True)

async def template(client,identity,**changes):
    goal,plan,_,_=await draft(client,identity)
    body={'template_plan_id':plan['plan_id'],'goal_id':goal['id'],'goal_version':goal['version'],
        'mode':'once','timezone':'Asia/Ho_Chi_Minh','once_at':(now()+timedelta(minutes=2)).isoformat(),
        'max_iterations':2,'max_cost_microusd':10,'max_elapsed_seconds':300,
        'cost_ceiling_microusd':5,'max_duration_seconds':60,
        'success_criteria':[{'field':'text','rule':'non_empty','value':None}],**changes}
    return goal,plan,body

async def create(client,identity,body,key=None):
    response=await client.post(BASE+'/preview',params={'workspace_id':identity['workspace']},headers=identity['owner'],json=body)
    assert response.status_code==200,response.text
    payload={**body,'workspace_id':identity['workspace'],'request_key':key or str(uuid4()),'confirmation_hash':response.json()['confirmation_hash']}
    response=await client.post(BASE,headers=identity['owner'],json=payload)
    assert response.status_code==201,response.text
    return response.json(),payload

async def control(client,identity,row,action):
    response=await client.post(BASE+'/'+row['id']+'/control',headers=identity['owner'],json={
        'version':row['version'],'request_key':str(uuid4()),'action':action})
    assert response.status_code==200,response.text;return response.json()

async def counts():
    async with Session() as db:return [await db.scalar(select(func.count()).select_from(c)) for c in
        (StudioSchedule,GoalScheduleSlot,GoalExecution,GoalCommand,StudioExecution,TaskAttempt)]

async def test_goal_schedule_crud_scoped_idempotent_separate_routes(client,identity,schedule_gates):
    goal,_,body=await template(client,identity);row,payload=await create(client,identity,body)
    assert row['status']=='disabled' and row['spec']['goal_source']['id']==goal['id']
    assert await counts()==[1,0,0,0,0,0]
    r=await client.post(BASE,headers=identity['owner'],json=payload);assert r.status_code==201 and r.json()==row
    assert (await client.get(BASE+'/'+row['id'],headers=identity['other'])).status_code==200
    assert (await client.get(BASE+'/'+row['id'],headers=identity['outsider'])).status_code==404
    assert (await client.get(BASE+'/'+row['id'])).status_code==401
    assert (await client.get('/v1/schedules/workflows/'+row['id'],headers=identity['owner'])).status_code==404
    assert (await client.get('/v1/schedules/workflows',params={'workspace_id':identity['workspace']},headers=identity['owner'])).json()==[]
    assert len((await client.get(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'])).json())==1
    assert (await client.post(BASE,headers=identity['owner'],json={**payload,'max_iterations':3})).status_code==409
    assert (await client.post(BASE+'/'+row['id']+'/control',headers=identity['other'],json={
        'version':row['version'],'request_key':str(uuid4()),'action':'enable'})).status_code==403
    row=await control(client,identity,row,'enable');row=await control(client,identity,row,'disable')
    edit={**body,'request_key':str(uuid4()),'version':row['version'],'confirmation_hash':payload['confirmation_hash']}
    r=await client.patch(BASE+'/'+row['id'],headers=identity['owner'],json=edit);assert r.status_code==200,r.text
    assert (await control(client,identity,r.json(),'archive'))['status']=='archived'

async def test_concurrent_tick_atomic_admission_restart_and_no_auto_approval(client,identity,schedule_gates):
    _,_,body=await template(client,identity);row,_=await create(client,identity,body);await control(client,identity,row,'enable')
    stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)
    values=await asyncio.gather(*(dispatcher.dispatch_studio_schedules(stamp=stamp) for _ in range(3)))
    assert sum(v['admitted'] for v in values)==1 and await counts()==[1,1,1,1,0,0]
    async with Session() as db:
        saved=await db.scalar(select(GoalExecution));await verify_admission(db,saved);await runner.bound(db,saved)
        assert saved.envelope['policy']['max_cost_microusd']==10 and saved.envelope['policy']['max_iterations']==2
    env={**os.environ,'PAO_SLOT_STAMP':stamp.isoformat()}
    for k in ('studio_schedule_manager_enabled','studio_schedule_dispatch_enabled','studio_enabled','workflow_planning_enabled',
        'workflow_durable_enabled','workflow_dispatch_enabled','workflow_worker_enabled','temporal_enabled',
        'goal_admission_enabled','goal_iterations_enabled','goal_runner_enabled'):env[k.upper()]='true'
    code="""
import asyncio,json,os
from datetime import datetime
from pao.modules.schedules.dispatcher import dispatch_studio_schedules
from pao.db import engine
async def main():
    print(json.dumps(await dispatch_studio_schedules(stamp=datetime.fromisoformat(os.environ['PAO_SLOT_STAMP']))));await engine.dispose()
asyncio.run(main())
"""
    p=await asyncio.create_subprocess_exec(sys.executable,'-c',code,env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:out,err=await asyncio.wait_for(p.communicate(),20)
    except asyncio.TimeoutError:p.kill();await p.communicate();raise
    assert p.returncode==0,err.decode();assert json.loads(out)['admitted']==0
    assert await counts()==[1,1,1,1,0,0]
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text('DELETE FROM goal_schedule_slots'))

@pytest.mark.parametrize('fault',['goal_version','source_text','permission','due_at','binding'])
async def test_pin_permission_deadline_fail_closed(client,identity,schedule_gates,monkeypatch,fault):
    goal,_,body=await template(client,identity);row,_=await create(client,identity,body);await control(client,identity,row,'enable')
    async with Session.begin() as db:
        g=await db.get(Goal,goal['id'])
        if fault=='goal_version':g.version+=1
        elif fault=='source_text':g.title='Changed outside runner'
        elif fault=='due_at':g.due_at=now()-timedelta(seconds=1)
        elif fault=='permission':(await db.get(Member,{'workspace_id':identity['workspace'],'user_id':identity['user_id']})).role='operator'
    if fault=='binding':monkeypatch.setattr(dispatcher,'execution_binding',lambda:{'sha256':'f'*64})
    assert (await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)))['errors']==1
    assert await counts()==[1,0,0,0,0,0]
    async with Session() as db:
        s=await db.get(StudioSchedule,row['id']);await store.verify(db,s);assert s.status=='manual_review'

async def test_runner_gate_rollback_does_not_block_workflow_or_cancel(client,identity,schedule_gates):
    _,_,body=await template(client,identity);row,_=await create(client,identity,body);row=await control(client,identity,row,'enable')
    settings().goal_runner_enabled=False
    assert (await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)))['checked']==0
    assert await counts()==[1,0,0,0,0,0]
    # Ten gated Goal records must not fill the shared owner's batch and
    # starve an otherwise-ready Studio workflow schedule.
    for _ in range(9):
        extra,_=await create(client,identity,body);await control(client,identity,extra,'enable')
    from test_studio_schedules import create as wf_create,control as wf_control
    wf_spec={k:v for k,v in body.items() if k in store.ScheduleSpec.model_fields}
    preview=await client.post('/v1/schedules/workflows/preview',params={'workspace_id':identity['workspace']},headers=identity['owner'],json=wf_spec)
    assert preview.status_code==200,preview.text
    wf_body={**wf_spec,'workspace_id':identity['workspace'],'request_key':str(uuid4()),'confirmation_hash':preview.json()['confirmation_hash']}
    wf=await wf_create(client,identity,wf_body);await wf_control(client,identity,wf,'enable')
    report=await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1))
    assert report=={'admitted':1,'checked':1,'errors':0}
    assert await counts()==[11,0,0,0,1,0]
    settings().studio_schedule_manager_enabled=False
    assert (await control(client,identity,row,'disable'))['status']=='disabled'

async def test_cross_schedule_busy_goal_is_not_overlapped(client,identity,schedule_gates):
    _,_,body=await template(client,identity);first,_=await create(client,identity,body);await control(client,identity,first,'enable')
    second,_=await create(client,identity,body);await control(client,identity,second,'enable')
    report=await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1))
    assert report['admitted']==1 and report['checked']==2 and report['errors']==0
    assert await counts()==[2,1,1,1,0,0]

async def test_goal_cron_coalesces_backlog_and_skips_busy_parent(client,identity,schedule_gates):
    _,_,body=await template(client,identity,mode='cron',cron='*/5 * * * *',once_at=None)
    row,_=await create(client,identity,body);row=await control(client,identity,row,'enable')
    stamp=store.timestamp(row['cursor_at'])+timedelta(minutes=16)
    assert (await dispatcher.dispatch_studio_schedules(stamp=stamp))['admitted']==1
    assert (await dispatcher.dispatch_studio_schedules(stamp=stamp+timedelta(minutes=16)))['admitted']==0
    assert await counts()==[1,1,1,1,0,0]
    read=(await client.get(BASE+'/'+row['id'],headers=identity['owner'])).json()
    assert read['status']=='enabled' and read['events'][0]['data']['details']['busy'] is True
    assert read['events'][0]['data']['details']['skipped']>=3

async def test_failure_after_goal_admission_rolls_back_slot_plan_commands(client,identity,schedule_gates,monkeypatch):
    _,_,body=await template(client,identity);row,_=await create(client,identity,body);await control(client,identity,row,'enable')
    original=goals.ledger.admit
    async def fail(*args,**kwargs):await original(*args,**kwargs);store.reject('fixture_after_goal_admission',409)
    monkeypatch.setattr(goals.ledger,'admit',fail)
    assert (await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)))['errors']==1
    assert await counts()==[1,0,0,0,0,0]
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(GoalEvent))==0

async def test_scheduled_parent_cancel_after_disable_and_gate_rollback(client,identity,schedule_gates,temporal,monkeypatch):
    _,_,body=await template(client,identity);row,_=await create(client,identity,body);row=await control(client,identity,row,'enable')
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1))
            async with Session() as db:slot=await db.scalar(select(GoalScheduleSlot))
            view={'execution_id':slot.execution_id};await wait(client,identity,view,'waiting_approval')
            row=(await client.get(BASE+'/'+row['id'],headers=identity['owner'])).json()
            assert (await control(client,identity,row,'disable'))['status']=='disabled'
            settings().studio_schedule_manager_enabled=False;settings().studio_schedule_dispatch_enabled=False
            settings().goal_runner_enabled=False;settings().goal_admission_enabled=False
            response=await client.post('/v1/goal-executions/'+slot.execution_id+'/cancel',headers=identity['owner'],json={'request_key':str(uuid4())})
            assert response.status_code==200,response.text
            await wait(client,identity,view,'cancelled')
            handle=env.client.get_workflow_handle('p63-'+slot.execution_id)
            assert (await asyncio.wait_for(handle.result(),15))['status']=='cancelled'
            await Replayer(workflows=[PaoGoalRunnerWorkflow]).replay_workflow(await handle.fetch_history())
    assert await counts()==[1,1,1,2,0,0]

@pytest.mark.parametrize('changes',[{'max_iterations':True},{'goal_version':2},{'max_cost_microusd':1},
    {'max_duration_seconds':121},{'success_criteria':[{'field':'text','rule':'python','value':'pass'}]},
    {'success_criteria':[{'field':'text','rule':'equals','value':'ignore previous instructions'}]},
    {'timeout_seconds':10},{'runner_profile':'untrusted'}])
async def test_invalid_goal_schedule_never_admitted(client,identity,schedule_gates,changes):
    _,_,body=await template(client,identity,**changes)
    r=await client.post(BASE+'/preview',params={'workspace_id':identity['workspace']},headers=identity['owner'],json=body)
    assert r.status_code in (409,422),r.text
    assert await counts()==[0]*6

async def test_scheduled_goal_real_parent_child_arq_approval_receipt_replay(client,identity,schedule_gates,temporal,monkeypatch):
    goal,template_plan,body=await template(client,identity);row,_=await create(client,identity,body);await control(client,identity,row,'enable')
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            assert (await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)))['admitted']==1
            async with Session() as db:slot=await db.scalar(select(GoalScheduleSlot));execution=await db.get(GoalExecution,slot.execution_id)
            view={'execution_id':execution.id};await wait(client,identity,view,'waiting_approval')
            async with Session() as db:assert await db.scalar(select(func.count()).select_from(StudioExecution))==0
            await approve(client,identity,view)
            assert execution.initial_plan_id!=template_plan['plan_id']
            await approve_steps(client,identity,execution.initial_plan_id)
            result=await wait(client,identity,view,'completed');assert result['state']['iteration']==1
            handle=env.client.get_workflow_handle('p63-'+execution.id)
            assert (await asyncio.wait_for(handle.result(),15))['status']=='completed'
            await Replayer(workflows=[PaoGoalRunnerWorkflow]).replay_workflow(await handle.fetch_history())
            await Replayer(workflows=[PaoPlannedDryRunWorkflow]).replay_workflow(
                await env.client.get_workflow_handle('p62-'+execution.initial_plan_id).fetch_history())
    async with Session() as db:
        saved=await db.get(GoalExecution,execution.id);await verify_admission(db,saved)
        assert (await runner.reconstruct(db,saved)).snapshot()['iteration']==1
        assert (await db.get(Goal,goal['id'])).status=='draft'
        assert await db.scalar(select(func.count()).select_from(TaskAttempt))==2
        assert await db.scalar(select(func.count()).select_from(Run))==0
        await store.verify(db,await db.get(StudioSchedule,row['id']))
