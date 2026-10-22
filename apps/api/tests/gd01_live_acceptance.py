"""Explicit-only real OpenAI smoke. Not collected by ordinary offline regression."""
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ChatSession, Run, LlmAttempt, ToolCall
from pao.modules.installation_ai import service, openai_effort
from pao.modules.installation_ai.models import InstallationAIResource
from test_gd01_ai_resources import common
from test_studio import make, publish, SCHEMA


@pytest.fixture
def live_summary():
    value={'pass':False,'calls':[],'primary_data_sent':False,'primary_mutations':False,
        'quota_remaining':None,'billing_amount':None}
    yield value
    target=Path(os.environ['PAO_GD01_LIVE_RECEIPT'])
    assert target.name=='live-summary.json' and target.parent.name.startswith('gd01-tests-')
    with target.open('x',encoding='utf-8') as output:json.dump(value,output,indent=2)


async def test_real_chat_and_specialist_two_models(client,identity,common,monkeypatch,live_summary):
    from pao.runtime import execute_run
    from pao.gateway import cloud_gateway
    key=os.environ.pop('PAO_GD01_LIVE_KEY')
    assert key and os.environ['PAO_GD01_LIVE_APPROVED']=='two_synthetic_calls_no_fallback'
    selected=[];calls=live_summary['calls']
    real=httpx.AsyncClient
    native=httpx.AsyncHTTPTransport
    class Restricted(native):
        async def handle_async_request(self,request):
            assert request.method=='POST' and str(request.url)=='https://api.openai.com/v1/chat/completions'
            body=json.loads(request.content)
            assert body['model'] in ('gpt-6.1-sol','gpt-6-luna')
            assert 0<body['max_completion_tokens']<=512 and len(request.content)<=16384
            assert not any(k in body for k in ('tools','functions','tool_choice'))
            assert len(calls)<2,'Live invocation ceiling reached; never retry automatically'
            calls.append({'model':body['model'],'effort':body.get('reasoning_effort')})
            return await super().handle_async_request(request)
    def client_factory(**kwargs):
        assert not kwargs.get('trust_env',True)
        return real(transport=Restricted(retries=0),**kwargs)
    def factory(provider,synthetic,model,**kwargs):
        assert provider=='openai' and synthetic=='SYNTHETIC-GD01'
        selected.append((model,kwargs.get('reasoning_effort')))
        return cloud_gateway(provider,key,model,**kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',client_factory)
    monkeypatch.setattr('pao.modules.engines.service.cloud_gateway',factory)
    for name in ('studio_enabled','brain_manager_enabled'):
        monkeypatch.setattr(settings(),name,True)
    # A plain Chat invocation, not a planner+answer pair. The total ceiling is
    # one Chat request plus one explicit specialist request, never three.
    monkeypatch.setattr(settings(),'agent_runtime_enabled',False)
    monkeypatch.setattr(settings(),'memory_enabled',False)
    async with Session.begin() as db:
        row=await db.get(InstallationAIResource,common)
        await service.capture(db,identity['user_id'],identity['workspace'],row.source_id,'api',[
            {'model':m,**openai_effort.metadata(m)} for m in ('gpt-6.1-sol','gpt-6-luna')])
    response=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})
    assert response.status_code==201
    sid=response.json()['id']
    async with Session.begin() as db:
        chat=await db.get(ChatSession,sid);chat.memory_enabled=False
        chat.chat_profile={'policy':{'privacy':'cloud_allowed','cloud_references':True,'context_tokens':8192,'max_output_tokens':512}}
        chat.engine_config=await service.config(db,identity['workspace'],identity['user_id'],None,common,'gpt-6.1-sol','low')
    response=await client.post('/v1/runs',headers=identity['owner'],json={
        'session_id':sid,'request_key':uuid4().hex,'message':'Reply with exactly PAO_GD01_OK. Do not use tools.'})
    assert response.status_code==202
    first=response.json()['id'];await execute_run({},first)
    async with Session() as db:
        run=await db.get(Run,first);assert run.status=='completed',run.error_code
        assert 'PAO_GD01_OK' in run.response
    monkeypatch.setattr(settings(),'agent_runtime_enabled',True)
    agent=await publish(client,identity,await make(client,identity,slug='gd01-live-agent',payload={
        'instruction':'Return only the requested JSON object. Never call tools.',
        'model_preference':{'provider':'openai','model':'gpt-6-luna','reasoning_effort':'medium','installation_resource_id':common}}))
    await publish(client,identity,await make(client,identity,'skills','gd01-live-echo',{
        'instruction':'Return exactly the input text as {"text":"..."}. No Markdown.',
        'agent_version_id':agent['version']['id'],'input_schema':SCHEMA,'output_schema':SCHEMA,
        'output_tokens':512,'timeout_seconds':120,'exit_criteria':['equals_input:text']}))
    body={'session_id':sid,'request_key':uuid4().hex,'message':'/gd01-live-echo {"text":"Synthetic GD01"}'}
    response=await client.post('/v1/runs',headers=identity['owner'],json=body);assert response.status_code==202
    second=response.json()['id'];await execute_run({},second)
    summaries=[]
    async with Session() as db:
        run=await db.get(Run,second);assert run.status=='completed',run.error_code
        assert run.studio_snapshot and run.engine_snapshot['model']=='gpt-6-luna'
        assert (await db.get(ChatSession,sid)).engine_config['model']=='gpt-6.1-sol'
        for rid in (first,second):
            rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==rid)))
            assert len(rows)==1 and rows[0].status=='completed' and rows[0].usage_state=='reported'
            assert not await db.scalar(select(ToolCall.id).where(ToolCall.run_id==rid))
            item=rows[0];summaries.append({'provider':item.provider,'model':item.model,'source':item.source,
                'usage_state':item.usage_state,'input_tokens':item.input_tokens,'output_tokens':item.output_tokens,
                'effort':item.trace['engine_selection'].get('reasoning_effort')})
    # Native replay cannot spend a third request or replace the original pins.
    replay=await client.post('/v1/runs',headers=identity['owner'],json=body)
    assert replay.status_code==202 and replay.json()['id']==second
    await execute_run({},second)
    assert calls==[{'model':'gpt-6.1-sol','effort':'low'},{'model':'gpt-6-luna','effort':'medium'}]
    live_summary.update({'pass':True,'attempts':summaries,
        'primary_data_sent':False,'primary_mutations':False,'tools':0,'replay_provider_calls':0,
        'native_chat_and_studio':True,'installed_browser_acceptance':False})
