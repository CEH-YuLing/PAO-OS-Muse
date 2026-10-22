"""Knowledge shared quota, immutable queued pins and source/Brain publication."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func,update,text
from sqlalchemy.exc import DBAPIError
from pao.auth import Principal
from pao.config import settings
from pao.db import Session
from pao.gateway import OllamaGateway
from pao.models import KnowledgeIndexJob,KnowledgeChunk,TenantModelLease,KnowledgeSource,Brain,User,Workspace,Member,now
from pao.modules.knowledge import index,retrieval
from test_knowledge_workspace import source,p2_on,sources_on,brains_on
from test_tenant_model_resources import configure

class Fake:
    def __init__(self):self.calls=0
    async def embed(self,value):self.calls+=1;return [1.0]+[0.0]*767

async def rebuild(client,identity,bid,row):
    result=await client.post(f'/v1/brains/{bid}/sources/{row["id"]}/index',headers=identity['owner'],json={'confirmed':True})
    assert result.status_code==200,result.text
    return result.json()

async def count(wid):
    async with Session() as db:return await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.workspace_id==wid,TenantModelLease.kind=='embedding'))

async def test_index_and_query_share_quota_and_lexical_fallback(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity)
    monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    assert (await configure(client,identity,calls=1)).status_code==200
    await rebuild(client,identity,bid,row);fake=Fake();await index.index_source({'knowledge_gateway':fake},jid)
    async with Session() as db:
        assert (await db.get(KnowledgeIndexJob,jid)).embedding_status=='ready'
        result=await retrieval.retrieve(db,Principal(identity['user_id'],0),bid,'doi tra',gateway=fake)
    assert result['degraded'] and result['mode']=='full_text' and result['items'] and fake.calls==1
    assert await count(identity['workspace'])==1

async def test_sme_a_cap_cannot_block_index_or_query_in_b(client,identity,p2_on,monkeypatch):
    a=await source(client,identity)
    async with Session.begin() as db:
        other=Workspace(name='Knowledge SME B');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    second={**identity,'workspace':wid};b=await source(client,second)
    monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    assert (await configure(client,identity,calls=1)).status_code==200
    fake=Fake()
    for who,data in ((identity,a),(second,b)):
        await rebuild(client,who,data[0],data[2]);await index.index_source({'knowledge_gateway':fake},data[4])
    async with Session() as db:
        denied=await retrieval.retrieve(db,Principal(identity['user_id'],0),a[0],'doi tra',gateway=fake)
        allowed=await retrieval.retrieve(db,Principal(identity['user_id'],0),b[0],'doi tra',gateway=fake)
    assert denied['degraded'] and allowed['mode']=='hybrid' and fake.calls==3
    assert all(item['brain_id']==b[0] for item in allowed['items'])
    assert await count(identity['workspace'])==1 and await count(wid)==2

async def test_batch_partial_quota_keeps_all_lexical_chunks(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity,content=b'Return policy 7 days.\n'*260)
    monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    assert (await configure(client,identity,calls=1)).status_code==200
    await rebuild(client,identity,bid,row);fake=Fake();await index.index_source({'knowledge_gateway':fake},jid)
    async with Session() as db:
        job=await db.get(KnowledgeIndexJob,jid)
        assert job.status=='completed' and job.embedding_status=='partial' and job.error_code=='tenant_model_daily_calls_exhausted'
        stored=list(await db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.version_id==row['version_id'])))
        assert len(stored)==len(chunks)>1 and sum(x.embedding_binding is not None for x in stored)==1
    assert fake.calls==1

async def test_retry_same_generation_never_resends_but_confirmed_rebuild_is_new_intent(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row)
    class Offline(Fake):
        async def embed(self,value):self.calls+=1;raise TimeoutError('unknown fixture outcome')
    old=Offline();await index.index_source({'knowledge_gateway':old},jid)
    async with Session.begin() as db:(await db.get(KnowledgeIndexJob,jid)).status='queued'
    fresh=Fake();await index.index_source({'knowledge_gateway':fresh},jid)
    assert old.calls==1 and fresh.calls==0
    async with Session() as db:assert (await db.get(KnowledgeIndexJob,jid)).error_code=='tenant_resource_replay_denied'
    await rebuild(client,identity,bid,row);await index.index_source({'knowledge_gateway':fresh},jid)
    assert fresh.calls==1 and await count(identity['workspace'])==2

async def test_legacy_missing_pin_and_stale_queue_cannot_acquire_new_intent(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    async with Session.begin() as db:
        legacy=KnowledgeIndexJob(workspace_id=identity['workspace'],brain_id=bid,version_id=row['version_id'],
            actor_id=identity['user_id'],chunker_version=index.CHUNKER,embedding_model='legacy-fixture')
        db.add(legacy);await db.flush();lid=legacy.id
    fake=Fake();await index.index_source({'knowledge_gateway':fake},lid)
    async with Session() as db:
        value=await db.get(KnowledgeIndexJob,lid)
        assert value.status=='completed' and value.embedding_engine is None and value.error_code=='embedding_pin_missing'
    await rebuild(client,identity,bid,row)
    await index.index_source({'knowledge_gateway':fake},jid,0)
    await index.index_source({'knowledge_gateway':fake,'job_id':'legacy-unversioned-delivery'},jid)
    assert fake.calls==0
    async with Session() as db:assert (await db.get(KnowledgeIndexJob,jid)).status=='queued'

async def test_queued_native_model_endpoint_pin_survives_host_setting_change(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity)
    monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row);expected=(settings().ollama_url,settings().embedding_model)
    seen=[]
    async def pinned(self,value):seen.append((self.base_url,self._embedding_model));return [1.0]+[0.0]*767
    monkeypatch.setattr(OllamaGateway,'embed',pinned)
    monkeypatch.setattr(settings(),'embedding_model','future-request-model')
    monkeypatch.setattr(settings(),'ollama_url','http://127.0.0.1:11435')
    await index.index_source({},jid)
    async with Session() as db:
        job=await db.get(KnowledgeIndexJob,jid);assert job.embedding_status=='ready'
        result=await retrieval.retrieve(db,Principal(identity['user_id'],0),bid,'doi tra',gateway=Fake())
    assert seen==[expected] and result['mode']=='full_text' and result['degraded']
    assert await count(identity['workspace'])==1 # no mixing new endpoint query into old vector space

async def test_query_has_no_caller_or_brain_lock_across_model_io(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row);await index.index_source({'knowledge_gateway':Fake()},jid)
    async with Session() as outer:
        await index.access(outer,Principal(identity['user_id'],0),bid)
        class Check(Fake):
            async def embed(self,value):
                assert not outer.in_transaction()
                async with Session.begin() as fresh:
                    await fresh.execute(select(Brain.id).where(Brain.id==bid).with_for_update(nowait=True))
                return await super().embed(value)
        result=await retrieval.retrieve(outer,Principal(identity['user_id'],0),bid,'doi tra',gateway=Check())
    assert result['mode']=='hybrid' and not result['degraded']

async def test_source_archived_during_query_cannot_return_cached_citations(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row);await index.index_source({'knowledge_gateway':Fake()},jid)
    class Archive(Fake):
        async def embed(self,value):
            async with Session.begin() as fresh:(await fresh.get(KnowledgeSource,row['id'])).archived_at=now()
            return await super().embed(value)
    async with Session() as db:result=await retrieval.retrieve(db,Principal(identity['user_id'],0),bid,'doi tra',gateway=Archive())
    assert result['items']==[] and result['degraded'] and await count(identity['workspace'])==2

async def test_offline_rebuild_does_not_erase_good_vectors(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row);await index.index_source({'knowledge_gateway':Fake()},jid)
    async with Session() as db:binding=(await db.get(KnowledgeChunk,chunks[0]['chunk_id'])).embedding_binding
    await rebuild(client,identity,bid,row)
    class Offline:
        async def embed(self,value):raise RuntimeError('fixture offline')
    await index.index_source({'knowledge_gateway':Offline()},jid)
    async with Session() as db:
        chunk=await db.get(KnowledgeChunk,chunks[0]['chunk_id'])
        assert chunk.embedding_binding==binding and chunk.embedding is not None

async def test_cancel_and_worker_lost_retry_release_slot_without_resending(client,identity,p2_on,monkeypatch):
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row);started=asyncio.Event();stop=asyncio.Event()
    class Slow(Fake):
        async def embed(self,value):self.calls+=1;started.set();await stop.wait();return [1.0]+[0.0]*767
    fake=Slow();task=asyncio.create_task(index.index_source({'knowledge_gateway':fake},jid))
    try:
        await asyncio.wait_for(started.wait(),5);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        async with Session.begin() as db:
            job=await db.get(KnowledgeIndexJob,jid);job.locked_at=now()-timedelta(seconds=61)
            assert job.status=='running'
        class Redis:
            async def enqueue_job(self,*args,**kwargs):pass
        await index.dispatch_indexes({'redis':Redis()})
        await index.index_source({'knowledge_gateway':fake},jid)
        async with Session() as db:
            assert (await db.get(KnowledgeIndexJob,jid)).error_code=='tenant_resource_replay_denied'
            assert not await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.status=='active'))
        assert fake.calls==1 and await count(identity['workspace'])==1
    finally:
        stop.set()
        if not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)

async def test_real_arq_generation_delivery_uses_shared_admission(client,identity,p2_on,monkeypatch):
    from arq import create_pool,func as worker_function
    from arq.connections import RedisSettings
    from arq.worker import create_worker
    from arq.constants import job_key_prefix,default_queue_name,in_progress_key_prefix,retry_key_prefix,result_key_prefix
    import signal
    bid,file,row,chunks,jid=await source(client,identity);monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    await rebuild(client,identity,bid,row);fake=Fake()
    async with Session() as db:generation=(await db.get(KnowledgeIndexJob,jid)).embedding_generation
    queue='pao-test:knowledge-embedding:'+uuid4().hex;key=f'index:{jid}:{generation}:0'
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    if not hasattr(signal,'SIGUSR1'):monkeypatch.setattr(signal,'SIGUSR1',signal.SIGTERM,raising=False)
    redis=await create_pool(config,default_queue_name=queue);runner=None
    async def execute(ctx,jid,version):await index.index_source({**ctx,'knowledge_gateway':fake},jid,version)
    class Workers:
        functions=[worker_function(execute,name='index_source')];redis_settings=config;queue_name=queue
        handle_signals=False;burst=True;max_jobs=max_burst_jobs=1;keep_result=0;poll_delay=.05;job_timeout=20
    try:
        await index.dispatch_indexes({'redis':redis})
        score=await redis.zscore(queue,key)
        if score is None:
            score=await redis.zscore(default_queue_name,key);assert score is not None
            await redis.zrem(default_queue_name,key);await redis.zadd(queue,{key:score})
        runner=create_worker(Workers);await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==1 and runner.jobs_failed==0 and fake.calls==1
        async with Session() as db:assert (await db.get(KnowledgeIndexJob,jid)).embedding_status=='ready'
        assert await count(identity['workspace'])==1
    finally:
        if runner:await runner.close()
        await redis.zrem(queue,key);await redis.zrem(default_queue_name,key)
        await redis.delete(*(prefix+key for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()

@pytest.mark.parametrize('kind',['pin','actor','generation','identity'])
async def test_index_pin_identity_and_rebuild_guard_sql(client,identity,p2_on,kind):
    bid,file,row,chunks,jid=await source(client,identity)
    async with Session() as db:pin=dict((await db.get(KnowledgeIndexJob,jid)).embedding_engine)
    pin['url']='http://127.0.0.1:11435'
    values={'pin':{'embedding_engine':pin},'actor':{'actor_id':str(uuid4())},
        'generation':{'embedding_generation':2},'identity':{'embedding_model':'other'}}[kind]
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(update(KnowledgeIndexJob).where(KnowledgeIndexJob.id==jid).values(**values))
