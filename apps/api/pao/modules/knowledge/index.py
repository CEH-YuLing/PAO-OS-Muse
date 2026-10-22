"""Stable, bounded chunks and local-only vector index. Originals are never rewritten."""
import asyncio,hashlib,math
from datetime import timedelta
from urllib.parse import urlsplit
from uuid import uuid4,uuid5,NAMESPACE_URL
from fastapi import HTTPException
from sqlalchemy import select,func
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...gateway import OllamaGateway
from ...models import Brain,User,KnowledgeVersion,KnowledgeSource,KnowledgeIngestion,KnowledgeChunk,KnowledgeIndexJob,now
from . import service
from ..connections.embedding_resources import embed
from ..engines.service import local_url,model_name,digest
from ..engines.contract import EngineFailure

CHUNKER='chars1800-v1'

def enabled():
    service.enabled()
    if not settings().knowledge_enabled:raise HTTPException(503,'Knowledge P2 chưa bật')

async def access(db,who,bid,write=False,lock=False):
    enabled();return await service.access(db,who,bid,write,lock)

def split(text):
    chunks=[];line=1
    for ordinal,start in enumerate(range(0,len(text),1800)):
        content=text[start:start+1800]
        chunks.append({'ordinal':ordinal,'start_char':start,'end_char':start+len(content),
            'start_line':line,'end_line':line+content.count('\n'),'content':content,'sha256':hashlib.sha256(content.encode()).hexdigest()})
        line+=content.count('\n')
    if len(chunks)>600:raise ValueError('chunk_limit')
    return chunks

async def parsed(db,version):
    job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.version_id==version.id,
        KnowledgeIngestion.parser_version==service.PARSER_VERSION,KnowledgeIngestion.status=='completed'))
    if not job or hashlib.sha256(job.parsed_text.encode()).hexdigest()!=job.parsed_sha256:
        raise HTTPException(409,'Parse chưa sẵn sàng hoặc hash sai')
    return job

async def ensure_job(db,version,actor_id):
    model=settings().embedding_model
    row=await db.scalar(select(KnowledgeIndexJob).where(KnowledgeIndexJob.version_id==version.id,
        KnowledgeIndexJob.chunker_version==CHUNKER,KnowledgeIndexJob.embedding_model==model))
    if not row:
        row=KnowledgeIndexJob(version_id=version.id,brain_id=version.brain_id,workspace_id=version.workspace_id,
            actor_id=actor_id,chunker_version=CHUNKER,embedding_model=model,embedding_engine=embedding_pin())
        db.add(row);await db.flush()
    return row

def valid_vector(value):
    if len(value)!=768:raise ValueError('embedding_dimensions')
    out=[float(x) for x in value]
    if not all(math.isfinite(x) and abs(x)<=100000 for x in out) or not any(out):raise ValueError('embedding_value')
    return out

def embedding_pin():
    try:return {'version':1,'model':model_name(settings().embedding_model),'url':local_url()}
    except EngineFailure:return None # lexical-only; no remote/missing model pull

async def local_embed(text,gateway=None,**scope):
    # Scope/admission is mandatory, including internal test/custom adapters.
    result,_=await embed(text,gateway=gateway,**scope)
    return result

async def authorize(db,job):
    actor=await db.get(User,job.actor_id)
    if not actor or not actor.active:raise HTTPException(403,'Actor revoked')
    await access(db,Principal(job.actor_id,0),job.brain_id,True)
    value=await db.get(KnowledgeVersion,job.version_id);source=await db.get(KnowledgeSource,value.source_id)
    if source.archived_at:raise HTTPException(409,'Source archived')
    await service.raw_version(db,source,value)
    return value,await parsed(db,value)

async def index_source(ctx,jid,expected_generation=None):
    if not settings().knowledge_enabled or not settings().knowledge_sources_enabled or not settings().brain_manager_enabled:return
    claim=str(uuid4())
    async with Session.begin() as db:
        initial=await db.get(KnowledgeIndexJob,jid)
        if not initial or initial.status!='queued':return
        # Modern dispatcher carries the exact admitted intent. Old ARQ payloads
        # must not consume a subsequently confirmed rebuild under the same id.
        if expected_generation is None and ctx.get('job_id') is not None:return
        if expected_generation is not None and initial.embedding_generation!=expected_generation:return
        await db.execute(select(Brain.id).where(Brain.id==initial.brain_id).with_for_update())
        job=await db.scalar(select(KnowledgeIndexJob).where(KnowledgeIndexJob.id==jid).with_for_update().execution_options(populate_existing=True))
        if job.status!='queued':return
        if expected_generation is not None and job.embedding_generation!=expected_generation:return
        if job.attempts>=3:job.status='failed';job.error_code='retry_exhausted';return
        job.attempts+=1
        try:
            if job.chunker_version!=CHUNKER:raise HTTPException(409,'Index version changed')
            if job.embedding_engine and job.embedding_engine.get('model')!=job.embedding_model:raise HTTPException(409,'Index pin changed')
            value,parse=await authorize(db,job);pieces=split(parse.parsed_text)
        except (HTTPException,ValueError):job.status='failed';job.error_code='source_access_unavailable';return
        job.status='running';job.claim_id=claim;job.locked_at=now();job.updated_at=now();job.error_code=None
        engine_pin=job.embedding_engine;generation=job.embedding_generation
        wid,actor,bid=job.workspace_id,job.actor_id,job.brain_id
        brand=(await db.get(Brain,bid)).brand_id
    vectors={};state='disabled';embedding_error=None
    async def check(fresh):
        current=await fresh.get(KnowledgeIndexJob,jid)
        if (not settings().knowledge_embeddings_enabled or not current or current.status!='running'
            or current.claim_id!=claim or current.embedding_generation!=generation or current.actor_id!=actor
            or current.embedding_engine!=engine_pin):raise EngineFailure('knowledge_index_claim_changed')
        await authorize(fresh,current)
    if settings().knowledge_embeddings_enabled and pieces:
        state='offline'
        if not engine_pin:embedding_error='embedding_pin_missing'
        deadline=asyncio.get_running_loop().time()+18
        for piece in pieces[:16] if engine_pin else []:
            if asyncio.get_running_loop().time()>deadline:break
            try:
                async with asyncio.timeout(max(.001,deadline-asyncio.get_running_loop().time())):
                    vectors[piece['ordinal']]=await local_embed(piece['content'],ctx.get('knowledge_gateway'),
                        workspace_id=wid,actor_id=actor,brain_id=bid,brand_id=brand,write=True,purpose='knowledge_index',
                        request_key=f'knowledge-index:{jid}:{generation}:{piece["ordinal"]}',engine_pin=engine_pin,check=check)
            except Exception as error:
                embedding_error=error.code if isinstance(error,EngineFailure) else 'embedding_unavailable'
                break # one failure is enough; lexical index still commits
        if vectors:state='ready' if len(vectors)==len(pieces) else 'partial'
    async with Session.begin() as db:
        await db.execute(select(Brain.id).where(Brain.id==initial.brain_id).with_for_update())
        job=await db.scalar(select(KnowledgeIndexJob).where(KnowledgeIndexJob.id==jid).with_for_update())
        if not job or job.status!='running' or job.claim_id!=claim or job.embedding_generation!=generation:return
        try:await authorize(db,job)
        except HTTPException:
            job.status='failed';job.error_code='source_access_unavailable'
        else:
            if not settings().knowledge_embeddings_enabled:
                vectors={};state='disabled'
            for piece in pieces:
                cid=str(uuid5(NAMESPACE_URL,f'pao:{value.id}:{CHUNKER}:{piece["ordinal"]}'))
                chunk=await db.get(KnowledgeChunk,cid)
                if not chunk:
                    chunk=KnowledgeChunk(id=cid,version_id=value.id,brain_id=job.brain_id,workspace_id=job.workspace_id,
                        chunker_version=CHUNKER,**piece);db.add(chunk)
                elif chunk.sha256!=piece['sha256']:raise ValueError('chunk_hash_changed')
                # A quota/offline retry must not erase a previously good vector.
                if settings().knowledge_embeddings_enabled and job.embedding_engine==engine_pin and piece['ordinal'] in vectors:
                    chunk.embedding=vectors[piece['ordinal']];chunk.embedding_model=job.embedding_model
                    chunk.embedding_binding=digest(engine_pin)
            job.status='completed';job.embedding_status=state;job.error_code=embedding_error
        job.claim_id=None;job.locked_at=None;job.updated_at=now()

async def dispatch_indexes(ctx):
    if not settings().knowledge_enabled or not settings().knowledge_sources_enabled or not settings().brain_manager_enabled:return
    async with Session.begin() as db:
        # Parent Brain serialization also prevents API/cron duplicate job insertion.
        candidates=list(await db.execute(select(KnowledgeVersion,KnowledgeIngestion.actor_id).join(
            KnowledgeIngestion,KnowledgeIngestion.version_id==KnowledgeVersion.id).where(KnowledgeIngestion.status=='completed',
            KnowledgeIngestion.parser_version==service.PARSER_VERSION,~select(KnowledgeIndexJob.id).where(
                KnowledgeIndexJob.version_id==KnowledgeVersion.id,KnowledgeIndexJob.chunker_version==CHUNKER,
                KnowledgeIndexJob.embedding_model==settings().embedding_model).exists()).order_by(KnowledgeVersion.brain_id,KnowledgeVersion.id).limit(100)))
        for value,actor in candidates:
            await db.execute(select(Brain.id).where(Brain.id==value.brain_id).with_for_update())
            await ensure_job(db,value,actor)
    async with Session.begin() as db:
        expired=list(await db.scalars(select(KnowledgeIndexJob).where(KnowledgeIndexJob.status=='running',
            KnowledgeIndexJob.locked_at<now()-timedelta(seconds=60)).order_by(KnowledgeIndexJob.id).limit(100).with_for_update(skip_locked=True)))
        for job in expired:
            job.status='queued' if job.attempts<3 else 'failed';job.error_code='worker_lost';job.claim_id=None;job.locked_at=None;job.updated_at=now()
        queued=list(await db.execute(select(KnowledgeIndexJob.id,KnowledgeIndexJob.embedding_generation,KnowledgeIndexJob.attempts).where(KnowledgeIndexJob.status=='queued').order_by(KnowledgeIndexJob.created_at).limit(100)))
    for jid,generation,attempt in queued:
        await ctx['redis'].enqueue_job('index_source',jid,generation,_job_id=f'index:{jid}:{generation}:{attempt}',_expires=120)
