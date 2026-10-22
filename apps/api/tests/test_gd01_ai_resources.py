"""GD01: real wire contracts with synthetic transports; never access provider quota."""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from pao.config import settings
from pao.db import Session
from pao.gateway import cloud_gateway, CloudProviderError
from pao.model_router import fetch_model_catalog, encrypt_key
from pao.models import ModelProviderConnection, ChatSession, Run, LlmAttempt, MemoryJob, Workspace, Member
from pao.modules.installation_ai import api_effort, service
from pao.modules.installation_ai.models import InstallationAIResource
from pao.modules.engines.contract import EngineFailure, normalize


@pytest.mark.parametrize('provider,model,levels',[
    ('anthropic','claude-opus-4-5',['low','medium','high']),
    ('anthropic','claude-opus-4-6',['low','medium','high','max']),
    ('anthropic','claude-sonnet-4-6',['low','medium','high','max']),
    ('anthropic','claude-opus-5-5',['low','medium','high','xhigh','max']),
    ('gemini','gemini-3.8-flash',['low','medium','high']),
    ('gemini','gemini-3.6-flash',['minimal','low','medium','high']),
    ('gemini','gemini-3-pro-preview',['low','high']),
])
def test_exact_api_contracts(provider,model,levels):
    assert api_effort.metadata(provider,model)['reasoning_efforts']==levels
    for effort in levels:cloud_gateway(provider,'SYNTHETIC',model,reasoning_effort=effort)
    changed=api_effort.metadata(provider,model);changed['reasoning_efforts'].clear()
    assert api_effort.metadata(provider,model)['reasoning_efforts']==levels


@pytest.mark.parametrize('provider,model',[
    ('anthropic','claude-opus-4-6:custom'),('anthropic','claude-opus-4-6-20990101'),
    ('anthropic','unknown'),('gemini','gemini-2.5-pro'),('gemini','gemini-3.8-live'),
    ('gemini','gemini-3.1-flash-lite-image'),('gemini','gemini-3.8-flash-unknown'),
])
def test_no_prefix_or_modality_guess(provider,model):
    assert api_effort.metadata(provider,model)['reasoning_efforts']==[]
    with pytest.raises(CloudProviderError,match='ai_effort_not_supported'):
        cloud_gateway(provider,'SYNTHETIC',model,reasoning_effort='high')
    cloud_gateway(provider,'SYNTHETIC',model)  # Old unselected contract stays readable.


@pytest.mark.parametrize('effort',['HIGH',True,{},[],'ultra','none'])
def test_invalid_effort_no_network(effort):
    for provider,model in [('anthropic','claude-opus-4-6'),('gemini','gemini-3.8-flash')]:
        with pytest.raises(CloudProviderError):cloud_gateway(provider,'SYNTHETIC',model,reasoning_effort=effort)


@pytest.mark.parametrize('provider,model',[('anthropic','claude-opus-4-6'),('gemini','gemini-3.8-flash')])
async def test_dynamic_ids_not_invented_and_effort_is_annotated(provider,model):
    def respond(request):
        assert request.method=='GET'
        data={'models':[{'name':'models/'+model,'supportedGenerationMethods':['generateContent']},
                        {'name':'models/unknown','supportedGenerationMethods':['generateContent']}]} if provider=='gemini' else {'data':[{'id':model},{'id':'unknown'}]}
        return httpx.Response(200,json=data)
    rows=await fetch_model_catalog(provider,'SYNTHETIC',httpx.MockTransport(respond))
    assert {v['model'] for v in rows}=={model,'unknown'}
    assert next(v for v in rows if v['model']==model)['reasoning_efforts']
    assert next(v for v in rows if v['model']=='unknown')['reasoning_efforts']==[]


@pytest.mark.parametrize('provider,model',[('anthropic','claude-opus-4-6'),('gemini','gemini-3.8-flash')])
@pytest.mark.parametrize('effort',['low','high'])
@pytest.mark.parametrize('mode',['stream','extract'])
async def test_wire_stream_usage_thinking_filter_and_structured(monkeypatch,provider,model,effort,mode):
    real=httpx.AsyncClient;seen=[]
    def respond(request):
        body=json.loads(request.content);seen.append(body)
        assert body.get('model',model)==model and not any(k in body for k in ('tools','tool_choice','thinking'))
        if provider=='anthropic':
            assert body['output_config']=={'effort':effort} and 'temperature' not in body
            assert body['max_tokens']==(128 if mode=='stream' else 512)
            if mode=='extract':return httpx.Response(200,json={'content':[{'type':'thinking','thinking':'PRIVATE'},
                {'type':'text','text':'{"facts":[]}'}],'usage':{'input_tokens':20,'output_tokens':7}})
            frames=[{'type':'message_start','message':{'usage':{'input_tokens':20,'output_tokens':0}}},
                {'type':'content_block_delta','delta':{'type':'thinking_delta','thinking':'PRIVATE'}},
                {'type':'content_block_delta','delta':{'type':'text_delta','text':'OK'}},
                {'type':'message_delta','usage':{'output_tokens':7}}, {'type':'message_stop'}]
        else:
            cfg=body['generationConfig'];assert cfg['thinkingConfig']=={'thinkingLevel':effort}
            assert cfg['maxOutputTokens']==(128 if mode=='stream' else 512)
            content={'candidates':[{'content':{'parts':[{'thought':True,'text':'PRIVATE'},
                {'text':'OK' if mode=='stream' else '{"facts":[]}'}]},'finishReason':'STOP'}],
                'usageMetadata':{'promptTokenCount':20,'candidatesTokenCount':3,'thoughtsTokenCount':4}}
            if mode=='extract':return httpx.Response(200,json=content)
            frames=[content]
        return httpx.Response(200,text='\n\n'.join('data: '+json.dumps(v) for v in frames)+'\n\n')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond),**kw))
    gateway=cloud_gateway(provider,'SYNTHETIC',model,reasoning_effort=effort)
    if mode=='extract':
        assert (await gateway.extract('Synthetic prompt')).facts==[]
        usage=gateway.last_usage
    else:
        rows=[v async for v in gateway.stream([{'role':'user','content':'Synthetic prompt'}],128)]
        assert ''.join(v.text for v in rows)=='OK'
        usage={k:v for chunk in rows for k,v in chunk.usage.items()}
    assert usage['input_tokens']==20 and usage['output_tokens']==7
    assert len(seen)==1


@pytest.mark.parametrize('provider,model',[('anthropic','claude-opus-4-6'),('gemini','gemini-3.8-flash')])
async def test_429_is_not_retried_or_reflected(monkeypatch,provider,model):
    real=httpx.AsyncClient;seen=[]
    def respond(request):seen.append(request.url);return httpx.Response(429,json={'error':'SENSITIVE'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond),**kw))
    with pytest.raises(CloudProviderError,match='^'+provider+'_request_failed$'):
        _=[v async for v in cloud_gateway(provider,'SYNTHETIC',model,reasoning_effort='low').stream([])]
    assert len(seen)==1


@pytest.fixture
async def common(client,identity,monkeypatch):
    for name in ('installation_ai_enabled','engine_contract_enabled','chat_features_enabled','memory_enabled'):
        monkeypatch.setattr(settings(),name,True)
    monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
    async with Session.begin() as db:
        source=ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',model='gpt-6.1-sol',
            api_key_ciphertext=encrypt_key('SYNTHETIC-GD01'),status='connected',is_default=False)
        db.add(source);await db.flush()
        await service.capture(db,identity['user_id'],identity['workspace'],source.id,'api',[
            {'model':'gpt-6.1-sol','reasoning_efforts':['low','high']},'gpt-6-luna'])
        row=await db.scalar(select(InstallationAIResource));resource_id=row.id
    result=await client.put('/v1/installation-ai/'+resource_id,headers=identity['owner'],json={
        'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'is_default':True,'default_model':'gpt-6.1-sol'})
    assert result.status_code==200,result.text
    return resource_id


async def create_completed(client,identity,common,monkeypatch):
    from pao.runtime import execute_run
    result=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})
    assert result.status_code==201,result.text
    sid=result.json()['id']
    async with Session.begin() as db:
        chat=await db.get(ChatSession,sid);chat.memory_enabled=True
        chat.chat_profile={'policy':{'privacy':'cloud_allowed','max_calls':8,'context_tokens':8192}}
        chat.engine_config=await service.config(db,identity['workspace'],identity['user_id'],None,common,'gpt-6.1-sol','low')
    response=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,'request_key':uuid4().hex,'message':'Synthetic business fact'})
    assert response.status_code==202,response.text
    rid=response.json()['id'];real=httpx.AsyncClient;seen=[]
    def respond(request):
        body=json.loads(request.content);seen.append(body)
        assert body['model']=='gpt-6.1-sol' and body['reasoning_effort']=='low'
        if body.get('stream'):
            return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':20,'completion_tokens':10}})+'\n\ndata: [DONE]\n\n')
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"facts":[]}'}}],
            'usage':{'prompt_tokens':30,'completion_tokens':5}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(respond),**kw))
    await execute_run({},rid)
    async with Session.begin() as db:
        run=await db.get(Run,rid);assert run.status=='completed',run.error_code
        assert run.engine_snapshot['memory_engine']=={'mode':'run_engine'}
        # The worker creates this only when enabled; keep the assertion explicit.
        assert await db.get(MemoryJob,rid)
    return rid,seen


async def test_extraction_uses_same_source_effort_and_no_local_llm(client,identity,common,monkeypatch):
    from pao.memory import extract_memory
    rid,seen=await create_completed(client,identity,common,monkeypatch)
    async def forbidden(*a,**kw):raise AssertionError('Must not re-resolve workspace defaults or invoke Ollama')
    monkeypatch.setattr('pao.model_router.gateway_for_workspace',forbidden)
    monkeypatch.setattr('pao.gateway.OllamaGateway.extract',forbidden)
    await extract_memory({},rid)
    async with Session() as db:
        job=await db.get(MemoryJob,rid);assert job.status=='completed',job.error_code
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==rid,LlmAttempt.source=='memory_extraction'))
        assert attempt.status=='completed' and attempt.provider=='openai' and attempt.model=='gpt-6.1-sol'
        assert attempt.trace['engine_selection']['reasoning_effort']=='low'
        assert (attempt.input_tokens,attempt.output_tokens)==(30,5)
    assert len(seen)==2


async def test_revoke_before_extraction_never_uses_other_source(client,identity,common,monkeypatch):
    from pao.memory import extract_memory
    rid,seen=await create_completed(client,identity,common,monkeypatch)
    async with Session.begin() as db:(await db.get(InstallationAIResource,common)).enabled=False
    await extract_memory({},rid)
    async with Session() as db:
        job=await db.get(MemoryJob,rid);assert job.status=='failed'
        assert job.error_code=='installation_ai_resource_disabled'
    assert len(seen)==1


async def test_evidence_distinguishes_catalog_inference_quota_and_sme(client,identity,common,monkeypatch):
    rid,_=await create_completed(client,identity,common,monkeypatch)
    async with Session.begin() as db:
        rows=await service.catalog(db,identity['workspace'],identity['user_id']);row=rows[0]
        assert row['catalog_evidence']['observed_at']
        assert row['inference_evidence']['state']=='observed_success'
        assert row['inference_evidence']['current_health']=='not_probed'
        assert row['quota_evidence']['remaining'] is None
        other=Workspace(name='Unrelated SME');db.add(other);await db.flush()
        db.add(Member(workspace_id=other.id,user_id=identity['user_id'],role='owner'));await db.flush()
        assert (await service.catalog(db,other.id,identity['user_id']))[0]['inference_evidence']['state']=='not_verified'
        native=await db.get(InstallationAIResource,common);native.revision+=1
        assert (await service.catalog(db,identity['workspace'],identity['user_id']))[0]['inference_evidence']['state']=='not_verified'


@pytest.mark.parametrize('kind,code',[('rate_limited','engine_provider_rate_limited'),
    ('authentication','engine_provider_authentication'),('temporary','engine_provider_temporary'),(None,'engine_unavailable')])
def test_provider_errors_remain_sanitized(kind,code):
    assert normalize(CloudProviderError('synthetic_response_not_safe_for_UI',kind)).code==code


@pytest.mark.parametrize('change',['none','success','revision','workspace','old','unclassified','effort'])
async def test_durable_circuit_uses_existing_ledger_and_does_not_cross_scope(client,identity,common,monkeypatch,change):
    from datetime import timedelta
    from pao.models import now
    from pao.modules.chat import transport_policy
    rid,_=await create_completed(client,identity,common,monkeypatch)
    async with Session.begin() as db:
        parent=await db.get(Run,rid);snapshot=dict(parent.engine_snapshot)
        chosen=transport_policy.selection(snapshot,'openai','gpt-6.1-sol')
        for i in range(3):
            trace={'engine_selection':chosen,'failure_code':'engine_provider_rate_limited'}
            if change=='unclassified':trace.pop('failure_code')
            db.add(LlmAttempt(workspace_id=parent.workspace_id,user_id=identity['user_id'],session_id=parent.session_id,
                run_id=rid,source='chat_final',request_key=uuid4().hex,provider='openai',model='gpt-6.1-sol',
                estimated_input_tokens=10,reserved_output_tokens=10,status='completed' if change=='success' and i==2 else 'failed',
                trace=trace,finished_at=now()-timedelta(seconds=120) if change=='old' else now()+timedelta(microseconds=i)))
        wid=parent.workspace_id
    # Fresh connection models a worker restart; no process-local circuit cache.
    async with Session() as db:
        if change=='revision':
            snapshot['connection_authority']={**snapshot['connection_authority'],'resource_revision':999}
        if change=='effort':snapshot['reasoning_effort']='high'  # Cannot evade a rate limit by changing effort.
        run=SimpleNamespace(workspace_id=str(uuid4()) if change=='workspace' else wid,engine_snapshot=snapshot)
        if change in ('none','effort'):
            with pytest.raises(EngineFailure,match='engine_resource_cooling_down'):
                await transport_policy.require_ready(db,run,'openai','gpt-6.1-sol')
        else:await transport_policy.require_ready(db,run,'openai','gpt-6.1-sol')


async def test_extraction_cancel_releases_attempt_and_context(client,identity,common,monkeypatch):
    from pao.modules.chat.ledger import AccountingEngine,CURRENT_ATTEMPT
    from pao.gateway import OllamaGateway
    from pao.models import TenantModelLease
    rid,_=await create_completed(client,identity,common,monkeypatch)
    class Cancelled:
        provider_name='openai';model_name='gpt-6.1-sol'
        extraction_messages=staticmethod(OllamaGateway.extraction_messages)
        async def extract(self,prompt):
            assert CURRENT_ATTEMPT.get()
            raise asyncio.CancelledError()
    async with Session() as db:
        run=await db.get(Run,rid);gateway=AccountingEngine(Cancelled(),run,source_prefix='memory_extraction',request_key='cancel-probe')
    with pytest.raises(asyncio.CancelledError):await gateway.extract('Synthetic')
    assert CURRENT_ATTEMPT.get() is None
    async with Session() as db:
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.request_key=='cancel-probe'))
        assert attempt.status=='cancelled' and attempt.usage_state=='unknown'
        assert not await db.scalar(select(TenantModelLease.id).where(TenantModelLease.attempt_id==attempt.id,TenantModelLease.status=='active'))


async def test_live_harness_offline_before_consuming_quota(client,identity,common,monkeypatch):
    from gd01_live_acceptance import test_real_chat_and_specialist_two_models
    class Offline(httpx.AsyncBaseTransport):
        def __init__(self,**kwargs):pass
        async def handle_async_request(self,request):
            body=json.loads(request.content)
            answer='PAO_GD01_OK' if body['model']=='gpt-6.1-sol' else '{"text":"Synthetic GD01"}'
            return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':answer},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':200,'completion_tokens':20}})+'\n\ndata: [DONE]\n\n')
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',Offline)
    monkeypatch.setenv('PAO_GD01_LIVE_KEY','SYNTHETIC-ONLY')
    monkeypatch.setenv('PAO_GD01_LIVE_APPROVED','two_synthetic_calls_no_fallback')
    state={'pass':False,'calls':[]}
    await test_real_chat_and_specialist_two_models(client,identity,common,monkeypatch,state)
    assert state['pass'] and len(state['calls'])==2
