"""S5 source->plan->native Run->draft review->simulated action->report gates."""
import asyncio,json
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import (BusinessJob,BusinessPlanEvent,Task,TaskAttempt,Run,Member,Workspace,now)
from pao.gateway import Chunk
from pao.runtime import execute_run
from pao.modules.business_planning import jobs
from test_business_plan_review import approved,material
from test_business_planning import base
from test_studio import make,publish

SCHEMA={'type':'object','properties':{'text':{'type':'string','maxLength':4096}},'required':['text'],'additionalProperties':False}


@pytest.fixture
def operational(monkeypatch,accounted_runs):
    monkeypatch.setattr(settings(),'business_planning_enabled',True)
    monkeypatch.setattr(settings(),'studio_enabled',True)
    async def local():return ['fixture-a','fixture-b']
    monkeypatch.setattr('pao.modules.engines.service.local_models',local)


async def setup(client,c,agent_payload=None):
    agent=await publish(client,c,await make(client,c,payload=agent_payload or {'instruction':'Write a factual draft. State missing data; never invent facts.'}))
    skill=await publish(client,c,await make(client,c,'skills','business-draft',{
        'instruction':'Return a draft text for owner review. No verified evidence or external actions.',
        'agent_version_id':agent['version']['id'],'input_schema':SCHEMA,'output_schema':SCHEMA,'exit_criteria':['non_empty:text']}))
    config={'targets':[{'key':'a','provider':'ollama','model':'fixture-a'},{'key':'b','provider':'ollama','model':'fixture-b'}],
        'default_target':'a','specialists':[{'kind':kind,'skill_version_id':skill['version']['id']} for kind in ('analyst','content')]}
    saved=await client.put(base(c)+'/routing',headers=c['owner'],json={'expected_revision':0,'request_key':str(uuid4()),'content':config})
    assert saved.status_code==200,saved.text
    path,plan,review,body=await approved(client,c)
    admitted=await client.post(path+'/materialize',headers=c['owner'],json=material(plan,review));assert admitted.status_code==200,admitted.text
    return path,plan,config,admitted.json()


def start_body(item='research',**change):
    return {'request_key':str(uuid4()),'routing_revision':1,'plan_revision':1,'item_key':item,'confirm_model_call':True,**change}


class Fake:
    provider_name='ollama'
    def __init__(self,model='fixture-a',hook=None):self.model_name=model;self.calls=0;self.hook=hook
    async def stream(self,messages,max_tokens=None):
        self.calls+=1
        if self.hook:await self.hook()
        yield Chunk(text=json.dumps({'text':'Bản nháp thử nghiệm. Chưa có số liệu doanh thu hoặc ưu đãi.'},ensure_ascii=False),
            usage={'input_tokens':300,'output_tokens':40})


async def start(client,c,path,body=None):
    response=await client.post(path+'/jobs',headers=c['owner'],json=body or start_body())
    assert response.status_code==202,response.text
    return response.json()


async def run_job(client,c,row,fake=None):
    fake=fake or Fake(row['model']);await execute_run({'gateway':fake},row['run_id'])
    response=await client.get(base(c)+'/jobs/'+row['id'],headers=c['owner']);assert response.status_code==200,response.text
    value=response.json();assert value['status']=='completed',value
    return value,fake


async def review_content(client,c,row,decision='approve'):
    response=await client.post(base(c)+'/jobs/'+row['id']+'/review',headers=c['owner'],json={
        'request_key':str(uuid4()),'decision':decision,'artifact_hash':row['artifact_hash'],'confirm_review':True})
    assert response.status_code==200,response.text
    return response.json()


async def budget(client,c,path,**changes):
    body={'request_key':str(uuid4()),'plan_revision':1,'account_id':'mock:account','campaign_id':'mock:campaign','currency':'VND',
        'cap':'1000','headroom':'100','opening_spent':'100','observed_at':now().isoformat(),'max_age_seconds':3600,'confirm_simulation':True,**changes}
    response=await client.post(path+'/budgets',headers=c['owner'],json=body)
    assert response.status_code==200,response.text
    return response.json(),body


async def action(client,c,job,wallet,amount='500'):
    body={'request_key':str(uuid4()),'job_id':job['id'],'budget_id':wallet['id'],'kind':'mock_ads_budget','amount':amount,
        'artifact_hash':job['artifact_hash'],'confirm_simulation':True}
    response=await client.post(base(c)+'/actions',headers=c['owner'],json=body)
    return response,body


async def action_review(client,c,row,decision='approve'):
    response=await client.post(base(c)+'/actions/'+row['id']+'/review',headers=c['owner'],json={
        'request_key':str(uuid4()),'decision':decision,'confirm_simulation':True})
    assert response.status_code==200,response.text


async def test_native_two_steps_two_models_review_and_no_second_runner(client,identity,operational):
    c=identity;path,plan,config,materialized=await setup(client,c)
    early=await client.post(path+'/jobs',headers=c['owner'],json=start_body('content',job={'target':'b'}));assert early.status_code==403
    body=start_body();first=await start(client,c,path,body)
    again=await start(client,c,path,body);assert again['id']==first['id']
    first,fake=await run_job(client,c,first);assert fake.calls==1
    await review_content(client,c,first)
    second=await start(client,c,path,start_body('content',job={'target':'b'}));second,fake=await run_job(client,c,second)
    assert second['model']=='fixture-b' and fake.calls==1
    await review_content(client,c,second)
    async with Session() as db:
        tasks=list(await db.scalars(select(Task).where(Task.goal_id==materialized['goal_id'])))
        assert all(t.status=='completed' and t.progress==100 and t.run_id for t in tasks)
        assert await db.scalar(text('SELECT count(*) FROM business_jobs'))==2
        assert await db.scalar(text('SELECT count(*) FROM task_attempts'))==2
        assert await db.scalar(text('SELECT count(*) FROM llm_attempts'))==2
        assert await db.scalar(text('SELECT count(*) FROM tool_calls'))==0


@pytest.mark.parametrize('cause',['stop','profile','plan','actor','cancel'])
async def test_queued_rechecks_before_local_provider_call(client,identity,operational,cause):
    c=identity;path,plan,config,_=await setup(client,c);row=await start(client,c,path)
    if cause=='stop':
        assert (await client.post(base(c)+'/control',headers=c['owner'],json={'request_key':str(uuid4()),'stopped':True,'confirm':True})).status_code==200
    if cause=='cancel':
        assert (await client.post(base(c)+'/jobs/'+row['id']+'/cancel',headers=c['owner'],json={'request_key':str(uuid4())})).status_code==200
    if cause=='actor':
        async with Session.begin() as db:(await db.get(Member,(c['workspace'],c['user_id']))).role='viewer'
    if cause in ('profile','plan'):
        if cause=='profile':
            content=(await client.get(base(c)+'/profile',headers=c['owner'])).json()['item']['content'];content['brand_voice']='Changed'
            response=await client.put(base(c)+'/profile',headers=c['owner'],json={'expected_revision':1,'request_key':str(uuid4()),'content':content})
        else:
            response=await client.put(path,headers=c['owner'],json={'expected_revision':1,'request_key':str(uuid4()),
                'profile_id':plan['profile_id'],'profile_revision':1,'content':{**plan['content'],'title':'Changed'}})
        assert response.status_code==200,response.text
    fake=Fake();await execute_run({'gateway':fake},row['run_id']);assert fake.calls==0
    async with Session() as db:assert (await db.get(Run,row['run_id'])).status in ('failed','cancelled')


async def test_stop_during_generation_denies_publication(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path)
    async def stop():
        response=await client.post(base(c)+'/control',headers=c['owner'],json={'request_key':str(uuid4()),'stopped':True,'confirm':True});assert response.status_code==200
    fake=Fake(hook=stop);await execute_run({'gateway':fake},row['run_id'])
    async with Session() as db:
        run=await db.get(Run,row['run_id']);assert run.status=='failed' and not run.response


async def test_routing_edit_does_not_repin_queued_job(client,identity,operational):
    c=identity;path,_,config,_=await setup(client,c);row=await start(client,c,path)
    config['default_target']='b'
    assert (await client.put(base(c)+'/routing',headers=c['owner'],json={'expected_revision':1,'request_key':str(uuid4()),'content':config})).status_code==200
    completed,_=await run_job(client,c,row)
    assert completed['model']=='fixture-a' and completed['routing_revision']==1


async def test_full_simulation_unknown_reservation_reconciliation_and_report(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row,_=await run_job(client,c,await start(client,c,path));await review_content(client,c,row)
    wallet,_=await budget(client,c,path);response,body=await action(client,c,row,wallet);assert response.status_code==200,response.text
    proposal=response.json()
    assert (await client.post(base(c)+'/actions',headers=c['owner'],json=body)).json()['id']==proposal['id']
    route=base(c)+'/actions/'+proposal['id']
    simulate={'request_key':str(uuid4()),'outcome':'unknown','confirm_simulation':True}
    assert (await client.post(route+'/simulate',headers=c['owner'],json=simulate)).status_code==403
    await action_review(client,c,proposal)
    unknown=await client.post(route+'/simulate',headers=c['owner'],json=simulate);assert unknown.status_code==200,unknown.text
    assert unknown.json()['status']=='unknown'
    assert (await client.post(route+'/simulate',headers=c['owner'],json=simulate)).status_code==200
    state=(await client.get(path+'/operations',headers=c['owner'])).json();assert state['budgets'][0]['reserved_minor']==500
    assert state['budgets'][0]['available_minor']==300
    reconciliation={'request_key':str(uuid4()),'outcome':'failure','note':'Đối soát mô phỏng, không có thao tác bên ngoài','confirm_simulation':True}
    fixed=await client.post(route+'/reconcile',headers=c['owner'],json=reconciliation);assert fixed.status_code==200,fixed.text
    assert (await client.post(route+'/reconcile',headers=c['owner'],json=reconciliation)).status_code==200
    state=(await client.get(path+'/operations',headers=c['owner'])).json();assert state['budgets'][0]['reserved_minor']==0
    assert state['budgets'][0]['available_minor']==800
    report=await client.post(path+'/reports',headers=c['owner'],json={'request_key':str(uuid4()),'window_from':(now()-timedelta(days=1)).isoformat(),'window_to':now().isoformat()})
    assert report.status_code==200,report.text
    value=report.json()['report'];assert value['model_usage']['input_tokens']==300
    assert value['kpis'][0]['measured'] is None and value['external_delivery'] is False
    assert value['source_pins']['native_job_ids']==[row['id']]


async def test_reservation_race_one_winner_and_no_overspend(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row,_=await run_job(client,c,await start(client,c,path));await review_content(client,c,row)
    wallet,_=await budget(client,c,path)
    results=await asyncio.gather(action(client,c,row,wallet,'600'),action(client,c,row,wallet,'600'))
    assert sorted(response.status_code for response,_ in results)==[200,409]
    state=(await client.get(path+'/operations',headers=c['owner'])).json();assert state['budgets'][0]['reserved_minor']==600


async def test_rejection_releases_and_approval_types_not_interchangeable(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row,_=await run_job(client,c,await start(client,c,path));wallet,_=await budget(client,c,path)
    response,_=await action(client,c,row,wallet);assert response.status_code==403
    await review_content(client,c,row);response,_=await action(client,c,row,wallet);assert response.status_code==200
    await action_review(client,c,response.json(),'reject')
    state=(await client.get(path+'/operations',headers=c['owner'])).json();assert state['budgets'][0]['reserved_minor']==0
    assert state['budgets'][0]['released_minor']==500


async def test_receipts_and_money_immutable_and_session_no_manual_retry(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path)
    async with Session() as db:
        job=await db.get(BusinessJob,row['id']);run=await db.get(Run,row['run_id']);sid=run.session_id
        for sql in ('UPDATE business_jobs SET selection_hash=repeat(\'0\',64)','DELETE FROM business_jobs'):
            with pytest.raises(DBAPIError):await db.execute(text(sql))
            await db.rollback()
    response=await client.post('/v1/runs',headers=c['owner'],json={'session_id':sid,'message':'Manual bypass','request_key':str(uuid4())})
    assert response.status_code==409


async def test_report_schedule_single_owner_and_slot_dedupe(client,identity,operational):
    c=identity;path,*_=await setup(client,c)
    response=await client.post(path+'/report-schedule',headers=c['owner'],json={'request_key':str(uuid4()),'enabled':True,'cadence':'hourly','confirm_internal_only':True})
    assert response.status_code==200,response.text
    from pao.modules.schedules.dispatcher import dispatch_studio_schedules
    stamp=now()+timedelta(hours=2)
    await dispatch_studio_schedules(stamp=stamp);await dispatch_studio_schedules(stamp=stamp)
    state=(await client.get(path+'/operations',headers=c['owner'])).json()
    assert len(state['reports'])==1,state
    assert state['schedule']['owner']=='runtime.dispatch_studio_schedules.v1'


async def test_other_sme_and_admin_not_financial_approver(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row,_=await run_job(client,c,await start(client,c,path))
    async with Session.begin() as db:
        second=Workspace(name='Other SME');db.add(second);await db.flush();db.add(Member(workspace_id=second.id,user_id=c['user_id'],role='owner'))
    assert (await client.get(base(c).replace(c['workspace'],second.id)+'/jobs/'+row['id'],headers=c['owner'])).status_code==404
    async with Session.begin() as db:(await db.get(Member,(c['workspace'],c['user_id']))).role='admin'
    response=await client.post(base(c)+'/jobs/'+row['id']+'/review',headers=c['owner'],json={'request_key':str(uuid4()),'decision':'approve','artifact_hash':row['artifact_hash'],'confirm_review':True})
    assert response.status_code==403


@pytest.mark.parametrize('cancelled',[False,True])
async def test_actual_arq_outbox_and_cancel(client,identity,operational,cancelled):
    from arq import create_pool
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix
    from pao.runtime import dispatch
    import signal
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path)
    if cancelled:
        assert (await client.post(base(c)+'/jobs/'+row['id']+'/cancel',headers=c['owner'],json={'request_key':str(uuid4())})).status_code==200
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:s5:'+uuid4().hex;redis=await create_pool(config,default_queue_name=queue);runner=None;fake=Fake()
    class Workers:
        functions=[execute_run]
        redis_settings=config
        queue_name=queue
        handle_signals=False
        burst=True
        max_jobs=max_burst_jobs=1
        keep_result=0
        poll_delay=.05
        job_timeout=20
    try:
        await dispatch({'redis':redis})
        assert await redis.exists(job_key_prefix+'run:'+row['run_id'])
        runner=create_worker(Workers,ctx={'gateway':fake});await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==1 and runner.jobs_failed==0
        async with Session() as db:
            run=await db.get(Run,row['run_id']);assert run.status==('cancelled' if cancelled else 'completed')
        assert fake.calls==(0 if cancelled else 1)
    finally:
        if runner:
            if not hasattr(signal,'SIGUSR1'):runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
            await runner.close()
        await redis.delete(queue,*(prefix+'run:'+row['run_id'] for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()


async def test_quota_denied_before_provider_and_worker_interruption_no_retry(client,identity,operational):
    from pao.models import TenantResourcePolicy
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path)
    async with Session.begin() as db:db.add(TenantResourcePolicy(workspace_id=c['workspace'],daily_model_calls=1,daily_model_tokens=1,concurrent_models=1,updated_by=c['user_id']))
    fake=Fake();await execute_run({'gateway':fake},row['run_id']);assert fake.calls==0
    async with Session() as db:assert (await db.get(Run,row['run_id'])).status=='failed'


async def test_stop_resume_never_revives_old_queued_admission(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path)
    for value in (True,False):
        assert (await client.post(base(c)+'/control',headers=c['owner'],json={'request_key':str(uuid4()),'stopped':value,'confirm':True})).status_code==200
    fake=Fake();await execute_run({'gateway':fake},row['run_id']);assert fake.calls==0


@pytest.mark.parametrize('currency,value,valid',[('VND','1.01',False),('JPY','1.1',False),('USD','1.01',True),('USD','1.001',False)])
def test_minor_unit_precision(currency,value,valid):
    from pao.modules.business_planning.money import minor
    from fastapi import HTTPException
    if valid:assert minor(value,currency)==101
    else:
        with pytest.raises(HTTPException):minor(value,currency)


async def test_per_job_timeout_is_enforced(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path,start_body(job={'timeout_seconds':1}))
    async def slow():await asyncio.sleep(2)
    await execute_run({'gateway':Fake(hook=slow)},row['run_id'])
    async with Session() as db:
        run=await db.get(Run,row['run_id']);assert run.status=='failed' and run.error_code=='studio_deadline_exceeded'


async def test_unknown_cannot_be_abandoned_or_reexecuted_and_stop_allows_reconciliation(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row,_=await run_job(client,c,await start(client,c,path));await review_content(client,c,row)
    wallet,_=await budget(client,c,path);response,_=await action(client,c,row,wallet);proposal=response.json();route=base(c)+'/actions/'+proposal['id']
    await action_review(client,c,proposal)
    unknown={'request_key':str(uuid4()),'outcome':'unknown','confirm_simulation':True}
    assert (await client.post(route+'/simulate',headers=c['owner'],json=unknown)).status_code==200
    assert (await client.post(route+'/cancel',headers=c['owner'],json={'request_key':str(uuid4()),'confirm_simulation':True})).status_code==409
    assert (await client.post(route+'/simulate',headers=c['owner'],json={**unknown,'request_key':str(uuid4()),'outcome':'success'})).status_code==409
    assert (await client.post(base(c)+'/control',headers=c['owner'],json={'request_key':str(uuid4()),'stopped':True,'confirm':True})).status_code==200
    assert (await client.post(route+'/reconcile',headers=c['owner'],json={'request_key':str(uuid4()),'outcome':'success','note':'Đối soát mô phỏng đã hoàn tất, không thực hiện lại.','confirm_simulation':True})).status_code==200
    state=(await client.get(path+'/operations',headers=c['owner'])).json()
    assert state['budgets'][0]['reserved_minor']==0 and state['budgets'][0]['spent_minor']==600


async def test_abandon_before_execution_releases_exactly_once(client,identity,operational):
    c=identity;path,*_=await setup(client,c);row,_=await run_job(client,c,await start(client,c,path));await review_content(client,c,row)
    wallet,_=await budget(client,c,path);response,_=await action(client,c,row,wallet);proposal=response.json();route=base(c)+'/actions/'+proposal['id']
    await action_review(client,c,proposal)
    body={'request_key':str(uuid4()),'confirm_simulation':True}
    assert (await client.post(route+'/cancel',headers=c['owner'],json=body)).status_code==200
    assert (await client.post(route+'/cancel',headers=c['owner'],json=body)).status_code==200
    assert (await client.post(route+'/simulate',headers=c['owner'],json={'request_key':str(uuid4()),'outcome':'success','confirm_simulation':True})).status_code==409
    state=(await client.get(path+'/operations',headers=c['owner'])).json();assert state['budgets'][0]['released_minor']==500


async def test_budget_stale_and_currency_fail_closed(client,identity,operational):
    c=identity;path,*_=await setup(client,c)
    common={'request_key':str(uuid4()),'plan_revision':1,'account_id':'mock:account','campaign_id':'mock:campaign','currency':'VND',
        'cap':'1000','headroom':'100','opening_spent':'100','observed_at':(now()-timedelta(hours=2)).isoformat(),'max_age_seconds':3600,'confirm_simulation':True}
    assert (await client.post(path+'/budgets',headers=c['owner'],json=common)).status_code==422
    common.update(observed_at=now().isoformat(),currency='USD')
    assert (await client.post(path+'/budgets',headers=c['owner'],json=common)).status_code==422
    common.update(currency='VND',cap=1000.0)
    assert (await client.post(path+'/budgets',headers=c['owner'],json=common)).status_code==422


def test_worker_and_scheduler_can_import_before_http_router():
    import subprocess,sys
    from pao.config import ROOT
    for module in ('jobs','reports'):
        code=f"import pao.runtime; from pao.modules.business_planning import {module}; print('fresh-import-ok')"
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True,timeout=30)
        assert result.returncode==0 and 'fresh-import-ok' in result.stdout,result.stderr[-1000:]


async def test_changed_backend_binding_denies_queued_job(client,identity,operational,monkeypatch):
    c=identity;path,*_=await setup(client,c);row=await start(client,c,path)
    monkeypatch.setattr('pao.skills.execution_binding',lambda:{'policy':'exact-backend-source-v1','sha256':'0'*64})
    fake=Fake();await execute_run({'gateway':fake},row['run_id']);assert fake.calls==0
    async with Session() as db:assert (await db.get(Run,row['run_id'])).status=='failed'


async def test_private_dependency_cannot_escape_into_unscoped_child(client,identity,operational,monkeypatch):
    from pao.models import Brain
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    c=identity
    async with Session.begin() as db:
        brain=Brain(workspace_id=c['workspace'],owner_id=c['user_id'],name='Private business source')
        db.add(brain);await db.flush();bid=brain.id
    path,_,config,_=await setup(client,c,{'instruction':'Return factual draft.','brain_id':bid})
    agent=await publish(client,c,await make(client,c,'agents','public-child',{'instruction':'Return factual draft.'}))
    skill=await publish(client,c,await make(client,c,'skills','public-child-draft',{
        'instruction':'Return draft text.','agent_version_id':agent['version']['id'],
        'input_schema':SCHEMA,'output_schema':SCHEMA,'exit_criteria':['non_empty:text']}))
    config['specialists'][1]['skill_version_id']=skill['version']['id']
    response=await client.put(base(c)+'/routing',headers=c['owner'],json={
        'expected_revision':1,'request_key':str(uuid4()),'content':config})
    assert response.status_code==200,response.text
    parent=await start(client,c,path,start_body(routing_revision=2));parent,_=await run_job(client,c,parent)
    await review_content(client,c,parent)
    denied=await client.post(path+'/jobs',headers=c['owner'],json=start_body('content',routing_revision=2))
    assert denied.status_code==403 and 'business_job_dependency_brain_mismatch' in denied.text,denied.text
    async with Session() as db:assert await db.scalar(text('SELECT count(*) FROM business_jobs'))==1
