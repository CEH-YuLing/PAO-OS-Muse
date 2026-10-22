"""No policy-row/global-feature exemption, no re-pin or untracked model calls."""
from uuid import uuid4
import asyncio
import pytest
from sqlalchemy import select,func,update
from pao.config import settings
from pao.db import Session
from pao.gateway import Chunk
from pao.models import ChatSession,Run,Workspace,Member,MemoryJob,Memory,LlmAttempt,TenantModelLease,TenantResourcePolicy
from pao.runtime import execute_run
from pao.memory import extract_memory
from pao.model_router import gateway_for_workspace
from pao.modules.chat.ledger import AccountingEngine
from pao.modules.engines.service import gateway_for_run
from pao.modules.engines.contract import EngineFailure
from test_tenant_model_resources import configure


class Fake:
    provider_name='ollama'
    def __init__(self):self.model_name=settings().ollama_model;self.calls=0
    async def stream(self,*args,**kwargs):self.calls+=1;yield Chunk(text='Accounted fixture reply')
    async def extract(self,*args):raise AssertionError('Legacy must never extract')


async def queued(client,identity,*,wid=None):
    session=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':wid or identity['workspace'],'memory_enabled':False})
    assert session.status_code==201
    sid=session.json()['id']
    run=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,'message':'Fixture request','request_key':uuid4().hex})
    assert run.status_code==202,run.text
    return sid,run.json()['id']


@pytest.mark.parametrize('configured',[False,True])
@pytest.mark.parametrize('pinned',[False,True])
async def test_legacy_runtime_and_gateway_injection_denied_without_io(client,identity,monkeypatch,configured,pinned):
    monkeypatch.setattr(settings(),'engine_contract_enabled',pinned)
    monkeypatch.setattr(settings(),'chat_features_enabled',False)
    if configured:assert (await configure(client,identity)).status_code==200
    sid,rid=await queued(client,identity);fake=Fake()
    before=None
    async with Session() as db:before=(await db.get(Run,rid)).engine_snapshot
    await execute_run({'gateway':fake},rid);await execute_run({'gateway':fake},rid)
    async with Session() as db:
        row=await db.get(Run,rid)
        assert row.status=='failed' and row.error_code=='tenant_resource_accounting_required' and row.engine_snapshot==before
        assert not await db.scalar(select(func.count()).select_from(LlmAttempt))
        assert not await db.scalar(select(func.count()).select_from(TenantModelLease))
    assert fake.calls==0


@pytest.mark.parametrize('configured',[False,True])
async def test_workspace_resolver_denied_before_local_factory_or_decrypt(client,identity,monkeypatch,configured):
    if configured:assert (await configure(client,identity)).status_code==200
    def forbidden(*args):raise AssertionError('No credential or local/cloud factory')
    monkeypatch.setattr('pao.model_router.decrypt_key',forbidden)
    monkeypatch.setattr('pao.model_router.cloud_gateway',forbidden)
    monkeypatch.setattr('pao.model_router.OllamaGateway',forbidden)
    async with Session() as db:
        with pytest.raises(EngineFailure,match='^tenant_resource_accounting_required$'):
            await gateway_for_workspace(db,identity['workspace'])


async def test_modern_mode_does_not_repin_queued_unknown_work(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'engine_contract_enabled',False)
    _,rid=await queued(client,identity)
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    fake=Fake();await execute_run({'gateway':fake},rid)
    async with Session() as db:
        row=await db.get(Run,rid)
        assert row.status=='failed' and row.engine_snapshot is None and row.error_code=='tenant_resource_accounting_required'
        assert not await db.scalar(select(func.count()).select_from(LlmAttempt))
    assert fake.calls==0


@pytest.mark.parametrize('mode',['off','missing_policy'])
async def test_pinned_local_gateway_not_usable_without_accounting_contract(client,identity,monkeypatch,mode):
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',False)
    _,rid=await queued(client,identity)
    if mode=='missing_policy':monkeypatch.setattr(settings(),'chat_features_enabled',True)
    async with Session() as db:
        row=await db.get(Run,rid);before=row.engine_snapshot
        with pytest.raises(EngineFailure,match='^tenant_resource_accounting_required$'):await gateway_for_run(db,row)
        assert row.engine_snapshot==before


async def test_cached_accounted_wrapper_cannot_call_after_flag_off(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    _,rid=await queued(client,identity);fake=Fake()
    async with Session() as db:wrapper=AccountingEngine(fake,await db.get(Run,rid))
    monkeypatch.setattr(settings(),'chat_features_enabled',False)
    with pytest.raises(EngineFailure,match='^tenant_resource_accounting_required$'):
        async for _ in wrapper.stream([{'role':'system','content':'Fixture'},{'role':'user','content':'Fixture request'}]):pass
    assert fake.calls==0
    async with Session() as db:assert not await db.scalar(select(func.count()).select_from(LlmAttempt))


async def test_legacy_memory_is_terminal_before_injected_gateway(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'memory_enabled',True)
    monkeypatch.setattr(settings(),'engine_contract_enabled',False)
    sid,rid=await queued(client,identity)
    async with Session.begin() as db:
        (await db.get(Run,rid)).status='completed'
        (await db.get(ChatSession,sid)).memory_enabled=True
        db.add(MemoryJob(run_id=rid,workspace_id=identity['workspace']))
    fake=Fake();await extract_memory({'memory_gateway':fake},rid);await extract_memory({'memory_gateway':fake},rid)
    async with Session() as db:
        job=await db.get(MemoryJob,rid)
        assert job.status=='failed' and job.error_code=='tenant_resource_accounting_required' and job.attempts==1
        assert not await db.scalar(select(func.count()).select_from(Memory))
        assert not await db.scalar(select(func.count()).select_from(LlmAttempt))


async def test_real_arq_unknown_a_does_not_block_accounted_b(client,identity,monkeypatch):
    from arq import create_pool
    from arq import func as worker_function
    import signal
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix,default_queue_name,in_progress_key_prefix,retry_key_prefix,result_key_prefix
    monkeypatch.setattr(settings(),'engine_contract_enabled',False)
    _,a=await queued(client,identity)
    async with Session.begin() as db:
        other=Workspace(name='Accounted SME B');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    _,b=await queued(client,identity,wid=wid);fake=Fake()
    async def execute_fixture(ctx,rid):await execute_run({**ctx,'gateway':fake},rid)
    execute_fixture.__name__='execute_run'
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    if not hasattr(signal,'SIGUSR1'):monkeypatch.setattr(signal,'SIGUSR1',signal.SIGTERM,raising=False)
    queue='pao-test:legacy-accounting:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue);runner=None;ids=['run:'+a,'run:'+b]
    class Workers:
        functions=[worker_function(execute_fixture,name='execute_run')];redis_settings=config;queue_name=queue
        handle_signals=False;burst=True;max_jobs=max_burst_jobs=2;keep_result=0;poll_delay=.05;job_timeout=20
    try:
        for jid in ids:
            assert await redis.exists(job_key_prefix+jid)
            score=await redis.zscore(default_queue_name,jid);assert score is not None
            await redis.zrem(default_queue_name,jid);await redis.zadd(queue,{jid:score})
        runner=create_worker(Workers);await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==2 and runner.jobs_failed==0 and fake.calls==1
        async with Session() as db:
            assert (await db.get(Run,a)).error_code=='tenant_resource_accounting_required'
            assert (await db.get(Run,b)).status=='completed'
            attempts=list(await db.scalars(select(LlmAttempt)))
            assert len(attempts)==1 and attempts[0].workspace_id==wid and attempts[0].usage_state=='unknown'
            assert await db.scalar(select(func.count()).select_from(TenantResourcePolicy))==0
    finally:
        if runner:await runner.close()
        for jid in ids:
            await redis.zrem(queue,jid)
            await redis.delete(*(prefix+jid for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()
