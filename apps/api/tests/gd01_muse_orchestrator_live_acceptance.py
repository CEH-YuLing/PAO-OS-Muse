"""Explicit planner+answer Muse smoke; synthetic pao_test scope only."""
import json,os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ChatSession,Run,LlmAttempt,ToolCall,AgentRun
from pao.modules.cli_connections import muse_client as native,muse_profile as profile,muse_execution as execution
from pao.modules.installation_ai.models import InstallationAIResource


async def test_real_muse_orchestrator(client,identity,monkeypatch,tmp_path):
    assert os.environ.get('PAO_GD01_MUSE_LIVE_APPROVED')=='two_synthetic_calls_no_fallback'
    state={'pass':False,'calls':[],'requested_calls':[],'primary_data_sent':False,'primary_mutations':False,'tools':None,'specialists':None,'api_fallback':False}
    try:
        monkeypatch.setattr(profile,'PROFILE',Path('F:/PAO-ACOS/.runtime/muse-profile'))
        monkeypatch.setattr(native,'STATE',tmp_path/'muse.json')
        for key in ('installation_ai_enabled','engine_contract_enabled','chat_features_enabled','agent_runtime_enabled'):
            monkeypatch.setattr(settings(),key,True)
        monkeypatch.setattr(settings(),'memory_enabled',False)
        monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
        result=await client.post('/v1/muse-client',params={'workspace_id':identity['workspace']},headers=identity['owner'],json={'request_key':str(uuid4()),'expected_revision':0})
        assert result.status_code==200,result.text
        async with Session() as db:rid=(await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='muse'))).id
        calls=state['requested_calls'];send=execution.execute
        async def counted(messages,model,effort,authorize,**kwargs):
            assert len(calls)<2,'Planner and final only, never retry/fallback'
            calls.append({'model':model,'effort':effort})
            return await send(messages,model,effort,authorize,**kwargs)
        monkeypatch.setattr(execution,'execute',counted)
        result=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']});assert result.status_code==201
        sid=result.json()['id']
        async with Session.begin() as db:
            chat=await db.get(ChatSession,sid);chat.memory_enabled=False
            chat.chat_profile={'policy':{'privacy':'cloud_allowed','cloud_references':True}}
        result=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={'provider':'muse','model':'muse-spark-1.3',
            'installation_resource_id':rid,'reasoning_effort':'minimal','prepare_muse_context':True,'version':1})
        assert result.status_code==200,result.text
        body={'session_id':sid,'request_key':uuid4().hex,'message':'Simple synthetic connection test. No specialist, tools, files, business data or external actions. Reply exactly PAO_MUSE_ORCHESTRATOR_OK.'}
        result=await client.post('/v1/runs',headers=identity['owner'],json=body);assert result.status_code==202,result.text
        run_id=result.json()['id']
        from pao.runtime import execute_run
        await execute_run({},run_id)
        async with Session() as db:
            run=await db.get(Run,run_id);assert run.status=='completed',run.error_code
            assert run.response.strip()=='PAO_MUSE_ORCHESTRATOR_OK'
            rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run_id).order_by(LlmAttempt.created_at)))
            assert len(rows)==2 and {r.source for r in rows}=={'chat_planner','chat_final'}
            for row in rows:
                state['calls'].append({'model':row.model,'source':row.source,'effort':row.trace['engine_selection']['reasoning_effort'],
                    'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,
                    'cleanup_verified':row.trace.get('muse_dispatch',{}).get('cleanup_verified')})
            tools=list(await db.scalars(select(ToolCall.id).where(ToolCall.run_id==run_id)))
            agents=list(await db.scalars(select(AgentRun).where(AgentRun.run_id==run_id)))
            state['tools']=len(tools)
            state['specialists']=sum(row.agent_key!='chief_of_staff' for row in agents)
            # The native orchestrator records its own chief row even without delegation.
            assert not tools and state['specialists']==0
            assert len(agents)==1 and agents[0].agent_key=='chief_of_staff' and agents[0].step_index==0
            for row in rows:
                assert row.status=='completed' and row.usage_state=='reported' and row.trace['muse_dispatch']['cleanup_verified']
        await execute_run({},run_id);assert len(calls)==2
        state.update(pass_=True,replay_provider_calls=0);state['pass']=state.pop('pass_')
    finally:
        with Path(os.environ['PAO_GD01_MUSE_LIVE_RECEIPT']).open('x',encoding='utf-8') as output:json.dump(state,output,indent=2)
