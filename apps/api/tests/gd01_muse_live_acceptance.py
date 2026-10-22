"""Explicit two-call Muse subscription acceptance in pao_test, never primary."""
import json
import os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ChatSession,Run,LlmAttempt,ToolCall
from pao.modules.cli_connections import muse_client as native,muse_profile as profile
from pao.modules.installation_ai.models import InstallationAIResource
from test_studio import make,publish,SCHEMA


async def test_real_muse_chat_and_agent(client,identity,monkeypatch,tmp_path):
    assert os.environ.get('PAO_GD01_MUSE_LIVE_APPROVED')=='two_synthetic_calls_no_fallback'
    target=Path(os.environ['PAO_GD01_MUSE_LIVE_RECEIPT'])
    assert target.name=='live-summary.json' and target.parent.name.startswith('gd01-tests-')
    state={'pass':False,'native_chat_and_studio':False,'primary_data_sent':False,'primary_mutations':False,
        'quota_remaining':None,'calls':[],'tools':0,'api_fallback':False}
    try:
        monkeypatch.setattr(profile,'PROFILE',Path('F:/PAO-ACOS/.runtime/muse-profile'))
        monkeypatch.setattr(native,'STATE',tmp_path/'muse.json')
        for name in ('installation_ai_enabled','engine_contract_enabled','chat_features_enabled','studio_enabled','brain_manager_enabled'):
            monkeypatch.setattr(settings(),name,True)
        monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
        monkeypatch.setattr(settings(),'agent_runtime_enabled',False)
        monkeypatch.setattr(settings(),'memory_enabled',False)
        result=await client.post('/v1/muse-client',params={'workspace_id':identity['workspace']},headers=identity['owner'],
            json={'request_key':str(uuid4()),'expected_revision':0})
        assert result.status_code==200,result.text
        assert result.json()['inference_enabled']
        async with Session() as db:rid=(await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='muse'))).id
        real=native.discover;counter=[]
        from pao.modules.cli_connections import muse_execution as execution
        actual=execution.execute
        async def send(messages,model,effort,authorize,**kwargs):
            assert len(counter)<2,'No automatic retry or fallback'
            assert model in ('muse-spark-1.3','muse-spark-1.2') and effort in ('minimal','low')
            counter.append((model,effort))
            return await actual(messages,model,effort,authorize,**kwargs)
        monkeypatch.setattr(execution,'execute',send)
        response=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})
        assert response.status_code==201,response.text
        sid=response.json()['id']
        async with Session.begin() as db:
            chat=await db.get(ChatSession,sid);chat.memory_enabled=False
            chat.chat_profile={'policy':{'privacy':'cloud_allowed','cloud_references':True}}
        response=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={
            'provider':'muse','model':'muse-spark-1.3','installation_resource_id':rid,
            'reasoning_effort':'minimal','prepare_muse_context':True,'version':1})
        assert response.status_code==200,response.text
        from pao.runtime import execute_run
        response=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,
            'request_key':uuid4().hex,'message':'Synthetic connection test only. Do not use tools or files. Reply exactly PAO_MUSE_CHAT_OK.'})
        assert response.status_code==202,response.text
        first=response.json()['id'];await execute_run({},first)
        async with Session() as db:
            run=await db.get(Run,first);assert run.status=='completed',run.error_code
            assert run.response.strip()=='PAO_MUSE_CHAT_OK'
        monkeypatch.setattr(settings(),'agent_runtime_enabled',True)
        agent=await publish(client,identity,await make(client,identity,slug='muse-live-agent',payload={
            'instruction':'Return only the requested JSON object without Markdown. No tools.',
            'model_preference':{'provider':'muse','model':'muse-spark-1.2','reasoning_effort':'low','installation_resource_id':rid}}))
        await publish(client,identity,await make(client,identity,'skills','muse-live-echo',{
            'instruction':'Return the exact input text in a single JSON object with key text. No Markdown.',
            'agent_version_id':agent['version']['id'],'input_schema':SCHEMA,'output_schema':SCHEMA,
            'token_budget':32768,'output_tokens':512,'timeout_seconds':120,'exit_criteria':['equals_input:text']}))
        body={'session_id':sid,'request_key':uuid4().hex,'message':'/muse-live-echo {"text":"Synthetic Muse"}'}
        response=await client.post('/v1/runs',headers=identity['owner'],json=body)
        assert response.status_code==202,response.text
        second=response.json()['id'];await execute_run({},second)
        async with Session() as db:
            run=await db.get(Run,second);assert run.status=='completed',run.error_code
            assert json.loads(run.response)=={'text':'Synthetic Muse'}
            assert run.studio_snapshot and run.engine_snapshot['model']=='muse-spark-1.2'
            assert (await db.get(ChatSession,sid)).engine_config['model']=='muse-spark-1.3'
            for run_id in (first,second):
                attempts=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run_id)))
                assert len(attempts)==1 and attempts[0].status=='completed' and attempts[0].usage_state=='reported'
                row=attempts[0];dispatch=row.trace['muse_dispatch']
                assert dispatch['status']=='native_completed' and dispatch['cleanup_verified']
                assert not await db.scalar(select(ToolCall.id).where(ToolCall.run_id==run_id))
                state['calls'].append({'model':row.model,'source':row.source,'status':row.status,'usage_state':row.usage_state,
                    'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,
                    'effort':row.trace['engine_selection']['reasoning_effort'],'cleanup_verified':True})
        replay=await client.post('/v1/runs',headers=identity['owner'],json=body)
        assert replay.status_code==202 and replay.json()['id']==second
        await execute_run({},second)
        assert counter==[('muse-spark-1.3','minimal'),('muse-spark-1.2','low')]
        state.update(pass_=True,native_chat_and_studio=True,replay_provider_calls=0)
        state['pass']=state.pop('pass_')
    finally:
        with target.open('x',encoding='utf-8') as output:json.dump(state,output,indent=2)
