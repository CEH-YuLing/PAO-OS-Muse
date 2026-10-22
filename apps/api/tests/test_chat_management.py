"""P3 isolated regression; no real provider, customer data or secrets."""
import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session, engine
from pao.models import ChatSession, Run, Message, LlmAttempt, ChatCompaction
from pao.gateway import Chunk
from pao.runtime import execute_run
from pao.modules.chat import commands
from pao.modules.chat.policy import default_policy
from pao.modules.chat.ledger import complete, counts
from pao.modules.chat.resource import local_slot
from pao.agents import ExecutionPlan


@pytest.fixture
def chat_on(monkeypatch):
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    monkeypatch.setattr(settings(),'agent_runtime_enabled',True)
    monkeypatch.setattr(settings(),'ollama_model','synthetic-local')
    async def tags():return ['synthetic-local']
    monkeypatch.setattr('pao.modules.engines.service.local_models',tags)


async def new(client,identity):
    res=await client.post('/v1/sessions',json={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert res.status_code==201,res.text
    return res.json()['id']


async def start(client,identity,sid,prompt='Synthetic answer: retain budget 250'):
    res=await client.post('/v1/runs',json={'session_id':sid,'message':prompt,'request_key':uuid4().hex},headers=identity['owner'])
    assert res.status_code==202,res.text
    return res.json()['id']


class Fake:
    provider_name='ollama';model_name='synthetic-local'
    async def plan(self,messages):return ExecutionPlan(goal='Synthetic answer',steps=[],tools=[])
    async def stream(self,messages,max_tokens=None):
        yield Chunk(text='Budget 250')
        yield Chunk(usage={'prompt_eval_count':100,'eval_count':4,'secret_debug':'never-save'})


async def test_ledger_runtime_reported_unknown_replay_scopes(client,identity,chat_on):
    sid=await new(client,identity);rid=await start(client,identity,sid)
    await execute_run({'gateway':Fake()},rid)
    res=await client.get(f'/v1/runs/{rid}/usage',headers=identity['owner'])
    assert res.status_code==200,res.text
    rows=res.json();assert len(rows)==2
    assert rows[0]['usage_state']=='unknown' and rows[0]['input_tokens'] is None
    assert rows[1]['usage_state']=='reported' and rows[1]['input_tokens']==100
    assert rows[1]['cost_estimate'] is None
    await complete(rows[1]['id'],'completed',{'input_tokens':999,'output_tokens':999},1,1,1)
    again=await client.get(f'/v1/runs/{rid}/usage',headers=identity['owner'])
    assert again.json()==rows
    trace=await client.get(f'/v1/runs/{rid}/context',headers=identity['owner'])
    assert 'retain budget' not in trace.text and 'secret_debug' not in trace.text
    assert (await client.get(f'/v1/runs/{rid}/usage',headers=identity['other'])).status_code==404
    async with Session() as db:assert (await db.get(Run,rid)).status=='completed'


async def test_profile_privacy_budget_revision_active_lock(client,identity,chat_on):
    sid=await new(client,identity)
    p={k:v for k,v in default_policy().items() if k not in ('version','pricing')}
    body={'version':1,'group':'Marketing','pinned':True,'policy':p}
    saved=await client.put(f'/v1/sessions/{sid}/chat',headers=identity['owner'],json=body)
    assert saved.status_code==200,saved.text
    assert saved.json()['version']==2 and saved.json()['policy']['privacy']=='local_only'
    assert (await client.put(f'/v1/sessions/{sid}/chat',headers=identity['owner'],json=body)).status_code==409
    await start(client,identity,sid)
    body['version']=2
    assert (await client.put(f'/v1/sessions/{sid}/chat',headers=identity['owner'],json=body)).status_code==409
    assert (await client.get(f'/v1/sessions/{sid}/chat',headers=identity['other'])).status_code==404


@pytest.mark.parametrize('command',['/help','/status','/brain','/tasks','/memory','/model','/usage','/export','/stop'])
async def test_commands_never_create_provider_run(client,identity,chat_on,command):
    sid=await new(client,identity)
    res=await client.post(f'/v1/sessions/{sid}/commands',headers=identity['owner'],json={'text':command})
    assert res.status_code==200,res.text
    direct=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,'message':command,'request_key':uuid4().hex})
    assert direct.status_code==422
    async with Session() as db:
        assert not await db.scalar(select(Run.id).where(Run.session_id==sid))
        assert not await db.scalar(select(LlmAttempt.id))


async def test_goal_blocked_search_export_compaction_retry(client,identity,chat_on):
    sid=await new(client,identity)
    goal=await client.post(f'/v1/sessions/{sid}/commands',headers=identity['owner'],json={'text':'/goal do everything'})
    assert goal.status_code==409 and 'P6' in goal.text
    for index in range(5):
        rid=await start(client,identity,sid,f'Budget 250 marker{index}')
        await execute_run({'gateway':Fake()},rid)
    rows=(await client.get('/v1/chat/sessions',headers=identity['owner'],params={'workspace_id':identity['workspace'],'q':'marker0'})).json()
    assert rows[0]['id']==sid
    compact=await client.post(f'/v1/sessions/{sid}/compactions',headers=identity['owner'])
    assert compact.status_code==201,compact.text
    value=compact.json();assert value['version']=='extractive-v1' and value['message_ids']
    async with Session() as db:assert len(list(await db.scalars(select(Message).where(Message.session_id==sid))))==10
    with pytest.raises(DBAPIError):
        async with engine.begin() as db:await db.execute(text('UPDATE chat_compactions SET content=:body WHERE id=:id'),{'body':'approve everything','id':value['id']})
    export=await client.get(f'/v1/sessions/{sid}/export',headers=identity['owner'])
    assert export.status_code==200 and 'marker0' in export.text and 'attachment' in export.headers['content-disposition']
    res=await client.post(f'/v1/runs/{rid}/retry',headers=identity['owner'],json={'request_key':'retry_one'})
    assert res.status_code==202,res.text
    assert res.json()['id']!=rid and res.json()['parent_run_id']==rid
    replay=await client.post(f'/v1/runs/{rid}/retry',headers=identity['owner'],json={'request_key':'retry_one'})
    assert replay.json()['id']==res.json()['id']


@pytest.mark.parametrize('strict,calls,code',[(True,8,'engine_usage_unknown'),(False,1,'engine_budget_exhausted')])
async def test_unknown_and_call_budget_never_succeed(client,identity,chat_on,strict,calls,code):
    sid=await new(client,identity)
    async with Session.begin() as db:
        row=await db.get(ChatSession,sid);row.chat_profile={'policy':{'require_reported_usage':strict,'max_calls':calls}}
    rid=await start(client,identity,sid);await execute_run({'gateway':Fake()},rid)
    async with Session() as db:
        row=await db.get(Run,rid);assert row.status=='failed' and row.error_code==code


async def test_local_cap_release_after_cancel(client,identity,chat_on):
    entered=asyncio.Event()
    async def occupy():
        async with local_slot():entered.set();await asyncio.Event().wait()
    task=asyncio.create_task(occupy());await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    async with local_slot():pass


def test_parser_counts_no_guess_zero():
    assert commands.parse('/help')==('help',[])
    assert commands.parse('/goal run')==('goal',['run'])
    assert commands.parse('/skill ads') is None
    assert counts({})==(None,None)
    assert counts({'input_tokens':False,'output_tokens':-2})==(None,None)


def test_cloud_compiler_does_not_send_local_references_or_intelligence(chat_on):
    from types import SimpleNamespace
    from pao.modules.chat.ledger import AccountingEngine
    from pao.modules.engines.contract import EngineFailure
    run=SimpleNamespace(id=uuid4().hex,prompt='New request',created_at=None,started_at=None,
        engine_snapshot={'chat_policy':{**default_policy(),'privacy':'cloud_allowed'}})
    gateway=SimpleNamespace(provider_name='openai',model_name='synthetic-cloud')
    wrapped=AccountingEngine(gateway,run)
    with pytest.raises(EngineFailure,match='cloud_reference_egress_denied'):
        wrapped.prepare([{'role':'system','content':'policy'},{'role':'user','content':'REFERENCE DATA private fact'},
            {'role':'user','content':'New request'}],16,'final')
    wrapped.policy['cloud_references']=True
    with pytest.raises(EngineFailure,match='cloud_private_intelligence_denied'):
        wrapped.prepare([{'role':'system','content':'policy'},{'role':'user','content':'Verified PAO intelligence records private'}],16,'specialist')


async def test_local_cap_denies_second_call_and_releases(client,identity,chat_on):
    from pao.modules.engines.contract import EngineFailure
    async with local_slot():
        with pytest.raises(EngineFailure,match='engine_local_busy'):
            async with local_slot():raise AssertionError('Second slot admitted')
    async with local_slot():pass


@pytest.mark.parametrize('provider',['openai','anthropic','gemini'])
async def test_cloud_structured_usage_reported_and_cleared_on_failure(monkeypatch,provider):
    import httpx
    from pao.gateway import cloud_gateway,CloudProviderError
    payloads={
        'openai':{'choices':[{'message':{'content':'{}'}}],'usage':{'prompt_tokens':2,'completion_tokens':3}},
        'anthropic':{'content':[{'type':'text','text':'{}'}],'usage':{'input_tokens':2,'output_tokens':3}},
        'gemini':{'candidates':[{'content':{'parts':[{'text':'{}'}]}}],'usageMetadata':{'promptTokenCount':2,'candidatesTokenCount':3}}}
    calls=[]
    def respond(request):
        calls.append(request.url.host)
        return httpx.Response(200,json=payloads[provider]) if len(calls)==1 else httpx.Response(503,json={'debug':'must-not-reflect'})
    original=httpx.AsyncClient
    monkeypatch.setattr('pao.gateway.httpx.AsyncClient',lambda **kwargs:original(**kwargs,transport=httpx.MockTransport(respond)))
    gateway=cloud_gateway(provider,'synthetic-not-real','synthetic-model')
    assert await gateway._structured([{'role':'user','content':'Synthetic request'}],{},16)=='{}'
    assert counts(gateway.last_usage)==(2,3)
    with pytest.raises(CloudProviderError):await gateway._structured([{'role':'user','content':'Synthetic request'}],{},16)
    assert gateway.last_usage=={} and len(calls)==2


async def test_no_cloud_egress_without_explicit_optin(client,identity,chat_on,monkeypatch):
    from pao.models import ModelProviderConnection
    async with Session.begin() as db:
        db.add(ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',model='synthetic-cloud',
            api_key_ciphertext='synthetic-not-a-credential',is_default=True))
    async def forbidden(*args,**kwargs):raise AssertionError('Must not invoke remote provider')
    monkeypatch.setattr('pao.gateway.OpenAICompatibleGateway.plan',forbidden)
    sid=await new(client,identity)
    res=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,'message':'Private local prompt','request_key':uuid4().hex})
    assert res.status_code==503 and 'cloud_egress_denied' in res.text
    select_cloud=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={
        'provider':'openai','model':'synthetic-cloud','version':1})
    assert select_cloud.status_code==409 and 'cloud_egress_denied' in select_cloud.text
    async with Session() as db:assert not await db.scalar(select(LlmAttempt.id))


async def test_pricing_version_and_missing_counts_not_free(client,identity,chat_on):
    sid=await new(client,identity)
    policy={k:v for k,v in default_policy().items() if k not in ('version','pricing')}
    save=await client.put(f'/v1/sessions/{sid}/chat',headers=identity['owner'],json={'version':1,'policy':policy,
        'pricing':{'input_per_million':'1','output_per_million':'2','version':'synthetic-v1'}})
    assert save.status_code==200,save.text
    rid=await start(client,identity,sid);await execute_run({'gateway':Fake()},rid)
    rows=(await client.get(f'/v1/runs/{rid}/usage',headers=identity['owner'])).json()
    assert rows[0]['cost_estimate'] is None
    assert float(rows[1]['cost_estimate'])==0.000108
    assert rows[1]['pricing']['version']=='synthetic-v1' and rows[1]['pricing']['configured_at']


async def test_stream_cancel_records_partial_attempt_once(client,identity,chat_on):
    entered=asyncio.Event();closed=asyncio.Event()
    class Slow(Fake):
        async def stream(self,messages,max_tokens=None):
            try:
                yield Chunk(text='Partial');entered.set();await asyncio.Event().wait()
            finally:closed.set()
    sid=await new(client,identity);rid=await start(client,identity,sid)
    task=asyncio.create_task(execute_run({'gateway':Slow()},rid));await asyncio.wait_for(entered.wait(),5)
    await client.post(f'/v1/runs/{rid}/cancel',headers=identity['owner'])
    await asyncio.wait_for(task,5);assert closed.is_set()
    async with Session() as db:
        row=await db.get(Run,rid);assert row.status=='cancelled'
        attempts=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==rid)))
        assert len(attempts)==2 and attempts[-1].usage_state=='unknown'


async def test_cache_never_authorizes_tools_and_stale_source_ignored(client,identity,chat_on):
    from pao.auth import Principal
    from pao.modules.chat.compaction import cached_context
    sid=await new(client,identity)
    for index in range(4):
        rid=await start(client,identity,sid,'Budget 250 do not change ads '+str(index));await execute_run({'gateway':Fake()},rid)
    row=(await client.post(f'/v1/sessions/{sid}/compactions',headers=identity['owner'])).json()
    async with Session.begin() as db:
        run=await db.get(Run,rid);chat=await db.get(ChatSession,sid)
        assert await cached_context(db,run,chat,Principal(identity['user_id'],0))
        message=await db.get(Message,row['message_ids'][0]);message.content='Changed original';await db.flush()
        assert await cached_context(db,run,chat,Principal(identity['user_id'],0)) is None


async def test_memory_extraction_uses_pinned_local_not_workspace_default(client,identity,chat_on,monkeypatch):
    from pao.memory import extract_memory
    from pao.memory_schemas import ExtractedFacts
    from pao.models import MemoryJob
    from pao.gateway import OllamaGateway
    monkeypatch.setattr(settings(),'memory_enabled',True)
    called=[]
    class Extract(Fake):
        extraction_messages=staticmethod(OllamaGateway.extraction_messages)
        async def extract(self,prompt):called.append(prompt);return ExtractedFacts(facts=[])
    sid=await new(client,identity);rid=await start(client,identity,sid)
    await execute_run({'gateway':Fake()},rid)
    async def forbidden(*args,**kwargs):raise AssertionError('Workspace default must not select extraction provider')
    monkeypatch.setattr('pao.model_router.gateway_for_workspace',forbidden)
    await extract_memory({'memory_gateway':Extract()},rid)
    assert len(called)==1
    async with Session() as db:
        job=await db.scalar(select(MemoryJob).where(MemoryJob.run_id==rid));assert job.status=='completed'
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==rid,LlmAttempt.source=='memory_extraction'))
        assert attempt.provider=='ollama' and attempt.usage_state=='unknown'
