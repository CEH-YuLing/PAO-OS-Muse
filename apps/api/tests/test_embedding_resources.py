"""Real shared SQL pool, local fixtures only; no synthetic Run or live models."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func,text,update
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import Workspace,Member,User,Memory,Run,LlmAttempt,TenantModelLease,now
from pao.modules.connections import resources
from pao.modules.connections.embedding_resources import embed
from pao.modules.engines.contract import EngineFailure
from test_tenant_model_resources import configure
from test_memory import memory_on,add


class Fake:
    def __init__(self):self.calls=0
    async def embed(self,value):self.calls+=1;return [1.0]+[0.0]*767


async def embedding(identity,fake,**kwargs):
    return await embed('Private synthetic fact',workspace_id=identity['workspace'],
        actor_id=identity['user_id'],purpose='fixture',gateway=fake,**kwargs)


async def test_default_policy_reserves_without_run_or_attempt_and_replay_denied(client,identity):
    fake=Fake();key='owned:'+uuid4().hex
    vector,model=await embedding(identity,fake,request_key=key)
    assert len(vector)==768 and model==settings().embedding_model
    with pytest.raises(EngineFailure,match='tenant_resource_replay_denied'):
        await embedding(identity,fake,request_key=key)
    async with Session() as db:
        rows=list(await db.scalars(select(TenantModelLease)))
        assert len(rows)==1 and rows[0].status=='released' and rows[0].attempt_id is None
        assert rows[0].embedding_pin['model']==model and 'Private synthetic fact' not in str(rows[0].embedding_pin)
        assert not await db.scalar(select(func.count()).select_from(Run))
        assert not await db.scalar(select(func.count()).select_from(LlmAttempt))
        usage=await resources.usage(db,identity['workspace'])
        assert usage['calls']==usage['unknown_usage_calls']==1 and usage['active_models']==0
        assert usage['reserved_or_reported_tokens']==22 and usage['billing_amount'] is None
    assert fake.calls==1


async def test_sme_a_exhaustion_does_not_block_sme_b(client,identity):
    assert (await configure(client,identity,calls=1)).status_code==200
    fake=Fake();await embedding(identity,fake)
    with pytest.raises(EngineFailure,match='tenant_model_daily_calls_exhausted'):await embedding(identity,fake)
    async with Session.begin() as db:
        other=Workspace(name='SME B embedding');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    await embed('Separate fact',workspace_id=wid,actor_id=identity['user_id'],purpose='fixture',gateway=fake)
    assert fake.calls==2


async def test_shared_concurrent_slot_and_cancel_no_refund(client,identity):
    assert (await configure(client,identity,slots=1)).status_code==200
    started=asyncio.Event();stop=asyncio.Event()
    class Slow(Fake):
        async def embed(self,value):self.calls+=1;started.set();await stop.wait();return [1.0]+[0.0]*767
    fake=Slow();task=asyncio.create_task(embedding(identity,fake))
    try:
        await asyncio.wait_for(started.wait(),5)
        with pytest.raises(EngineFailure,match='tenant_model_concurrency_exhausted'):await embedding(identity,Fake())
        async with Session.begin() as db:
            await resources.lock(db,identity['workspace'])
            with pytest.raises(EngineFailure,match='tenant_model_concurrency_exhausted'):
                await resources.admit(db,identity['workspace'],identity['user_id'],'management_probe',uuid4().hex,96)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        async with Session() as db:
            usage=await resources.usage(db,identity['workspace'])
            assert usage['calls']==1 and usage['active_models']==0 and usage['reserved_or_reported_tokens']>0
    finally:
        stop.set()
        if not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)


@pytest.mark.parametrize('kind',['timeout','invalid','provider'])
async def test_failed_embedding_releases_slot_and_retains_debit(client,identity,monkeypatch,kind):
    monkeypatch.setattr(settings(),'memory_timeout_seconds',.03)
    class Bad:
        async def embed(self,value):
            if kind=='timeout':await asyncio.sleep(.2)
            if kind=='provider':raise RuntimeError('private upstream diagnostic')
            return [0.0]*768
    with pytest.raises((TimeoutError,EngineFailure,RuntimeError)):await embedding(identity,Bad())
    async with Session() as db:
        row=await db.scalar(select(TenantModelLease));assert row.status=='released'
        assert (await resources.usage(db,identity['workspace']))['calls']==1


@pytest.mark.parametrize('kind',['member','actor','brand'])
async def test_scope_denied_before_adapter(client,identity,kind):
    fake=Fake();params={}
    async with Session.begin() as db:
        if kind=='member':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer';params['write']=True
        elif kind=='actor':(await db.get(User,identity['user_id'])).active=False
        else:params['brand_id']=str(uuid4())
    with pytest.raises(EngineFailure):await embedding(identity,fake,**params)
    assert fake.calls==0
    async with Session() as db:assert not await db.scalar(select(func.count()).select_from(TenantModelLease))


async def test_late_revocation_prevents_result_and_memory_publication(client,identity,memory_on,monkeypatch):
    from pao.gateway import OllamaGateway
    async def revoke(self,value):
        async with Session.begin() as db:(await db.get(User,identity['user_id'])).active=False
        return [1.0]+[0.0]*767
    monkeypatch.setattr(OllamaGateway,'embed',revoke)
    response=await add(client,identity)
    assert response.status_code==403 and 'embedding_access_revoked' in response.text
    async with Session() as db:
        assert not await db.scalar(select(func.count()).select_from(Memory))
        assert (await db.scalar(select(TenantModelLease))).status=='released'


async def test_memory_quota_degrades_to_lexical_without_provider(client,identity,memory_on,monkeypatch):
    from pao.gateway import OllamaGateway
    assert (await configure(client,identity,calls=1)).status_code==200
    assert (await add(client,identity)).status_code==201
    async def forbidden(*args):raise AssertionError('No embed beyond quota')
    monkeypatch.setattr(OllamaGateway,'embed',forbidden)
    response=await client.post('/v1/memory/search',headers=identity['owner'],json={
        'workspace_id':identity['workspace'],'query':'Malaysia'})
    assert response.status_code==200 and response.json()['degraded'] and len(response.json()['items'])==1
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TenantModelLease))==1


async def test_pin_and_history_immutable_sql(client,identity):
    await embedding(identity,Fake())
    async with Session() as db:row=await db.scalar(select(TenantModelLease));lid=row.id
    for mutation in ('pin','delete'):
        with pytest.raises(DBAPIError):
            async with Session.begin() as db:
                if mutation=='pin':await db.execute(update(TenantModelLease).where(TenantModelLease.id==lid).values(embedding_pin={'model':'other'}))
                else:await db.execute(text('DELETE FROM tenant_model_leases WHERE id=:id'),{'id':lid})


@pytest.mark.parametrize('url',['https://example.test','http://user:secret@localhost:11434','http://localhost:11434/path'])
async def test_non_loopback_or_credentialed_endpoint_denied_before_io(client,identity,monkeypatch,url):
    monkeypatch.setattr(settings(),'ollama_url',url);fake=Fake()
    with pytest.raises(EngineFailure,match='engine_local_endpoint_invalid'):await embedding(identity,fake)
    assert fake.calls==0


async def test_native_gateway_pins_model_and_url_across_setting_change(client,identity,monkeypatch):
    from pao.gateway import OllamaGateway
    observed=[]
    async def fake_embed(self,value):
        monkeypatch.setattr(settings(),'embedding_model','changed-after-admission')
        monkeypatch.setattr(settings(),'ollama_url','http://127.0.0.1:11435')
        observed.append((self.base_url,self._embedding_model));return [1.0]+[0.0]*767
    monkeypatch.setattr(OllamaGateway,'embed',fake_embed)
    expected=(settings().ollama_url,settings().embedding_model)
    _,model=await embed('Pinned request',workspace_id=identity['workspace'],actor_id=identity['user_id'],purpose='fixture')
    assert observed==[expected] and model==expected[1]


async def test_expired_unknown_never_resends_same_key(client,identity):
    key=uuid4().hex;stamp=now()-timedelta(seconds=20)
    import hashlib
    async with Session.begin() as db:
        db.add(TenantModelLease(workspace_id=identity['workspace'],actor_id=identity['user_id'],kind='embedding',
            request_key=hashlib.sha256(key.encode()).hexdigest(),policy_version=0,reserved_tokens=10,
            embedding_pin={'model':'fixture'},created_at=stamp,expires_at=stamp+timedelta(seconds=15)))
    fake=Fake()
    with pytest.raises(EngineFailure,match='tenant_resource_replay_denied'):await embedding(identity,fake,request_key=key)
    await embedding(identity,fake) # fresh explicit invocation reaps expired slot, not old debit
    async with Session() as db:
        usage=await resources.usage(db,identity['workspace'])
        assert usage['calls']==2 and usage['active_models']==0 and usage['unknown_usage_calls']==2
        assert await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.status=='expired'))==1
    assert fake.calls==1


async def test_token_limit_before_adapter(client,identity):
    assert (await configure(client,identity,tokens=1)).status_code==200
    fake=Fake()
    with pytest.raises(EngineFailure,match='tenant_model_daily_tokens_exhausted'):await embedding(identity,fake)
    assert fake.calls==0


async def test_memory_query_late_revocation_does_not_lexically_disclose(client,identity,memory_on,monkeypatch):
    from pao.gateway import OllamaGateway
    assert (await add(client,identity)).status_code==201
    async def revoke(self,value):
        async with Session.begin() as db:await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
        return [1.0]+[0.0]*767
    monkeypatch.setattr(OllamaGateway,'embed',revoke)
    response=await client.post('/v1/memory/search',headers=identity['owner'],json={'workspace_id':identity['workspace'],'query':'Malaysia'})
    assert response.status_code==403 and 'Malaysia' not in response.text


async def test_memory_extraction_native_adapter_uses_queued_embedding_pin_once(client,identity,memory_on,monkeypatch):
    from pao.gateway import OllamaGateway
    from pao.memory import extract_memory
    from pao.memory_schemas import ExtractedFacts,Fact
    from pao.runtime import execute_run
    from test_memory import run_chat,Gateway
    fact='Thị trường mục tiêu là Malaysia.'
    _,rid=await run_chat(client,identity,fact)
    expected=(settings().ollama_url,settings().embedding_model)
    await execute_run({'gateway':Gateway()},rid)
    observed=[]
    async def facts(self,prompt):return ExtractedFacts(facts=[Fact(key='market',value=prompt,importance=4)])
    async def pinned(self,value):observed.append((self.base_url,self._embedding_model));return [1.0]+[0.0]*767
    monkeypatch.setattr(OllamaGateway,'extract',facts);monkeypatch.setattr(OllamaGateway,'embed',pinned)
    monkeypatch.setattr(settings(),'embedding_model','changed-new-request-only')
    monkeypatch.setattr(settings(),'ollama_url','http://127.0.0.1:11435')
    await extract_memory({},rid);await extract_memory({},rid)
    assert observed==[expected]
    async with Session() as db:
        row=await db.scalar(select(Memory));assert row.embedding_model==expected[1]
        assert await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.kind=='embedding'))==1
        usage=await resources.usage(db,identity['workspace'])
        assert usage['calls']==3 # final, extraction, fact embedding; no double invocation charge
