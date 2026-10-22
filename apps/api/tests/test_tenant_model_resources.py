"""Real PostgreSQL admission/concurrency, synthetic gateways, no external calls."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from cryptography.fernet import Fernet
from pao.config import settings
from pao.db import Session,engine
from pao.models import (ChatSession,Run,Workspace,Member,LlmAttempt,TenantModelLease,
    ModelProviderConnection,now)
from pao.gateway import Chunk
from pao.modules.connections import resources
from pao.modules.chat.ledger import reserve,complete,AccountingEngine
from pao.modules.engines.contract import EngineFailure
from pao.model_router import encrypt_key


def route(wid):return f'/v1/workspaces/{wid}/resources/models'


async def configure(client,identity,*,wid=None,version=0,calls=50,tokens=100000,slots=2):
    return await client.put(route(wid or identity['workspace']),headers=identity['owner'],json={
        'expected_version':version,'daily_model_calls':calls,'daily_model_tokens':tokens,'concurrent_models':slots})


async def run_row(identity,wid=None):
    async with Session.begin() as db:
        chat=ChatSession(workspace_id=wid or identity['workspace'],user_id=identity['user_id'])
        db.add(chat);await db.flush()
        run=Run(workspace_id=chat.workspace_id,session_id=chat.id,request_key=uuid4().hex,
            prompt='Synthetic request',status='running',started_at=now())
        db.add(run);await db.flush();return run


async def book(run,tokens=100,key=None):
    return await reserve(run.id,key or uuid4().hex,'chat_final','ollama','fixture-model',{'estimated_tokens':tokens},16)


async def second(identity):
    async with Session.begin() as db:
        row=Workspace(name='Independent SME');db.add(row);await db.flush()
        db.add(Member(workspace_id=row.id,user_id=identity['user_id'],role='owner'));return row.id


async def status(client,identity,wid=None):
    result=await client.get(route(wid or identity['workspace']),headers=identity['owner'])
    assert result.status_code==200,result.text
    return result.json()


async def test_defaults_no_billing_no_credentials_no_store(client,identity):
    res=await client.get(route(identity['workspace']),headers=identity['owner'])
    data=res.json();assert res.status_code==200 and res.headers['cache-control']=='no-store'
    assert data['model_policy']=={'version':0,**resources.DEFAULTS}
    assert data['usage']['billing_amount'] is None and data['usage']['provider_subscription_remaining'] is None
    assert data['grants_authorized'] is False and 'model_metadata_requests' not in data['pending_coverage']
    assert {'unaccounted_legacy_denied','memory_embeddings','knowledge_embeddings'}<=set(data['coverage']) and data['pending_coverage']==[]
    assert not any(word in res.text for word in ('api_key','ciphertext','prompt','email'))


async def test_invalid_secret_and_oversized_json_never_echoed(client,identity):
    marker='fixture-redaction-marker-not-key'
    response=await client.put(route(identity['workspace']),headers=identity['owner'],json={'api_key':marker})
    assert response.status_code==422 and marker not in response.text
    assert response.headers['cache-control']=='no-store'
    response=await client.put(route(identity['workspace']),
        headers={**identity['owner'],'Content-Type':'application/json'},
        content='{"api_key":"'+marker*500+'"}')
    assert response.status_code==413 and marker not in response.text


@pytest.mark.parametrize('method',['get','put'])
async def test_manager_only_and_foreign_unknown_scopes(client,identity,method):
    kwargs={'json':{'expected_version':0,'daily_model_calls':10,'daily_model_tokens':1000,'concurrent_models':1}} if method=='put' else {}
    for headers,code in (({},401),(identity['other'],403),(identity['outsider'],404)):
        res=await getattr(client,method)(route(identity['workspace']),headers=headers,**kwargs)
        assert res.status_code==code,res.text
    assert (await getattr(client,method)(route(str(uuid4())),headers=identity['owner'],**kwargs)).status_code==404


@pytest.mark.parametrize('field,value',[('daily_model_calls',True),('daily_model_calls',10001),
    ('daily_model_tokens',0),('daily_model_tokens',10000001),('concurrent_models',9),('concurrent_models',0)])
async def test_host_ceiling_strict_dto(client,identity,field,value):
    body={'expected_version':0,'daily_model_calls':10,'daily_model_tokens':1000,'concurrent_models':1,field:value}
    assert (await client.put(route(identity['workspace']),headers=identity['owner'],json=body)).status_code==422


async def test_policy_cas_concurrent_does_not_reset_usage(client,identity):
    results=await asyncio.gather(configure(client,identity,calls=4),configure(client,identity,calls=6))
    assert sorted(row.status_code for row in results)==[200,409]
    run=await run_row(identity);aid=await book(run)
    await complete(aid,'completed',{},0,None,1)
    changed=await configure(client,identity,version=1,calls=1)
    assert changed.status_code==200 and changed.json()['model_policy']['version']==2
    assert changed.json()['usage']['calls']==1
    with pytest.raises(EngineFailure,match='tenant_model_daily_calls_exhausted'):await book(await run_row(identity))


async def test_atomic_admission_limits_same_sme_but_not_other(client,identity):
    wid=await second(identity)
    assert (await configure(client,identity,slots=1)).status_code==200
    runs=[await run_row(identity) for _ in range(8)]
    results=await asyncio.gather(*(book(run) for run in runs),return_exceptions=True)
    admitted=[row for row in results if isinstance(row,str)]
    assert len(admitted)==1 and all(isinstance(row,str) or str(row)=='tenant_model_concurrency_exhausted' for row in results)
    other=await book(await run_row(identity,wid))
    assert (await status(client,identity,wid))['usage']['calls']==1
    await complete(admitted[0],'cancelled',{},0,None,1)
    assert isinstance(await book(runs[0]),str)
    await complete(other,'completed',{},0,None,1)


async def test_unknown_partial_overage_conservative_no_double_complete(client,identity):
    run=await run_row(identity);aid=await book(run,100)
    await complete(aid,'completed',{},0,None,1)
    data=(await status(client,identity))['usage'];assert data['reserved_or_reported_tokens']==116
    assert data['unknown_usage_calls']==1 and data['active_models']==0
    await complete(aid,'completed',{'input_tokens':99999,'output_tokens':99999},1,1,1)
    assert (await status(client,identity))['usage']==data
    aid=await book(run,100);await complete(aid,'failed',{'input_tokens':200,'output_tokens':20},0,None,1)
    assert (await status(client,identity))['usage']['reserved_or_reported_tokens']==336
    assert (await configure(client,identity,tokens=336)).status_code==200
    with pytest.raises(EngineFailure,match='tenant_model_daily_tokens_exhausted'):await book(run)


async def test_request_replay_never_reserves_again(client,identity):
    run=await run_row(identity);aid=await book(run,key='fixed-invocation')
    await complete(aid,'cancelled',{},0,None,1)
    with pytest.raises(EngineFailure,match='engine_attempt_replay_denied'):await book(run,key='fixed-invocation')
    assert (await status(client,identity))['usage']['calls']==1


async def test_durable_restart_expiry_keeps_unknown_charge_and_old_pin(client,identity):
    # Insert an already-expired reservation as a lost worker fixture. Native
    # immutable trigger intentionally prevents moving a live deadline backwards.
    run=await run_row(identity);stamp=now()-timedelta(minutes=8)
    async with Session.begin() as db:
        attempt=LlmAttempt(workspace_id=identity['workspace'],user_id=identity['user_id'],session_id=run.session_id,
            run_id=run.id,request_key='lost-worker',source='chat_final',provider='ollama',model='fixture-model',
            estimated_input_tokens=100,reserved_output_tokens=16,trace={},created_at=stamp)
        db.add(attempt);await db.flush();aid=attempt.id
        db.add(TenantModelLease(workspace_id=identity['workspace'],actor_id=identity['user_id'],kind='llm',
            request_key=aid,attempt_id=aid,policy_version=0,reserved_tokens=0,created_at=stamp,
            expires_at=stamp+timedelta(seconds=resources.LEASE_SECONDS)))
    await engine.dispose()  # Reopen durable state, not an in-memory reset.
    assert isinstance(await book(await run_row(identity)),str)
    async with Session() as db:
        row=await db.get(LlmAttempt,aid);lease=await db.scalar(select(TenantModelLease).where(TenantModelLease.attempt_id==aid))
        assert row.status=='failed' and row.usage_state=='unknown' and row.input_tokens is None
        assert lease.status=='expired' and lease.request_key==aid
    await complete(aid,'completed',{'input_tokens':1,'output_tokens':1},1,1,1)
    assert (await status(client,identity))['usage']['reserved_or_reported_tokens']==232


@pytest.mark.parametrize('statement',["UPDATE tenant_model_leases SET reserved_tokens=1 WHERE id=:id",
    "UPDATE tenant_model_leases SET expires_at=expires_at+interval '1 second' WHERE id=:id",
    "DELETE FROM tenant_model_leases WHERE id=:id"])
async def test_sql_history_immutable(client,identity,statement):
    aid=await book(await run_row(identity))
    async with Session() as db:lease=await db.scalar(select(TenantModelLease.id).where(TenantModelLease.attempt_id==aid))
    with pytest.raises(DBAPIError):
        async with engine.begin() as db:await db.execute(text(statement),{'id':lease})


async def test_sql_foreign_attempt_scope_refused(client,identity):
    aid=await book(await run_row(identity));wid=await second(identity)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            stamp=now();db.add(TenantModelLease(workspace_id=wid,actor_id=identity['user_id'],kind='llm',
                request_key=uuid4().hex,attempt_id=aid,policy_version=0,reserved_tokens=0,
                created_at=stamp,expires_at=stamp+timedelta(seconds=240)))


async def test_accounting_denied_never_calls_gateway(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    assert (await configure(client,identity,tokens=1)).status_code==200
    class Never:
        provider_name='ollama';model_name='fixture-model'
        async def stream(self,*args,**kwargs):raise AssertionError('Denied invocation');yield
    engine=AccountingEngine(Never(),await run_row(identity))
    with pytest.raises(EngineFailure,match='tenant_model_daily_tokens_exhausted'):
        async for _ in engine.stream([{'role':'system','content':'Synthetic policy'},
            {'role':'user','content':'Synthetic request'}]):pass
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(LlmAttempt))==0


async def test_timeout_releases_slot_but_keeps_charge(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    monkeypatch.setattr(resources,'CALL_TIMEOUT',.5)
    class Slow:
        provider_name='ollama';model_name='fixture-model'
        async def stream(self,*args,**kwargs):await asyncio.sleep(2);yield Chunk(text='Never')
    wrapped=AccountingEngine(Slow(),await run_row(identity))
    with pytest.raises(TimeoutError):
        async for _ in wrapped.stream([{'role':'system','content':'Synthetic policy'},
            {'role':'user','content':'Synthetic request'}]):pass
    data=(await status(client,identity))['usage']
    assert data['calls']==1 and data['active_models']==0 and data['reserved_or_reported_tokens']>0


async def probe_fixture(identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        db.add(ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',
            api_key_ciphertext=encrypt_key('fixture-never-external'),model='fixture-model'))


async def test_native_probe_denied_before_decrypt_and_network(client,identity,monkeypatch):
    await probe_fixture(identity,monkeypatch)
    assert (await configure(client,identity,tokens=1)).status_code==200
    def never(*args):raise AssertionError('Quota deny accessed credential/provider')
    monkeypatch.setattr('pao.model_api.decrypt_key',never);monkeypatch.setattr('pao.model_api.cloud_gateway',never)
    res=await client.post('/v1/model-providers/openai/test',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert res.status_code==429 and res.json()['detail']=='tenant_model_daily_tokens_exhausted'
    assert (await status(client,identity))['usage']['calls']==0
    async with Session() as db:
        row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==identity['workspace']))
        assert row.status=='connected' and row.last_checked_at is None


async def test_native_probe_charge_and_release_unknown(client,identity,monkeypatch):
    await probe_fixture(identity,monkeypatch)
    class Probe:
        provider_name='openai';model_name='fixture-model'
        async def stream(self,*args,**kwargs):yield Chunk(text='PAO OK')
    monkeypatch.setattr('pao.model_api.cloud_gateway',lambda *args:Probe())
    res=await client.post('/v1/model-providers/openai/test',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert res.status_code==200,res.text
    usage=(await status(client,identity))['usage']
    assert usage['calls']==1 and usage['reserved_or_reported_tokens']==96
    assert usage['unknown_usage_calls']==1 and usage['active_models']==0


async def test_probe_model_changed_late_denies_publication_releases_but_no_refund(client,identity,monkeypatch):
    await probe_fixture(identity,monkeypatch)
    started,release=asyncio.Event(),asyncio.Event()
    class Probe:
        provider_name='openai';model_name='fixture-model'
        async def stream(self,*args,**kwargs):
            started.set();await release.wait();yield Chunk(text='PAO OK')
    monkeypatch.setattr('pao.model_api.cloud_gateway',lambda *args:Probe())
    task=asyncio.create_task(client.post('/v1/model-providers/openai/test',
        params={'workspace_id':identity['workspace']},headers=identity['owner']))
    try:
        await asyncio.wait_for(started.wait(),5)
        async with Session.begin() as db:
            row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==identity['workspace']))
            row.model='other-fixture-model'
        release.set();res=await asyncio.wait_for(task,5);assert res.status_code==403
        usage=(await status(client,identity))['usage']
        assert usage['calls']==1 and usage['active_models']==0 and usage['reserved_or_reported_tokens']==96
    finally:release.set();await asyncio.gather(task,return_exceptions=True)


async def test_active_policy_reduction_does_not_kill_or_reset_existing_reservations(client,identity):
    assert (await configure(client,identity,slots=2)).status_code==200
    first=await book(await run_row(identity));second=await book(await run_row(identity))
    changed=await configure(client,identity,version=1,slots=1)
    assert changed.status_code==200 and changed.json()['usage']['active_models']==2
    with pytest.raises(EngineFailure,match='tenant_model_concurrency_exhausted'):await book(await run_row(identity))
    await complete(first,'cancelled',{},0,None,1)
    with pytest.raises(EngineFailure,match='tenant_model_concurrency_exhausted'):await book(await run_row(identity))
    await complete(second,'completed',{},0,None,1)
    assert isinstance(await book(await run_row(identity)),str)


async def test_configured_tenant_cannot_use_unaccounted_legacy_fallback(client,identity,monkeypatch):
    from pao.model_router import gateway_for_workspace
    assert (await configure(client,identity)).status_code==200
    def never(*args):raise AssertionError('Legacy bypass decrypted/resolved provider')
    monkeypatch.setattr('pao.model_router.decrypt_key',never)
    async with Session() as db:
        with pytest.raises(EngineFailure,match='tenant_resource_accounting_required'):
            await gateway_for_workspace(db,identity['workspace'])


async def test_probe_and_chat_share_same_tenant_concurrency(client,identity,monkeypatch):
    await probe_fixture(identity,monkeypatch)
    assert (await configure(client,identity,slots=1)).status_code==200
    aid=await book(await run_row(identity))
    def never(*args):raise AssertionError('Probe bypassed chat slot')
    monkeypatch.setattr('pao.model_api.decrypt_key',never)
    res=await client.post('/v1/model-providers/openai/test',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert res.status_code==429 and res.json()['detail']=='tenant_model_concurrency_exhausted'
    await complete(aid,'cancelled',{},0,None,1)


async def test_native_probe_hard_timeout_unknown_and_slot_release(client,identity,monkeypatch):
    await probe_fixture(identity,monkeypatch);monkeypatch.setattr(resources,'CALL_TIMEOUT',.5)
    class Slow:
        provider_name='openai';model_name='fixture-model'
        async def stream(self,*args,**kwargs):await asyncio.sleep(2);yield Chunk(text='PAO OK')
    monkeypatch.setattr('pao.model_api.cloud_gateway',lambda *args:Slow())
    res=await client.post('/v1/model-providers/openai/test',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert res.status_code==503,res.text
    data=(await status(client,identity))['usage']
    assert data['active_models']==0 and data['calls']==1 and data['reserved_or_reported_tokens']==96
