"""Production-default token policy, including outputs beyond former 512-token caps."""
import json
import httpx
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Run,LlmAttempt,TenantResourcePolicy
from pao.gateway import Chunk,OpenAICompatibleGateway,AnthropicGateway,GeminiGateway,OllamaGateway
from pao.agents import ExecutionPlan
from pao.runtime import execute_run
from pao.modules.chat.token_policy import PROVIDER_MANAGED,TRANSPORT_BYTES
from pao.modules.chat.context import compile_messages
from pao.modules.engines.contract import EngineFailure
from test_chat_management import chat_on,new,start


class Large:
    provider_name='ollama';model_name='synthetic-local'
    async def plan(self,messages):
        assert PROVIDER_MANAGED.get()
        self.last_usage={'input_tokens':40000,'output_tokens':1200}
        return ExecutionPlan(goal='Synthetic large context',steps=[],tools=[])
    async def stream(self,messages,max_tokens=None):
        assert PROVIDER_MANAGED.get() and max_tokens==0
        yield Chunk(text='Synthetic answer. '*700,usage={'input_tokens':41000,'output_tokens':6000})


async def test_large_input_output_planner_and_legacy_fields_do_not_cap_new_run(client,identity,chat_on,monkeypatch):
    monkeypatch.setattr(settings(),'provider_managed_tokens',True)
    sid=await new(client,identity)
    run_id=await start(client,identity,sid,'Synthetic large input. '*1000)
    await execute_run({'gateway':Large()},run_id)
    async with Session() as db:
        run=await db.get(Run,run_id)
        assert run.status=='completed',run.error_code
        assert len(run.response)>10000 and run.engine_snapshot['chat_policy']['token_mode']=='provider'
        rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run_id)))
        assert len(rows)==2 and all(r.status=='completed' and r.reserved_output_tokens==0 for r in rows)
        assert {r.output_tokens for r in rows}=={1200,6000}
        assert all(r.trace['max_tokens'] is None and r.trace['max_bytes']==TRANSPORT_BYTES for r in rows)
    assert PROVIDER_MANAGED.get() is False


async def test_explicit_enterprise_quota_is_not_removed(client,identity,chat_on,monkeypatch):
    monkeypatch.setattr(settings(),'provider_managed_tokens',True)
    sid=await new(client,identity);rid=await start(client,identity,sid)
    async with Session.begin() as db:
        db.add(TenantResourcePolicy(workspace_id=identity['workspace'],daily_model_calls=1,daily_model_tokens=1,
            concurrent_models=1,updated_by=identity['user_id']))
    await execute_run({'gateway':Large()},rid)
    async with Session() as db:
        run=await db.get(Run,rid);assert run.status=='failed'
        assert run.error_code=='tenant_model_daily_tokens_exhausted'
        assert not await db.scalar(select(LlmAttempt.id).where(LlmAttempt.run_id==rid))


def test_context_is_not_trimmed_and_transport_limit_remains_explicit():
    rows=[{'role':'system','content':'Policy'},*[{'role':'user','content':'Synthetic history '+str(i)+' x'*500} for i in range(180)]]
    value=compile_messages(rows,max_tokens=None,max_bytes=TRANSPORT_BYTES)
    assert len(value.messages)==len(rows) and value.trace['dropped_history_count']==0
    with pytest.raises(EngineFailure,match='context_transport_limit'):
        compile_messages(rows,max_tokens=None,max_bytes=100)


@pytest.mark.parametrize('provider',['openai','openrouter','anthropic','gemini','ollama'])
async def test_provider_wire_uses_native_token_defaults(provider,monkeypatch):
    captured=[];plan=ExecutionPlan(goal='Synthetic',steps=[],tools=[]).model_dump_json()
    def handle(request):
        if request.method=='GET':
            assert provider=='anthropic' and '/models/' in request.url.path
            return httpx.Response(200,json={'id':'fixture','max_tokens':64000})
        body=json.loads(request.content);captured.append(body)
        if provider in ('openai','openrouter'):
            assert 'max_tokens' not in body and 'max_completion_tokens' not in body
            return httpx.Response(200,json={'choices':[{'message':{'content':plan}}],'usage':{'input_tokens':100,'output_tokens':1200}})
        if provider=='anthropic':
            assert body['max_tokens']==64000
            return httpx.Response(200,json={'content':[{'type':'text','text':plan}],'usage':{'input_tokens':100,'output_tokens':1200}})
        if provider=='gemini':
            assert 'maxOutputTokens' not in body['generationConfig']
            return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':plan}]}}],
                'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':1200}})
        assert 'num_ctx' not in body['options'] and 'num_predict' not in body['options']
        return httpx.Response(200,json={'done':True,'message':{'content':plan},'prompt_eval_count':100,'eval_count':1200})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handle),**kw))
    gateway=(OpenAICompatibleGateway(provider,'synthetic','fixture','https://example.test') if provider in ('openai','openrouter')
        else AnthropicGateway('synthetic','fixture') if provider=='anthropic'
        else GeminiGateway('synthetic','fixture') if provider=='gemini' else OllamaGateway('synthetic-local','http://127.0.0.1:11434'))
    token=PROVIDER_MANAGED.set(True)
    try:
        result=await gateway.plan([{'role':'system','content':'Policy'},{'role':'user','content':'Synthetic'}])
        assert result.goal=='Synthetic' and len(captured)==1
    finally:PROVIDER_MANAGED.reset(token)
