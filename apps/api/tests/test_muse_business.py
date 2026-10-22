"""Two dependent business jobs through the existing ARQ/Studio/Muse path."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import signal
from uuid import uuid4
from unittest.mock import AsyncMock

from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import BusinessJob,ChatSession,Goal,Project,Task,TaskAttempt,Run,LlmAttempt,ToolCall,Workspace,Member,now
from pao.modules.cli_connections import muse_client as native,muse_profile as profile,muse_execution as execution
from pao.modules.installation_ai.models import InstallationAIResource
from test_studio import make,publish
from test_business_operations import SCHEMA,start_body,review_content
from test_business_plan_review import approved,material
from test_business_planning import base


async def business_cycle(client,c,monkeypatch,tmp_path,*,live=False,provider_managed=False):
    state={'pass':False,'live_subscription':live,'requested_calls':[],'calls':[],
        'primary_data_sent':False,'primary_mutations':False,'quota_remaining':None,
        'API_fallback':False,'external_actions':False,'stages':[]}
    target=Path(os.environ['PAO_GD01_MUSE_LIVE_RECEIPT']) if live else tmp_path/'business-summary.json'
    redis=None;owned=[];queue='pao-test:muse-business:'+uuid4().hex
    try:
        for name in ('business_planning_enabled','studio_enabled','installation_ai_enabled',
                     'engine_contract_enabled','chat_features_enabled','agent_runtime_enabled'):
            monkeypatch.setattr(settings(),name,True)
        monkeypatch.setattr(settings(),'provider_managed_tokens',provider_managed)
        monkeypatch.setattr(settings(),'memory_enabled',False)
        monkeypatch.setattr(settings(),'installation_ai_manager_ids',[c['user_id']])
        monkeypatch.setattr(native,'STATE',tmp_path/'muse-business.json')
        if live:
            assert os.environ.get('PAO_GD01_MUSE_LIVE_APPROVED')=='two_synthetic_calls_no_fallback'
            monkeypatch.setattr(profile,'PROFILE',Path('F:/PAO-ACOS/.runtime/muse-profile'))
        else:
            data={'account_state':'accountLogin','models':[
                {'model':name,'display_name':name,'reasoning_efforts':['minimal','low'],
                 'default_effort':'low','provider_output_modalities':['text']}
                for name in ('muse-spark-1.3','muse-spark-1.2')],
                'observed_at':'2026-10-22T00:00:00+00:00','binary_version':native.VERSION,
                'binary_sha256':native.SHA,'schema_fingerprint':native.SCHEMA,'profile':'pao_isolated'}
            monkeypatch.setattr(native,'discover',AsyncMock(return_value=data))
        response=await client.post('/v1/muse-client',params={'workspace_id':c['workspace']},headers=c['owner'],
            json={'request_key':str(uuid4()),'expected_revision':0})
        assert response.status_code==200,response.text
        async with Session() as db:
            rid=(await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='muse'))).id
        actual=execution.execute
        async def send(messages,model,effort,authorize,**kwargs):
            assert len(state['requested_calls'])<2,'At most two synthetic calls; no hidden retries'
            assert (model,effort) in (('muse-spark-1.3','minimal'),('muse-spark-1.2','low'))
            state['requested_calls'].append({'model':model,'effort':effort})
            if live:return await actual(messages,model,effort,authorize,**kwargs)
            await authorize()
            if kwargs.get('lifecycle') is not None:
                kwargs['lifecycle'].update(resumed=True,cleanup_verified=True)
            return json.dumps({'text':'PAO_MUSE_BUSINESS_DRAFT'}),{'input_tokens':14000,'output_tokens':6000 if provider_managed else 40}
        monkeypatch.setattr(execution,'execute',send)
        agent=await publish(client,c,await make(client,c,slug='muse-business-agent',payload={
            'instruction':'Synthetic draft-only acceptance. No tools, files, outside actions or invented business facts.'}))
        skill=await publish(client,c,await make(client,c,'skills','muse-business-draft',{
            'instruction':'Connection test with synthetic data only. Return exactly the JSON object '
                '{"text":"PAO_MUSE_BUSINESS_DRAFT"}. No Markdown. Do not use tools or files.',
            'agent_version_id':agent['version']['id'],'input_schema':SCHEMA,'output_schema':SCHEMA,
            'token_budget':32768,'output_tokens':512,'timeout_seconds':120,'exit_criteria':['non_empty:text']}))
        config={'targets':[{'key':key,'provider':'muse','model':model,'reasoning_effort':effort,
            'installation_resource_id':rid} for key,model,effort in (
                ('research','muse-spark-1.3','minimal'),('content','muse-spark-1.2','low'))],
            'default_target':'research','cloud_allowed':True,
            'limits':{'token_budget':32768,'output_tokens':512,'timeout_seconds':120},
            'specialists':[{'kind':kind,'skill_version_id':skill['version']['id']} for kind in ('analyst','content')]}
        response=await client.put(base(c)+'/routing',headers=c['owner'],json={
            'expected_revision':0,'request_key':str(uuid4()),'content':config})
        assert response.status_code==200,response.text
        path,plan,review,_=await approved(client,c)
        response=await client.post(path+'/materialize',headers=c['owner'],json=material(plan,review))
        assert response.status_code==200,response.text
        materialized=response.json();state['stages'].append('profile_plan_owner_review_materialized')
        state['plan_id']=plan['id']
        async with Session.begin() as db:
            other=Workspace(name='Other synthetic SME');db.add(other);await db.flush()
            db.add(Member(workspace_id=other.id,user_id=c['user_id'],role='owner'))
            other_id=other.id
        denied=await client.post(path+'/jobs',headers=c['owner'],json=start_body('content',job={'target':'content'}))
        assert denied.status_code==403 and not state['requested_calls'],denied.text
        # Capture a real immutable model/budget pin, then edit routing. The queued
        # job must keep its original target; only a later job uses revision2.
        body=start_body();response=await client.post(path+'/jobs',headers=c['owner'],json=body)
        assert response.status_code==202,response.text
        first=response.json();owned.append(first['run_id'])
        duplicate=await client.post(path+'/jobs',headers=c['owner'],json=body)
        assert duplicate.status_code==202 and duplicate.json()['id']==first['id']
        config['default_target']='content'
        response=await client.put(base(c)+'/routing',headers=c['owner'],json={
            'expected_revision':1,'request_key':str(uuid4()),'content':config})
        assert response.status_code==200,response.text
        from arq import create_pool
        from arq.worker import create_worker
        from arq.connections import RedisSettings
        from arq.constants import job_key_prefix
        from pao.runtime import dispatch,execute_run
        rs=RedisSettings.from_dsn(settings().redis_url);assert rs.database==15
        redis=await create_pool(rs,default_queue_name=queue)
        class Workers:
            functions=[execute_run];redis_settings=rs;queue_name=queue
            handle_signals=False;burst=True;max_jobs=max_burst_jobs=1
            keep_result=0;poll_delay=.05;job_timeout=150
        async def worker(job):
            await dispatch({'redis':redis})
            assert await redis.exists(job_key_prefix+'run:'+job['run_id'])
            runner=create_worker(Workers)
            try:
                await asyncio.wait_for(runner.async_run(),160)
                assert runner.jobs_complete==1 and runner.jobs_failed==0
            finally:
                if not hasattr(signal,'SIGUSR1'):
                    runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
                await runner.close()
            # Production collects terminal business runs on its existing scheduler
            # tick; ARQ execution alone does not update the task's review state.
            from pao.modules.schedules.dispatcher import dispatch_studio_schedules
            await dispatch_studio_schedules()
            response=await client.get(base(c)+'/jobs/'+job['id'],headers=c['owner'])
            assert response.status_code==200,response.text
            value=response.json();assert value['status']=='completed',value
            assert value['artifact']=={'text':'PAO_MUSE_BUSINESS_DRAFT'}
            return value
        first=await worker(first)
        assert (first['model'],first['routing_revision'])==('muse-spark-1.3',1)
        assert len(state['requested_calls'])==1
        # Completion is draft-only until owner review. A dependency is still blocked.
        denied=await client.post(path+'/jobs',headers=c['owner'],json=start_body('content',routing_revision=2))
        assert denied.status_code==403 and len(state['requested_calls'])==1
        async with Session() as db:
            task=await db.get(Task,first['task_id']);assert task.status=='waiting_approval' and task.progress==90
        wrong=await client.post(base(c)+'/jobs/'+first['id']+'/review',headers=c['owner'],json={
            'request_key':str(uuid4()),'decision':'approve','artifact_hash':'0'*64,'confirm_review':True})
        assert wrong.status_code==409,wrong.text
        await review_content(client,c,first)
        state['stages'].append('arq_research_draft_owner_review_dependency_gate')
        response=await client.post(path+'/jobs',headers=c['owner'],json=start_body('content',routing_revision=2))
        assert response.status_code==202,response.text
        second=response.json();owned.append(second['run_id'])
        second=await worker(second)
        assert (second['model'],second['routing_revision'])==('muse-spark-1.2',2)
        await review_content(client,c,second)
        for item in (first,second):
            denied=await client.get(base(c).replace(c['workspace'],other_id)+'/jobs/'+item['id'],headers=c['owner'])
            assert denied.status_code==404
            await execute_run({},item['run_id'])  # Completed replay never dispatches again.
            # Studio business drafts are read through their native job artifact;
            # legacy skill-replay is a different archive contract, not this path.
            replay=await client.get(base(c)+'/jobs/'+item['id'],headers=c['owner'])
            assert replay.status_code==200,replay.text
            assert replay.json()['artifact_hash']==item['artifact_hash']
            assert replay.json()['artifact']==item['artifact'] and replay.json()['content_approved']
            legacy=await client.get('/v1/runs/'+item['run_id']+'/skill-replay',headers=c['owner'])
            assert legacy.status_code==409  # Never synthesize a legacy archive to pass.
        assert len(state['requested_calls'])==2
        state['stages'].append('arq_content_owner_review_scoped_artifacts_replay')
        async with Session() as db:
            tasks=list(await db.scalars(select(Task).where(Task.goal_id==materialized['goal_id'])))
            assert len(tasks)==2 and all(t.status=='completed' and t.progress==100 for t in tasks)
            goal=await db.get(Goal,materialized['goal_id']);assert goal.status=='completed'
            project=await db.get(Project,tasks[0].project_id);assert project.status=='completed'
            attempts=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id.in_(owned))))
            assert len(attempts)==2
            for row in attempts:
                state['calls'].append({'model':row.model,'source':row.source,'status':row.status,
                    'usage_state':row.usage_state,'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,
                    'effort':row.trace['engine_selection']['reasoning_effort'],
                    'cleanup_verified':row.trace['muse_dispatch'].get('cleanup_verified')})
                assert row.provider=='muse' and row.status=='completed' and row.usage_state=='reported'
                assert row.trace['muse_dispatch']['cleanup_verified']
            assert not await db.scalar(select(ToolCall.id).where(ToolCall.run_id.in_(owned)))
            assert len(list(await db.scalars(select(TaskAttempt).where(TaskAttempt.run_id.in_(owned)))))==2
            for run_id in owned:
                job=await db.scalar(select(BusinessJob).where(BusinessJob.run_id==run_id))
                chat=await db.get(ChatSession,(await db.get(Run,run_id)).session_id)
                assert job.selection['limits']['token_budget']==32768
                assert job.selection['target']['installation_resource_id']==rid
                assert chat.engine_config['provider']=='muse' and chat.memory_enabled is False
        report_body={'request_key':str(uuid4()),'window_from':(now()-timedelta(days=1)).isoformat(),'window_to':now().isoformat()}
        response=await client.post(path+'/reports',headers=c['owner'],json=report_body)
        assert response.status_code==200,response.text
        report=response.json();usage=report['report']['model_usage']
        assert usage['input_tokens']==sum(v['input_tokens'] for v in state['calls'])
        assert usage['output_tokens']==sum(v['output_tokens'] for v in state['calls'])
        assert usage['provider_billed_cost'] is None and report['report']['external_delivery'] is False
        assert all(k['measured'] is None for k in report['report']['kpis'])
        duplicate=await client.post(path+'/reports',headers=c['owner'],json=report_body)
        assert duplicate.status_code==200 and duplicate.json()['id']==report['id']
        operations=await client.get(path+'/operations',headers=c['owner'])
        assert operations.status_code==200 and len(operations.json()['jobs'])==2
        assert all(j['content_approved'] for j in operations.json()['jobs'])
        assert len(state['requested_calls'])==2
        state.update(pass_=True,arq_jobs=2,replay_provider_calls=0,tools=0,
            report_usage=usage,completed_tasks=2,goal_completed=True,project_completed=True)
        state['pass']=state.pop('pass_');state['stages'].append('report_actual_usage_idempotency_goal_project_completed')
    finally:
        try:
            if redis:
                from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix
                keys=[queue,*(prefix+'run:'+rid for rid in owned
                    for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix))]
                try:
                    await redis.delete(*keys)
                    state['redis_cleanup_verified']=await redis.exists(*keys)==0
                    if not state['redis_cleanup_verified']:
                        state['pass']=False
                        raise AssertionError('Owned ARQ keys remain; preserve failure, never flush Redis')
                finally:await redis.aclose()
        finally:
            with target.open('x',encoding='utf-8') as output:json.dump(state,output,indent=2)
    return state


async def test_muse_business_cycle_without_provider(client,identity,monkeypatch,tmp_path):
    value=await business_cycle(client,identity,monkeypatch,tmp_path)
    assert value['pass'] and value['live_subscription'] is False


async def test_provider_managed_business_cycle_above_legacy_output(client,identity,monkeypatch,tmp_path):
    value=await business_cycle(client,identity,monkeypatch,tmp_path,provider_managed=True)
    assert value['pass'] and value['report_usage']['output_tokens']==12000
