"""Offline protocol + native resource/engine/accounting tests. No real API key."""
import json
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import ModelProviderConnection,User,Workspace,Member,ChatSession,Run,LlmAttempt,TenantModelLease,ToolCall,MemoryJob
from pao.model_router import fetch_model_catalog,fetch_models,encrypt_key
from pao.gateway import cloud_gateway,CloudProviderError,OpenAICompatibleGateway
from pao.modules.installation_ai import openai_effort as contract,service
from pao.modules.installation_ai.models import InstallationAIResource
from pao.modules.engines.service import choose_config,pin_run,checked_snapshot
from pao.modules.engines.contract import EngineFailure
from pao.modules.connections.model_fence import check_run


@pytest.mark.parametrize('model,levels',[
    ('gpt-6.1-sol',['low','medium','high','xhigh','max']),
    ('gpt-6-astra',['low','medium','high','xhigh','max']),
    ('gpt-6-luna',['none','low','medium','high','xhigh','max'])])
def test_exact_reviewed_models(model,levels):
    assert contract.metadata(model)['reasoning_efforts']==levels
    for effort in levels:contract.validate(model,effort)
    contract.validate(model,None)
    changed=contract.metadata(model);changed['reasoning_efforts'].clear()
    assert contract.metadata(model)['reasoning_efforts']==levels


@pytest.mark.parametrize('model',['gpt-test','GPT-6.1-sol','gpt-6.1-sol-2099-01-01','gpt-6.1-sol:custom','ft:gpt-6.1-sol','openai/gpt-6.1-sol'])
def test_unknown_models_never_inherit_effort_by_prefix(model):
    assert contract.metadata(model)=={'reasoning_efforts':[],'default_effort':None}
    with pytest.raises(ValueError):contract.validate(model,'high')


@pytest.mark.parametrize('effort',['none','minimal','pro','ultra','HIGH',True,{},[]])
def test_invalid_effort_is_rejected_without_io(effort):
    with pytest.raises(ValueError):contract.validate('gpt-6.1-sol',effort)


async def test_catalog_only_annotates_returned_ids_and_does_not_trust_extra_fields():
    seen=[]
    def response(request):
        seen.append(request.method);assert request.url=='https://api.openai.com/v1/models'
        return httpx.Response(200,json={'data':[{'id':'gpt-6.1-sol'},
            {'id':'unknown-model','reasoning':{'supported_efforts':['high']}},{'id':'gpt-6-luna'}]})
    transport=httpx.MockTransport(response)
    result=await fetch_model_catalog('openai','SYNTHETIC',transport)
    assert [v['model'] for v in result]==['gpt-6-luna','gpt-6.1-sol','unknown-model']
    assert result[-1]['reasoning_efforts']==[] and result[1]['default_effort']=='medium'
    assert 'gpt-6-astra' not in [v['model'] for v in result]  # Never invent entitlement.
    assert seen==['GET']
    assert await fetch_models('openai','SYNTHETIC',transport)==[v['model'] for v in result]


@pytest.mark.parametrize('effort',[None,'low','high','max'])
@pytest.mark.parametrize('mode',['stream','structured'])
async def test_wire_payload_uses_real_openai_parameter_and_same_budget(monkeypatch,effort,mode):
    real=httpx.AsyncClient;seen=[]
    def response(request):
        body=json.loads(request.content);seen.append(body)
        assert str(request.url)=='https://api.openai.com/v1/chat/completions'
        assert body['model']=='gpt-6.1-sol' and body['max_completion_tokens']==128
        assert not any(v in body for v in ('temperature','max_tokens','reasoning','tools','tool_choice','service_tier'))
        assert body.get('reasoning_effort')==effort and ('reasoning_effort' in body)==(effort is not None)
        if mode=='structured':return httpx.Response(200,json={'choices':[{'message':{'content':'{"ok":true}'}}],
            'usage':{'prompt_tokens':20,'completion_tokens':15,'completion_tokens_details':{'reasoning_tokens':10}}})
        return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':'OK','reasoning_content':'PRIVATE'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':20,'completion_tokens':15,'completion_tokens_details':{'reasoning_tokens':10}}})+'\n\ndata: [DONE]\n\n')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(response),**kw))
    gateway=cloud_gateway('openai','SYNTHETIC','gpt-6.1-sol',reasoning_effort=effort)
    if mode=='stream':
        chunks=[v async for v in gateway.stream([{'role':'user','content':'Synthetic'}],128)]
        assert ''.join(v.text for v in chunks)=='OK' and chunks[-1].usage['completion_tokens']==15
    else:assert await gateway._structured([{'role':'user','content':'Synthetic'}],{'type':'object'},128)=='{"ok":true}'
    assert len(seen)==1


def test_old_unselected_models_and_openrouter_keep_their_payload_contract():
    old={'model':'gpt-test','max_tokens':64,'temperature':0.4}
    assert cloud_gateway('openai','SYNTHETIC','gpt-test')._reasoning(dict(old))==old
    value=cloud_gateway('openrouter','SYNTHETIC','gpt-6.1-sol',reasoning_effort='high')._reasoning(dict(old))
    assert value=={'model':'gpt-test','max_tokens':64,'reasoning':{'effort':'high'}}
    with pytest.raises(CloudProviderError):cloud_gateway('openai','SYNTHETIC','gpt-test',reasoning_effort='high')


@pytest.mark.parametrize('body',[{'tools':[]},{'functions':[]},{'tool_choice':'auto'},{'reasoning':{'mode':'pro'}},
    {'max_tokens':64,'max_completion_tokens':64}])
def test_effort_does_not_enable_tools_or_two_token_limits(body):
    with pytest.raises(ValueError):contract.payload('gpt-6.1-sol','high',dict(body))


async def test_provider_failure_is_redacted_and_not_retried(monkeypatch):
    real=httpx.AsyncClient;seen=[]
    def response(request):seen.append(str(request.url));return httpx.Response(429,json={'error':'SYNTHETIC_SECRET'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(response),**kw))
    with pytest.raises(CloudProviderError,match='^openai_request_failed$'):
        _=[v async for v in cloud_gateway('openai','SYNTHETIC','gpt-6.1-sol',reasoning_effort='high').stream([])]
    assert len(seen)==1


@pytest.fixture
async def resource(client,identity,monkeypatch):
    for name in ('installation_ai_enabled','engine_contract_enabled','chat_features_enabled'):
        monkeypatch.setattr(settings(),name,True)
    monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
    async with Session.begin() as db:
        source=ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',model='gpt-6.1-sol',
            api_key_ciphertext=encrypt_key('SYNTHETIC'),status='connected',is_default=False)
        db.add(source);await db.flush()
        await service.capture(db,identity['user_id'],identity['workspace'],source.id,'api',
            [{'model':v,**contract.metadata(v)} for v in ('gpt-6.1-sol','gpt-6-luna','unknown-model')])
        row=await db.scalar(select(InstallationAIResource));rid=row.id;sid=source.id
    response=await client.put('/v1/installation-ai/'+rid,headers=identity['owner'],json={
        'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'is_default':True,'default_model':'gpt-6.1-sol'})
    assert response.status_code==200,response.text
    return rid,sid


@pytest.mark.parametrize('role',['operator','viewer'])
async def test_native_chat_model_selection_and_accounting_end_to_end(client,identity,resource,monkeypatch,role):
    from pao.runtime import execute_run
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        workspace=Workspace(name='Independent OpenAI caller');db.add(workspace);await db.flush();wid=workspace.id
        db.add(Member(workspace_id=wid,user_id=uid,role=role))
    response=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':wid})
    assert response.status_code==201,response.text
    sid=response.json()['id']
    catalog=await client.get('/v1/engines',params={'workspace_id':wid},headers=identity['other'])
    assert catalog.status_code==200 and catalog.json()['scope']=='installation'
    invalid=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['other'],json={
        'provider':'openai','model':'gpt-6.1-sol','version':1,'installation_resource_id':resource[0],'reasoning_effort':'none'})
    assert invalid.status_code==409
    choice=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['other'],json={
        'provider':'openai','model':'gpt-6.1-sol','version':1,'installation_resource_id':resource[0],'reasoning_effort':'high'})
    assert choice.status_code==200,choice.text
    created=await client.post('/v1/runs',headers=identity['other'],json={'session_id':sid,'request_key':uuid4().hex,'message':'Synthetic prompt'})
    assert created.status_code==202,created.text
    rid=created.json()['id'];seen=[];real=httpx.AsyncClient
    def response(request):
        body=json.loads(request.content);seen.append(body)
        assert body['model']=='gpt-6.1-sol' and body['reasoning_effort']=='high'
        assert 'max_completion_tokens' in body and 'max_tokens' not in body and 'temperature' not in body
        return httpx.Response(200,text='data: '+json.dumps({'choices':[{'delta':{'content':'SYNTHETIC_OK'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':20,'completion_tokens':15,'completion_tokens_details':{'reasoning_tokens':10}}})+'\n\ndata: [DONE]\n\n')
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(response),**kw))
    await execute_run({},rid)
    async with Session() as db:
        run=await db.get(Run,rid);assert run.status=='completed' and run.response=='SYNTHETIC_OK',run.error_code
        assert checked_snapshot(run.engine_snapshot)['reasoning_effort']=='high'
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==rid))
        assert attempt.user_id==uid and attempt.workspace_id==wid and attempt.model=='gpt-6.1-sol'
        assert attempt.status=='completed' and attempt.input_tokens==20 and attempt.output_tokens==15
        assert attempt.usage_state=='reported' and len(seen)==1
        assert not await db.scalar(select(TenantModelLease.id).where(TenantModelLease.attempt_id==attempt.id,TenantModelLease.status=='active'))
        assert await db.scalar(select(func.count()).select_from(ToolCall))==0
        assert await db.scalar(select(func.count()).select_from(MemoryJob))==0
        assert (run.engine_snapshot.get('interaction_mode')=='read_only_ai')==(role=='viewer')
    assert (await client.get(f'/v1/runs/{rid}',headers=identity['owner'])).status_code==404


async def test_revoke_and_corrupted_capability_cannot_bypass_server_contract(client,identity,resource):
    async with Session.begin() as db:
        row=await db.get(InstallationAIResource,resource[0]);row.catalog=[{'model':'unknown-model','reasoning_efforts':['high']}]
        with pytest.raises(EngineFailure,match='ai_effort_not_supported'):
            await choose_config(db,identity['workspace'],'openai','unknown-model',actor_id=identity['user_id'],
                installation_resource_id=resource[0],reasoning_effort='high')


async def test_specialist_has_independent_model_effort_and_queued_revocation(client,identity,resource):
    async with Session.begin() as db:
        original=await service.config(db,identity['workspace'],identity['user_id'],None,resource[0],'gpt-6.1-sol','high')
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
            engine_config=original,chat_profile={'policy':{'privacy':'cloud_allowed'}})
        db.add(chat);await db.flush()
        run=SimpleNamespace(engine_snapshot=None,workspace_id=identity['workspace'],brain_id=None,brain_context=None,
            studio_snapshot={'agent':{'payload':{'model_preference':{'provider':'openai','model':'gpt-6-luna',
                'installation_resource_id':resource[0],'reasoning_effort':'low'}}},
                'skill':{'payload':{'token_budget':2048,'output_tokens':128}}})
        await pin_run(db,run,chat)
        assert run.engine_snapshot['model']=='gpt-6-luna' and run.engine_snapshot['reasoning_effort']=='low'
        assert chat.engine_config['model']=='gpt-6.1-sol' and chat.engine_config['reasoning_effort']=='high'
        await service.check(db,run,chat,run.engine_snapshot)
        (await db.get(InstallationAIResource,resource[0])).enabled=False;await db.flush()
        with pytest.raises(EngineFailure):await service.check(db,run,chat,run.engine_snapshot)
