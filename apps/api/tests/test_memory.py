from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.gateway import Chunk, OllamaGateway
from pao.models import Memory, MemoryJob, Member, Workspace, Brand, now
from pao.memory import extract_memory, dispatch_memory, retrieve
from pao.memory_schemas import ExtractedFacts, Fact
from pao.runtime import execute_run


@pytest.fixture
async def memory_on(monkeypatch):
    monkeypatch.setattr(settings(), 'memory_enabled', True)
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    monkeypatch.setattr(settings(),'ollama_model','memory-fixture')
    async def embed(self, text):
        return ([1.0, 0.0] if 'Malaysia' in text else [0.0, 1.0]) + [0.0] * 766
    monkeypatch.setattr(OllamaGateway, 'embed', embed)


async def add(client, identity, value='Thị trường chính là Malaysia', key='target_market', brand_id=None, headers=None):
    return await client.post('/v1/memory', headers=headers or identity['owner'], json={
        'workspace_id':identity['workspace'], 'brand_id':brand_id, 'key':key, 'value':value, 'importance':4})


async def test_memory_scope_crud_conflicts_and_delete(client, identity, memory_on):
    headers=identity['owner']
    first=await add(client,identity); assert first.status_code==201, first.text
    old=first.json()
    assert (await add(client,identity)).json()['id']==old['id']
    second=(await add(client,identity,'Thị trường chính là Vietnam')).json()
    assert second['status']=='pending'
    assert (await client.get('/v1/memory',headers=identity['other'],params={'workspace_id':identity['workspace']})).json()==[]
    assert (await client.patch('/v1/memory/'+old['id'],headers=identity['other'],json={
        'key':old['key'],'value':old['value'],'version':1})).status_code==404
    assert (await client.get('/v1/memory',headers=identity['outsider'],params={'workspace_id':identity['workspace']})).status_code==404
    saved=await client.patch('/v1/memory/'+second['id'],headers=headers,json={
        'key':second['key'],'value':second['value'],'version':second['version'],'status':'active'})
    assert saved.status_code==200,saved.text
    rows=(await client.get('/v1/memory',headers=headers,params={'workspace_id':identity['workspace']})).json()
    assert sorted(r['status'] for r in rows)==['active','superseded']
    stale=await client.patch('/v1/memory/'+old['id'],headers=headers,json={'key':old['key'],'value':old['value'],'version':1})
    assert stale.status_code==409
    deleted=await client.delete('/v1/memory/'+second['id'],headers=headers,params={'version':saved.json()['version']})
    assert deleted.status_code==204
    async with Session() as db:
        row=await db.get(Memory,second['id'])
        assert row.value=='' and row.embedding is None and row.status=='deleted'
    assert (await add(client,identity,'Thị trường chính là Vietnam')).status_code==409


async def test_brand_and_workspace_isolation_pgvector(client, identity, memory_on):
    a=(await client.post('/v1/brands',headers=identity['owner'],json={'workspace_id':identity['workspace'],'name':'Brand A'})).json()
    b=(await client.post('/v1/brands',headers=identity['owner'],json={'workspace_id':identity['workspace'],'name':'Brand B'})).json()
    await add(client,identity,brand_id=a['id'])
    await add(client,identity,'Brand B bán tại Vietnam',brand_id=b['id'])
    hits,degraded=await retrieve(identity['workspace'],identity['user_id'],a['id'],'Malaysia')
    assert not degraded and len(hits)==1 and hits[0][0].brand_id==a['id']
    assert await retrieve(identity['workspace'],identity['user_id'],None,'Malaysia')==([],False)
    async with Session.begin() as db:
        workspace=Workspace(name='Other workspace');db.add(workspace);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=identity['user_id'],role='owner'))
    assert await retrieve(workspace.id,identity['user_id'],a['id'],'Malaysia')==([],False)
    wrong=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':workspace.id,'brand_id':a['id']})
    assert wrong.status_code==404
    assert (await client.post('/v1/memory/search',headers=identity['owner'],json={
        'workspace_id':workspace.id,'brand_id':a['id'],'query':'Malaysia'})).status_code==404


async def test_viewer_cannot_manage_memory(client, identity, memory_on):
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    assert (await add(client,identity)).status_code==403
    assert (await client.post('/v1/brands',headers=identity['owner'],json={'workspace_id':identity['workspace'],'name':'Denied'})).status_code==403


async def test_concurrent_writes_deduplicate(client, identity, memory_on):
    import asyncio
    results = await asyncio.gather(add(client, identity), add(client, identity))
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json()['id'] == results[1].json()['id']


async def test_stalled_embedding_falls_back_without_using_reply_budget(client, identity, memory_on, monkeypatch):
    import asyncio
    await add(client, identity)
    class Stalled:
        async def embed(self, text):
            await asyncio.sleep(2)
    monkeypatch.setattr(settings(), 'memory_timeout_seconds', 0.01)
    hits, degraded = await retrieve(identity['workspace'], identity['user_id'], None, 'Malaysia', Stalled())
    assert degraded and len(hits) == 1


class Gateway(OllamaGateway):
    def __init__(self): super().__init__();self.context=None
    async def stream(self,messages,max_tokens=None):
        self.context=messages
        yield Chunk(text='Đã nhận thông tin.')
    async def extract(self,prompt):
        return ExtractedFacts(facts=[Fact(key='target_market',value=prompt,importance=4)])
    async def embed(self,text): return [1.0]+[0.0]*767


async def run_chat(client,identity,message,session=None):
    if not session:
        session=(await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})).json()['id']
    result=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':session,'message':message,'request_key':'memory-test-'+str(int(now().timestamp()*1000000))})
    assert result.status_code==202,result.text
    return session,result.json()['id']


async def test_extract_then_recall_different_session_and_delete_not_resurrect(client,identity,memory_on):
    gateway=Gateway();fact='Thị trường mục tiêu của doanh nghiệp tôi là Malaysia.'
    sid,rid=await run_chat(client,identity,fact)
    await execute_run({'gateway':gateway,'memory_gateway':gateway},rid)
    await extract_memory({'memory_gateway':gateway},rid)
    await extract_memory({'memory_gateway':gateway},rid)
    items=(await client.get('/v1/memory',headers=identity['owner'],params={'workspace_id':identity['workspace']})).json()
    assert len(items)==1 and items[0]['source_run_id']==rid and items[0]['value']==fact
    _,rid2=await run_chat(client,identity,'Doanh nghiệp của tôi nhắm tới thị trường nào?')
    await execute_run({'gateway':gateway,'memory_gateway':gateway},rid2)
    assert any('REFERENCE DATA' in m['content'] and fact in m['content'] for m in gateway.context if m['role']=='user')
    assert fact not in gateway.context[0]['content']  # Facts never promoted to system instructions.
    status=(await client.get('/v1/memory/status',headers=identity['owner'],params={'session_id':sid})).json()
    assert status['job_status']=='completed' and status['extracted']==1
    await client.delete('/v1/memory/'+items[0]['id'],headers=identity['owner'],params={'version':1})
    # Simulate a job replay after a crash. Tombstone blocks reinstating the same fact.
    async with Session.begin() as db:
        job=await db.get(MemoryJob,rid);job.status='queued'
    await extract_memory({'memory_gateway':gateway},rid)
    assert (await client.get('/v1/memory',headers=identity['owner'],params={'workspace_id':identity['workspace']})).json()==[]


async def test_extraction_rejects_hallucinated_value_and_low_importance(client,identity,memory_on):
    class BadFacts(Gateway):
        async def extract(self,prompt):
            return ExtractedFacts(facts=[Fact(key='fake_market',value='Imaginary fact not in source',importance=5),
                                         Fact(key='low_value',value=prompt,importance=1)])
    sid,rid=await run_chat(client,identity,'Một câu nói thông thường.')
    await execute_run({'gateway':Gateway()},rid)
    await extract_memory({'memory_gateway':BadFacts()},rid)
    async with Session() as db:
        assert not list(await db.scalars(select(Memory)))
        assert (await db.get(MemoryJob,rid)).status=='completed'


async def test_disabled_session_and_revoked_user_prevent_extraction(client,identity,memory_on):
    sid,rid=await run_chat(client,identity,'Thị trường của tôi là Malaysia.')
    await execute_run({'gateway':Gateway()},rid)
    await client.patch('/v1/sessions/'+sid,headers=identity['owner'],json={'memory_enabled':False})
    await extract_memory({'memory_gateway':Gateway()},rid)
    async with Session() as db:
        assert not list(await db.scalars(select(Memory)))
    _,rid2=await run_chat(client,identity,'Thị trường của tôi là Malaysia.')
    await execute_run({'gateway':Gateway()},rid2)
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    await extract_memory({'memory_gateway':Gateway()},rid2)
    async with Session() as db:
        assert (await db.get(MemoryJob,rid2)).error_code=='access_revoked'
        assert not list(await db.scalars(select(Memory)))


async def test_embedding_failure_degrades_without_losing_fact(client,identity,memory_on,monkeypatch):
    async def broken(self,text): raise RuntimeError('private-url')
    monkeypatch.setattr(OllamaGateway,'embed',broken)
    response=await add(client,identity)
    assert response.status_code==201 and response.json()['embedding_model'] is None
    hits=await client.post('/v1/memory/search',headers=identity['owner'],json={'workspace_id':identity['workspace'],'query':'Malaysia'})
    assert hits.json()['degraded'] and len(hits.json()['items'])==1
    assert 'private-url' not in hits.text


async def test_memory_job_bounded_retry_and_stale_recovery(client,identity,memory_on):
    class Broken(Gateway):
        async def extract(self,prompt): raise RuntimeError('private-error')
    _,rid=await run_chat(client,identity,'Thị trường của tôi là Malaysia.')
    await execute_run({'gateway':Gateway()},rid)
    await extract_memory({'memory_gateway':Broken()},rid)
    async with Session() as db: assert (await db.get(MemoryJob,rid)).status=='queued'
    await extract_memory({'memory_gateway':Broken()},rid)
    async with Session() as db:
        job=await db.get(MemoryJob,rid);assert job.status=='failed' and job.attempts==2
    async with Session.begin() as db:
        job=await db.get(MemoryJob,rid);job.status='running';job.attempts=1;job.updated_at=now()-timedelta(hours=1)
    redis=AsyncMock();await dispatch_memory({'redis':redis})
    redis.enqueue_job.assert_awaited_once()
    async with Session() as db: assert (await db.get(MemoryJob,rid)).status=='queued'
