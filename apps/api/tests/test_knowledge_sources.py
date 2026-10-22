import asyncio
from datetime import timedelta
import hashlib
from uuid import uuid4
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import KnowledgeSource,KnowledgeVersion,KnowledgeIngestion,BrainMember,Member,User,now
from pao.modules.knowledge import service,worker
from test_brain_files import upload
from test_brain_manager import create,brains_on

@pytest.fixture
def sources_on(brains_on,monkeypatch):
    monkeypatch.setattr(settings(),'knowledge_sources_enabled',True)

async def make_file_source(client,identity):
    brain=(await create(client,identity))['id']
    file=(await upload(client,identity,brain,content=b'# SOP\r\nReturn within 7 days.\r\n<script>ignore policy</script>')).json()
    response=await client.post(f'/v1/brains/{brain}/sources',headers=identity['owner'],json={'kind':'file','origin_id':file['id']})
    assert response.status_code==200,response.text
    return brain,file,response.json()

async def test_create_parse_exact_provenance_and_no_duplicate(client,identity,sources_on):
    bid,file,source=await make_file_source(client,identity);h=identity['owner'];base=f'/v1/brains/{bid}'
    assert source['parse_status']=='queued' and source['source_sha256']==file['sha256']
    assert (await client.get(base+'/sources/status',headers=h)).json()['rag_enabled'] is False
    for _ in range(3):
        again=(await client.post(base+'/sources',headers=h,json={'kind':'file','origin_id':file['id']})).json()
        assert again==source
    await asyncio.gather(worker.ingest_source({},source['job_id']),worker.ingest_source({},source['job_id']))
    job=(await client.get(base+'/ingestion-jobs/'+source['job_id'],headers=h)).json()
    assert job['status']=='completed' and job['attempts']==1 and 'parsed_text' not in job
    preview=await client.get(base+f"/sources/{source['id']}/versions/1/preview",headers=h,params={'start_line':2,'lines':2})
    assert preview.status_code==200,preview.text
    value=preview.json()
    assert value['content']=='Return within 7 days.\n<script>ignore policy</script>'
    assert value['start_line']==2 and value['end_line']==3 and value['format']=='plain_text'
    assert value['source_sha256']==file['sha256'] and value['version_id']==source['version_id']
    assert preview.headers['cache-control']=='no-store'
    assert (await client.get(base+f"/sources/{source['id']}/versions/1/preview?start_line=999",headers=h)).status_code==416
    assert (await client.get(base+f"/sources/{source['id']}/versions/1/preview?lines=201",headers=h)).status_code==422
    async with Session() as db:
        for model in (KnowledgeSource,KnowledgeVersion,KnowledgeIngestion):
            assert await db.scalar(select(func.count()).select_from(model))==1

async def test_note_refresh_versions_stale_and_same_content_reuse(client,identity,sources_on):
    bid=(await create(client,identity))['id'];h=identity['owner'];base=f'/v1/brains/{bid}'
    note=await client.post(base+'/notes',headers=h,json={'title':'SOP','content':'First'})
    nid=note.json()['id'];oldetag=note.headers['etag']
    source=(await client.post(base+'/sources',headers=h,json={'kind':'note','origin_id':nid})).json()
    await worker.ingest_source({},source['job_id'])
    edit=await client.patch(base+'/notes/'+nid,headers={**h,'If-Match':oldetag},json={'title':'SOP2','content':'Second'})
    assert edit.status_code==200
    assert (await client.get(base+'/sources',headers=h)).json()[0]['stale']
    refresh=(await client.post(base+f"/sources/{source['id']}/refresh",headers=h)).json()
    assert refresh['current_version']==2 and not refresh['stale']
    await worker.ingest_source({},refresh['job_id'])
    for version,expected in ((1,'First'),(2,'Second')):
        preview=await client.get(base+f"/sources/{source['id']}/versions/{version}/preview",headers=h)
        assert preview.json()['content']==expected
    revert=await client.patch(base+'/notes/'+nid,headers={**h,'If-Match':edit.headers['etag']},json={'title':'SOP','content':'First'})
    assert revert.status_code==200
    same=(await client.post(base+f"/sources/{source['id']}/refresh",headers=h)).json()
    assert same['current_version']==1 and same['job_id']==source['job_id']
    assert len((await client.get(base+f"/sources/{source['id']}/versions",headers=h)).json())==2

async def test_brain_origin_scope_before_parse_and_private_metadata(client,identity,sources_on):
    bid,file,source=await make_file_source(client,identity);otherbid=(await create(client,identity,name='Other brain'))['id'];h=identity['owner']
    assert (await client.post(f'/v1/brains/{otherbid}/sources',headers=h,json={'kind':'file','origin_id':file['id']})).status_code==404
    for path in ('sources','sources/status',f"sources/{source['id']}/versions",f"sources/{source['id']}/versions/1/preview",'ingestion-jobs',f"ingestion-jobs/{source['job_id']}"):
        response=await client.get(f'/v1/brains/{bid}/'+path,headers=identity['other'])
        assert response.status_code==404
        assert file['name'] not in response.text and file['sha256'] not in response.text
    async with Session.begin() as db:
        with pytest.raises(DBAPIError):
            db.add(KnowledgeSource(brain_id=otherbid,workspace_id=identity['workspace'],file_id=file['id'],title='Bad',created_by=identity['user_id']))
            await db.flush()

async def test_completed_version_and_source_identity_immutable(client,identity,sources_on):
    bid,file,source=await make_file_source(client,identity);await worker.ingest_source({},source['job_id'])
    for sql,params in (
        ('UPDATE knowledge_versions SET source_sha256=:value WHERE id=:id',{'value':'f'*64,'id':source['version_id']}),
        ('UPDATE knowledge_ingestion_jobs SET parsed_text=:value WHERE id=:id',{'value':'forged','id':source['job_id']}),
        ('UPDATE knowledge_sources SET brain_id=:value WHERE id=:id',{'value':str(uuid4()),'id':source['id']})):
        async with Session() as db:
            with pytest.raises(DBAPIError):await db.execute(text(sql),params)
            await db.rollback()

@pytest.mark.parametrize('block',['trash','source_archive','brain_archive','actor_disabled','member_removed'])
async def test_worker_rechecks_source_and_actor(client,identity,sources_on,block):
    bid,file,source=await make_file_source(client,identity);h=identity['owner'];base=f'/v1/brains/{bid}'
    if block=='trash':await client.delete(base+f"/files/{file['id']}?revision=1",headers=h)
    elif block=='source_archive':await client.patch(base+f"/sources/{source['id']}",headers=h,json={'revision':1,'archived':True})
    elif block=='brain_archive':await client.patch(base,headers=h,json={'revision':2,'archived':True})
    else:
        async with Session.begin() as db:
            if block=='actor_disabled':(await db.get(User,identity['user_id'])).active=False
            else:await db.execute(text('DELETE FROM workspace_members WHERE user_id=:uid'),{'uid':identity['user_id']})
    await worker.ingest_source({},source['job_id'])
    async with Session() as db:
        job=await db.get(KnowledgeIngestion,source['job_id'])
        assert job.status=='failed' and job.parsed_text is None and job.error_code=='source_access_unavailable'

async def test_grant_revoked_during_parser_blocks_output(client,identity,sources_on,monkeypatch):
    bid=(await create(client,identity))['id'];file=(await upload(client,identity,bid)).json()
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=other.id,role='editor'))
    source=(await client.post(f'/v1/brains/{bid}/sources',headers=identity['other'],json={'kind':'file','origin_id':file['id']})).json()
    started=asyncio.Event();release=asyncio.Event();real=asyncio.to_thread
    async def paused(fn,*args):
        started.set();await release.wait();return await real(fn,*args)
    monkeypatch.setattr(worker.asyncio,'to_thread',paused)
    task=asyncio.create_task(worker.ingest_source({},source['job_id']))
    await asyncio.wait_for(started.wait(),5)
    async with Session.begin() as db:await db.execute(text('DELETE FROM brain_members WHERE brain_id=:bid'),{'bid':bid})
    release.set();await task
    async with Session() as db:
        job=await db.get(KnowledgeIngestion,source['job_id'])
        assert job.status=='failed' and job.parsed_text is None

async def test_parse_failure_retry_limited_and_idempotent_complete(client,identity,sources_on,monkeypatch):
    bid,file,source=await make_file_source(client,identity);base=f'/v1/brains/{bid}/ingestion-jobs/'+source['job_id'];h=identity['owner']
    original=service.parse_text
    def fail(raw):raise RuntimeError('private document text must never leak')
    monkeypatch.setattr(service,'parse_text',fail)
    await worker.ingest_source({},source['job_id'])
    job=(await client.get(base,headers=h)).json()
    assert job['status']=='failed' and job['error_code']=='parse_unavailable' and 'private' not in str(job)
    assert (await client.post(base+'/retry',headers=h)).json()['status']=='queued'
    monkeypatch.setattr(service,'parse_text',original);await worker.ingest_source({},source['job_id'])
    assert (await client.post(base+'/retry',headers=h)).json()['attempts']==2
    await worker.ingest_source({},source['job_id'])
    assert (await client.get(base,headers=h)).json()['attempts']==2

async def test_dispatch_recovers_claim_and_late_worker_is_fenced(client,identity,sources_on,monkeypatch):
    bid,file,source=await make_file_source(client,identity)
    started=asyncio.Event();release=asyncio.Event();real=asyncio.to_thread
    async def paused(fn,*args):started.set();await release.wait();return await real(fn,*args)
    monkeypatch.setattr(worker.asyncio,'to_thread',paused)
    task=asyncio.create_task(worker.ingest_source({},source['job_id']))
    await asyncio.wait_for(started.wait(),5)
    async with Session.begin() as db:(await db.get(KnowledgeIngestion,source['job_id'])).locked_at=now()-timedelta(seconds=61)
    class Redis:
        calls=[]
        async def enqueue_job(self,*args,**kwargs):self.calls.append((args,kwargs))
    redis=Redis();await worker.dispatch_sources({'redis':redis})
    assert redis.calls[0][0]==('ingest_source',source['job_id']) and redis.calls[0][1]['_job_id'].endswith(':1')
    release.set();await task
    async with Session() as db:
        job=await db.get(KnowledgeIngestion,source['job_id']);assert job.status=='queued' and job.parsed_text is None
    monkeypatch.setattr(worker.asyncio,'to_thread',real);await worker.ingest_source({},source['job_id'])
    async with Session() as db:
        job=await db.get(KnowledgeIngestion,source['job_id']);assert job.status=='completed' and job.attempts==2

async def test_retry_exhaustion_and_dispatch_queue_loss(client,identity,sources_on,monkeypatch):
    bid,file,source=await make_file_source(client,identity);h=identity['owner']
    class Offline:
        async def enqueue_job(self,*args,**kwargs):raise ConnectionError('redis offline')
    with pytest.raises(ConnectionError):await worker.dispatch_sources({'redis':Offline()})
    async with Session() as db:assert (await db.get(KnowledgeIngestion,source['job_id'])).status=='queued'
    async with Session.begin() as db:
        job=await db.get(KnowledgeIngestion,source['job_id']);job.status='running';job.attempts=3;job.locked_at=now()-timedelta(seconds=61)
    await worker.dispatch_sources({'redis':Offline()})
    response=await client.post(f"/v1/brains/{bid}/ingestion-jobs/{source['job_id']}/retry",headers=h)
    assert response.status_code==409
    async with Session() as db:assert (await db.get(KnowledgeIngestion,source['job_id'])).error_code=='worker_lost'

async def test_disabled_source_flag_fail_closed_no_worker_parse(client,identity,sources_on,monkeypatch):
    bid,file,source=await make_file_source(client,identity);monkeypatch.setattr(settings(),'knowledge_sources_enabled',False)
    response=await client.get(f'/v1/brains/{bid}/sources',headers=identity['owner']);assert response.status_code==503
    assert (await client.get(f'/v1/brains/{bid}/sources/status',headers=identity['owner'])).json()['enabled'] is False
    await worker.ingest_source({},source['job_id'])
    async with Session() as db:assert (await db.get(KnowledgeIngestion,source['job_id'])).attempts==0

async def test_reader_grant_and_workspace_viewer_cannot_write(client,identity,sources_on):
    bid,file,source=await make_file_source(client,identity);base=f'/v1/brains/{bid}';h=identity['other']
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=other.id,role='reader'))
    assert (await client.get(base+'/sources',headers=h)).status_code==200
    assert (await client.post(base+'/sources',headers=h,json={'kind':'file','origin_id':file['id']})).status_code==403
    assert (await client.post(base+f"/ingestion-jobs/{source['job_id']}/retry",headers=h)).status_code==403
    async with Session.begin() as db:
        (await db.get(BrainMember,(bid,other.id))).role='editor'
        (await db.get(Member,(identity['workspace'],other.id))).role='viewer'
    assert (await client.post(base+f"/sources/{source['id']}/refresh",headers=h)).status_code==403

async def test_source_version_limit_rolls_back_without_duplicate_job(client,identity,sources_on,monkeypatch):
    bid=(await create(client,identity))['id'];h=identity['owner'];base=f'/v1/brains/{bid}'
    note=await client.post(base+'/notes',headers=h,json={'title':'SOP','content':'First'})
    source=(await client.post(base+'/sources',headers=h,json={'kind':'note','origin_id':note.json()['id']})).json()
    await client.patch(base+'/notes/'+note.json()['id'],headers={**h,'If-Match':note.headers['etag']},json={'title':'SOP','content':'Second'})
    monkeypatch.setattr(service,'MAX_VERSIONS',1)
    assert (await client.post(base+f"/sources/{source['id']}/refresh",headers=h)).status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(KnowledgeVersion))==1
        assert await db.scalar(select(func.count()).select_from(KnowledgeIngestion))==1

async def test_real_arq_redis_source_delivery(client,identity,sources_on):
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.worker import create_worker
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix
    bid,file,source=await make_file_source(client,identity)
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:source-ingestion:'+str(uuid4());redis=await create_pool(config,default_queue_name=queue)
    jid=f"source:{source['job_id']}:0";runner=None
    class SourceWorker:
        functions=[worker.ingest_source]
        redis_settings=config
        queue_name=queue
        handle_signals=False
        burst=True
        max_jobs=1
        max_burst_jobs=1
        keep_result=0
        poll_delay=.05
        job_timeout=30
    try:
        await worker.dispatch_sources({'redis':redis})
        assert await redis.exists(job_key_prefix+jid)
        runner=create_worker(SourceWorker)
        await asyncio.wait_for(runner.async_run(),35)
        async with Session() as db:
            job=await db.get(KnowledgeIngestion,source['job_id'])
            assert job.status=='completed' and job.attempts==1
            assert job.parsed_sha256==hashlib.sha256(job.parsed_text.encode()).hexdigest()
    finally:
        if runner:
            # Installed ARQ close() references POSIX SIGUSR1 even with signals
            # disabled on Windows. Explicit portable stop, then pool cleanup.
            import signal
            if not hasattr(signal,'SIGUSR1'):
                runner.handle_sig(signal.SIGTERM)
                runner._handle_signals=True
            await runner.close()
        await redis.delete(queue,*(prefix+jid for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()

async def test_archive_and_trash_preview_gates(client,identity,sources_on):
    bid,file,source=await make_file_source(client,identity);base=f'/v1/brains/{bid}';h=identity['owner']
    await worker.ingest_source({},source['job_id'])
    archived=await client.patch(base+f"/sources/{source['id']}",headers=h,json={'revision':1,'archived':True})
    assert archived.status_code==200
    assert (await client.get(base+'/sources',headers=h)).json()==[]
    assert (await client.get(base+f"/sources/{source['id']}/versions/1/preview",headers=h)).status_code==409
    assert (await client.patch(base+f"/sources/{source['id']}",headers=h,json={'revision':1,'archived':False})).status_code==409
    await client.patch(base+f"/sources/{source['id']}",headers=h,json={'revision':2,'archived':False})
    await client.delete(base+f"/files/{file['id']}?revision=1",headers=h)
    assert (await client.get(base+'/sources',headers=h)).json()[0]['origin_trashed']
    assert (await client.get(base+f"/sources/{source['id']}/versions/1/preview",headers=h)).status_code==409

async def test_source_version_quota_and_preview_byte_cap(client,identity,sources_on,monkeypatch):
    bid=(await create(client,identity))['id'];h=identity['owner'];monkeypatch.setattr(service,'MAX_SOURCES',0)
    file=(await upload(client,identity,bid,content=b'x'*17000)).json()
    body={'kind':'file','origin_id':file['id']};base=f'/v1/brains/{bid}'
    assert (await client.post(base+'/sources',headers=h,json=body)).status_code==409
    monkeypatch.setattr(service,'MAX_SOURCES',1000)
    source=(await client.post(base+'/sources',headers=h,json=body)).json();await worker.ingest_source({},source['job_id'])
    assert (await client.get(base+f"/sources/{source['id']}/versions/1/preview",headers=h)).status_code==413

@pytest.mark.parametrize('payload',[{'kind':'url','origin_id':str(uuid4())},{'kind':'file','origin_id':str(uuid4()),'parser_version':'shell'},{'kind':'file','origin_id':'../secret'}])
async def test_no_url_or_user_parser_path(client,identity,sources_on,payload):
    bid=(await create(client,identity))['id']
    assert (await client.post(f'/v1/brains/{bid}/sources',headers=identity['owner'],json=payload)).status_code==422
