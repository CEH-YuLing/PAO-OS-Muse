"""Real synthetic High reasoning chat, only two Muse calls, no primary prompts."""
import json,os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ChatSession,Run,LlmAttempt,ToolCall
from pao.modules.cli_connections import muse_client as native,muse_profile as profile,muse_execution as execution
from test_muse_resources import connect


async def test_real_high_reasoning_without_pao_token_caps(client,identity,monkeypatch,tmp_path):
    assert os.environ.get('PAO_GD01_MUSE_LIVE_APPROVED')=='two_synthetic_calls_no_fallback'
    state={'pass':False,'requested_calls':[],'calls':[],'primary_data_sent':False,'primary_mutations':False,'API_fallback':False}
    try:
        for key in ('provider_managed_tokens','installation_ai_enabled','engine_contract_enabled','chat_features_enabled','agent_runtime_enabled'):
            monkeypatch.setattr(settings(),key,True)
        monkeypatch.setattr(settings(),'memory_enabled',False)
        monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
        monkeypatch.setattr(profile,'PROFILE',Path('F:/PAO-ACOS/.runtime/muse-profile'))
        monkeypatch.setattr(native,'STATE',tmp_path/'muse.json')
        rid=await connect(client,identity)
        send=execution.execute
        async def counted(messages,model,effort,authorize,**kwargs):
            assert len(state['requested_calls'])<2 and model=='muse-spark-1.2' and effort=='high'
            state['requested_calls'].append({'model':model,'effort':effort})
            return await send(messages,model,effort,authorize,**kwargs)
        monkeypatch.setattr(execution,'execute',counted)
        response=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})
        assert response.status_code==201;sid=response.json()['id']
        async with Session.begin() as db:
            chat=await db.get(ChatSession,sid);chat.memory_enabled=False
            chat.chat_profile={'policy':{'privacy':'cloud_allowed','cloud_references':True,'context_tokens':4096,
                'max_output_tokens':512,'max_run_tokens':32768}}
        response=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={
            'provider':'muse','model':'muse-spark-1.2','installation_resource_id':rid,'reasoning_effort':'high','version':1})
        assert response.status_code==200,response.text
        response=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,'request_key':uuid4().hex,
            'message':'Bài thử tổng hợp, không dùng công cụ, tệp hoặc dữ liệu doanh nghiệp. Viết một bài giải thích bằng tiếng Việt khoảng 450 từ về cách lập danh sách việc cần làm trong ngày. Bắt đầu bằng PAO_MUSE_HIGH_OK. Không giao cho chuyên gia.'})
        assert response.status_code==202,response.text
        run_id=response.json()['id']
        from pao.runtime import execute_run
        await execute_run({},run_id)
        async with Session() as db:
            run=await db.get(Run,run_id)
            rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run_id)))
            state['run_id']=run_id;state['run_status']=run.status;state['error_code']=run.error_code
            state['calls']=[{'source':r.source,'model':r.model,'status':r.status,'input_tokens':r.input_tokens,
                'output_tokens':r.output_tokens,'reserved_output_tokens':r.reserved_output_tokens,
                'cleanup_verified':r.trace.get('muse_dispatch',{}).get('cleanup_verified')} for r in rows]
            assert run.status=='completed',run.error_code
            assert 'PAO_MUSE_HIGH_OK' in run.response[:80] and len(run.response)>1000
            assert run.engine_snapshot['chat_policy']['token_mode']=='provider'
            assert len(rows)==2 and all(r.status=='completed' and r.usage_state=='reported' and r.reserved_output_tokens==0 for r in rows)
            assert any(r.output_tokens>512 for r in rows),'Must actually exercise former failing boundary'
            assert not await db.scalar(select(ToolCall.id).where(ToolCall.run_id==run_id))
        await execute_run({},run_id);assert len(state['requested_calls'])==2
        state.update(pass_=True,replay_provider_calls=0,tools=0);state['pass']=state.pop('pass_')
    finally:
        with Path(os.environ['PAO_GD01_MUSE_LIVE_RECEIPT']).open('x',encoding='utf-8') as output:json.dump(state,output,indent=2)
