"""Persisted schedules/slot atomicity. Real PostgreSQL, fixed Echo only."""
import asyncio
import json,os,sys
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session,engine
from pao.models import StudioSchedule,StudioScheduleEvent,StudioScheduleSlot,StudioExecution,StudioCommand,Member,now
from pao.modules.schedules import store,dispatcher
from test_durable_admission import plan,gates
from test_goal_temporal_kernel import temporal
from test_goal_runner import stack,approve_steps
from temporalio.worker import Replayer
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow
from pao.models import TaskAttempt,Run

BASE='/v1/schedules/workflows'

@pytest.fixture
def schedule_gates(monkeypatch,gates):
    for key in ('studio_schedule_manager_enabled','studio_schedule_dispatch_enabled','workflow_worker_enabled'):
        monkeypatch.setattr(settings(),key,True)

async def draft(client,identity,**changes):
    p=await plan(client,identity)
    body={'template_plan_id':p['plan_id'],'mode':'once','timezone':'Asia/Ho_Chi_Minh',
        'once_at':(now()+timedelta(minutes=2)).isoformat(),**changes}
    r=await client.post(BASE+'/preview',params={'workspace_id':identity['workspace']},headers=identity['owner'],json=body)
    assert r.status_code==200,r.text
    payload={**body,'workspace_id':identity['workspace'],'request_key':str(uuid4()),'confirmation_hash':r.json()['confirmation_hash']}
    return p,payload

async def create(client,identity,body):
    r=await client.post(BASE,headers=identity['owner'],json=body)
    assert r.status_code==201,r.text;return r.json()

async def control(client,identity,row,action,**changes):
    body={'request_key':str(uuid4()),'version':row['version'],'action':action,**changes}
    r=await client.post(BASE+'/'+row['id']+'/control',headers=identity['owner'],json=body)
    assert r.status_code==200,r.text;return r.json(),body

async def counts():
    async with Session() as db:
        return [await db.scalar(select(func.count()).select_from(c)) for c in (StudioSchedule,StudioScheduleSlot,StudioExecution)]

async def test_create_disabled_concurrent_idempotent_and_scoped(client,identity,schedule_gates):
    p,body=await draft(client,identity)
    rows=await asyncio.gather(*(create(client,identity,body) for _ in range(2)))
    assert rows[0]==rows[1] and rows[0]['status']=='disabled'
    assert await counts()==[1,0,0]
    assert (await client.post(BASE,headers=identity['owner'],json={**body,'confirmation_hash':'f'*64})).status_code==409
    ident=rows[0]['id']
    assert (await client.get(BASE+'/'+ident,headers=identity['other'])).status_code==200
    assert (await client.get(BASE+'/'+ident,headers=identity['outsider'])).status_code==404
    assert (await client.post(BASE+'/'+ident+'/control',headers=identity['other'],json={
        'request_key':str(uuid4()),'version':1,'action':'enable'})).status_code==403
    assert (await client.get(BASE,params={'workspace_id':identity['workspace']})).status_code==401

async def test_control_edit_archive_and_gate_rollback(client,identity,schedule_gates):
    _,body=await draft(client,identity);row=await create(client,identity,body)
    row,key=await control(client,identity,row,'enable')
    replay=await client.post(BASE+'/'+row['id']+'/control',headers=identity['owner'],json=key)
    assert replay.status_code==200 and replay.json()['version']==row['version']
    payload={**body,'version':row['version'],'request_key':str(uuid4())};payload.pop('workspace_id')
    assert (await client.patch(BASE+'/'+row['id'],headers=identity['owner'],json=payload)).status_code==409
    settings().studio_schedule_manager_enabled=False
    row,_=await control(client,identity,row,'disable')
    assert await dispatcher.dispatch_studio_schedules(stamp=now()+timedelta(minutes=3))=={'admitted':0,'checked':0,'errors':0}
    settings().studio_schedule_manager_enabled=True
    payload['version']=row['version']
    r=await client.patch(BASE+'/'+row['id'],headers=identity['owner'],json=payload)
    assert r.status_code==200 and r.json()['status']=='disabled'
    row,_=await control(client,identity,r.json(),'archive')
    assert (await client.post(BASE+'/'+row['id']+'/control',headers=identity['owner'],json={
        'request_key':str(uuid4()),'version':row['version'],'action':'enable'})).status_code==409
    assert await counts()==[1,0,0]

async def test_once_due_concurrent_tick_and_restart_dedup_native_start(client,identity,schedule_gates):
    _,body=await draft(client,identity);row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)
    results=await asyncio.gather(*(dispatcher.dispatch_studio_schedules(stamp=stamp) for _ in range(3)))
    assert sum(r['admitted'] for r in results)==1 and await counts()==[1,1,1]
    await engine.dispose()  # new DB connections; no in-memory cursor ownership
    assert (await dispatcher.dispatch_studio_schedules(stamp=stamp))['admitted']==0
    # A completely new interpreter must recover from the persisted ledger too.
    program="""
import asyncio,json
from datetime import datetime
from pao.config import settings
from pao.modules.schedules.dispatcher import dispatch_studio_schedules
from pao.db import engine
async def main():
    value=await dispatch_studio_schedules(stamp=datetime.fromisoformat(__import__('os').environ['PAO_SLOT_STAMP']))
    print(json.dumps(value));await engine.dispose()
asyncio.run(main())
"""
    env={**os.environ,'PAO_SLOT_STAMP':stamp.isoformat()}
    for key in ('studio_schedule_manager_enabled','studio_schedule_dispatch_enabled','studio_enabled',
        'workflow_planning_enabled','workflow_durable_enabled','temporal_enabled','workflow_dispatch_enabled','workflow_worker_enabled'):
        env[key.upper()]='true'
    process=await asyncio.create_subprocess_exec(sys.executable,'-c',program,env=env,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:output,error=await asyncio.wait_for(process.communicate(),20)
    except asyncio.TimeoutError:
        process.kill();await process.communicate();raise
    assert process.returncode==0,error.decode()
    assert json.loads(output)=={'admitted':0,'checked':0,'errors':0}
    assert await counts()==[1,1,1]
    async with Session() as db:
        saved=await db.get(StudioSchedule,row['id']);await store.verify(db,saved)
        assert saved.status=='completed'
        native=await db.scalar(select(StudioExecution))
        assert native.status=='starting' and all(s['approval_required'] for s in native.command['steps'])
        assert await db.scalar(select(func.count()).select_from(StudioCommand))==1
    # Immutable audit/slot identity prevents erase-and-replay after restart.
    for table in ('studio_schedule_slots','studio_schedule_events'):
        with pytest.raises(DBAPIError):
            async with Session.begin() as db:await db.execute(text('DELETE FROM '+table))

async def test_cron_coalesces_and_skips_busy_without_overlapping(client,identity,schedule_gates):
    _,body=await draft(client,identity,mode='cron',cron='*/5 * * * *',once_at=None)
    row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    stamp=store.timestamp(row['cursor_at'])+timedelta(minutes=16)
    assert (await dispatcher.dispatch_studio_schedules(stamp=stamp))['admitted']==1
    assert (await dispatcher.dispatch_studio_schedules(stamp=stamp+timedelta(minutes=16)))['admitted']==0
    assert await counts()==[1,1,1]
    async with Session() as db:
        last=await db.scalar(select(StudioScheduleEvent).order_by(StudioScheduleEvent.revision.desc()))
        assert last.data['details']['busy'] and last.data['details']['skipped']>=3

@pytest.mark.parametrize('fault',['permission','binding','gap'])
async def test_revocation_pin_and_long_recovery_fail_closed(client,identity,schedule_gates,monkeypatch,fault):
    _,body=await draft(client,identity);row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)
    if fault=='permission':
        async with Session.begin() as db:
            member=await db.get(Member,{'workspace_id':identity['workspace'],'user_id':identity['user_id']});member.role='operator'
    elif fault=='binding':monkeypatch.setattr(dispatcher,'execution_binding',lambda:{'sha256':'f'*64})
    else:stamp+=timedelta(days=8)
    assert (await dispatcher.dispatch_studio_schedules(stamp=stamp))['errors']==1
    assert await counts()==[1,0,0]
    async with Session() as db:
        saved=await db.get(StudioSchedule,row['id']);await store.verify(db,saved);assert saved.status=='manual_review'

async def test_tamper_is_not_whitelisted_by_dispatcher(client,identity,schedule_gates):
    _,body=await draft(client,identity);row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    async with Session.begin() as db:
        saved=await db.get(StudioSchedule,row['id']);saved.spec_hash='f'*64
    assert (await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)))['errors']==1
    assert (await client.get(BASE+'/'+row['id'],headers=identity['owner'])).status_code==409
    assert await counts()==[1,0,0]

async def test_sparse_once_after_twenty_days_is_not_an_offline_gap(client,identity,schedule_gates):
    _,body=await draft(client,identity,once_at=(now()+timedelta(days=20)).isoformat())
    row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    result=await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1))
    assert result['admitted']==1 and result['errors']==0
    assert await counts()==[1,1,1]

async def test_disabled_schedule_does_not_backfill_or_reenable_expired_once(client,identity,schedule_gates,monkeypatch):
    _,body=await draft(client,identity);row=await create(client,identity,body)
    later=store.timestamp(body['once_at'])+timedelta(seconds=1)
    assert (await dispatcher.dispatch_studio_schedules(stamp=later))['admitted']==0
    monkeypatch.setattr(store,'now',lambda:later)
    r=await client.post(BASE+'/'+row['id']+'/control',headers=identity['owner'],json={
        'request_key':str(uuid4()),'version':row['version'],'action':'enable'})
    assert r.status_code==409 and await counts()==[1,0,0]

async def test_dispatch_failure_rolls_back_plan_tasks_and_slot(client,identity,schedule_gates,monkeypatch):
    _,body=await draft(client,identity);row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    original=dispatcher.durable.admit
    async def fail_after_creating_native(*args,**kwargs):
        await original(*args,**kwargs)
        store.reject('fixture_after_native_failure',409)
    monkeypatch.setattr(dispatcher.durable,'admit',fail_after_creating_native)
    result=await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1))
    assert result['errors']==1 and await counts()==[1,0,0]
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(StudioCommand))==0
        saved=await db.get(StudioSchedule,row['id']);await store.verify(db,saved)
        assert saved.status=='manual_review'

@pytest.mark.parametrize('changes',[{'timezone':'Invalid/Zone'},{'cron':'@reboot','mode':'cron','once_at':None},
    {'once_at':'2020-01-01T00:00:00Z'},{'once_at':'2026-10-11T00:00:00'}, {'timeout_seconds':True}])
async def test_invalid_policy_never_stores_or_runs(client,identity,schedule_gates,changes):
    p=await plan(client,identity)
    body={'template_plan_id':p['plan_id'],'mode':'once','timezone':'UTC','once_at':(now()+timedelta(minutes=2)).isoformat(),**changes}
    r=await client.post(BASE+'/preview',params={'workspace_id':identity['workspace']},headers=identity['owner'],json=body)
    assert r.status_code==422 and await counts()==[0,0,0]

async def test_due_schedule_actual_temporal_arq_receipts_and_replay(client,identity,schedule_gates,temporal,monkeypatch):
    _,body=await draft(client,identity);row=await create(client,identity,body);row,_=await control(client,identity,row,'enable')
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            assert (await dispatcher.dispatch_studio_schedules(stamp=store.timestamp(body['once_at'])+timedelta(seconds=1)))['admitted']==1
            async with Session() as db:slot=await db.scalar(select(StudioScheduleSlot))
            # Never auto-approve: the actual child must wait before any attempts.
            for _ in range(100):
                async with Session() as db:native=await db.get(StudioExecution,slot.execution_id)
                if native.status=='waiting_approval':break
                await asyncio.sleep(.1)
            assert native.status=='waiting_approval'
            async with Session() as db:assert await db.scalar(select(func.count()).select_from(TaskAttempt))==0
            await approve_steps(client,identity,slot.execution_id)
            handle=env.client.get_workflow_handle('p62-'+slot.execution_id)
            assert (await asyncio.wait_for(handle.result(),15))['status']=='completed'
            await Replayer(workflows=[PaoPlannedDryRunWorkflow]).replay_workflow(await handle.fetch_history())
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TaskAttempt))==2
        assert await db.scalar(select(func.count()).select_from(Run))==0
        await store.verify(db,await db.get(StudioSchedule,row['id']))
