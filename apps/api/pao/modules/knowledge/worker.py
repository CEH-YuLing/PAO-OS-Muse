"""Durable DB outbox, bounded retry and claim fencing; Redis is delivery only."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import KnowledgeIngestion,KnowledgeVersion,KnowledgeSource,User,now
from . import service

async def authorized(db,job,lock=False):
    user=await db.get(User,job.actor_id)
    if not user or not user.active:raise HTTPException(403,'Actor không active')
    await service.access(db,Principal(job.actor_id,0),job.brain_id,True,lock)
    value=await db.get(KnowledgeVersion,job.version_id)
    source=await db.get(KnowledgeSource,value.source_id)
    if source.archived_at:raise HTTPException(409,'Source archived')
    raw=await service.raw_version(db,source,value)
    return raw

async def ingest_source(ctx,job_id):
    if not settings().knowledge_sources_enabled or not settings().brain_manager_enabled:return
    claim=str(uuid4())
    async with Session.begin() as db:
        # Shared order across API/worker: Brain -> job. Never hold a job then Brain.
        initial=await db.get(KnowledgeIngestion,job_id)
        if not initial or initial.status!='queued':return
        from ...models import Brain
        await db.execute(select(Brain.id).where(Brain.id==initial.brain_id).with_for_update())
        job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.id==job_id).with_for_update().execution_options(populate_existing=True))
        if job.status!='queued':return
        if job.attempts>=3:
            job.status='failed';job.error_code='retry_exhausted';return
        job.attempts+=1;job.updated_at=now()
        try:
            if job.parser_version!=service.PARSER_VERSION:raise HTTPException(409,'Unsupported parser')
            raw=await authorized(db,job)
        except HTTPException:
            job.status='failed';job.error_code='source_access_unavailable';return
        job.status='running';job.locked_at=now();job.claim_id=claim;job.error_code=None
    error=None;parsed=None
    try:
        async with asyncio.timeout(20):
            parsed=await asyncio.to_thread(service.parse_text,raw)
    except asyncio.CancelledError:raise # durable running lease recovered by dispatcher
    except Exception:error='parse_unavailable'
    async with Session.begin() as db:
        from ...models import Brain
        await db.execute(select(Brain.id).where(Brain.id==initial.brain_id).with_for_update())
        job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.id==job_id).with_for_update())
        if not job or job.status!='running' or job.claim_id!=claim:return
        try:await authorized(db,job)
        except HTTPException:error='source_access_unavailable'
        if error:job.status='failed';job.error_code=error
        else:job.parsed_text,job.parsed_sha256,job.line_count=parsed;job.status='completed'
        job.locked_at=None;job.claim_id=None;job.updated_at=now()

async def dispatch_sources(ctx):
    if not settings().knowledge_sources_enabled or not settings().brain_manager_enabled:return
    async with Session.begin() as db:
        expired=list(await db.scalars(select(KnowledgeIngestion).where(KnowledgeIngestion.status=='running',
            KnowledgeIngestion.locked_at<now()-timedelta(seconds=60)).order_by(KnowledgeIngestion.id).limit(100).with_for_update(skip_locked=True)))
        for job in expired:
            job.status='queued' if job.attempts<3 else 'failed';job.error_code='worker_lost'
            job.claim_id=None;job.locked_at=None;job.updated_at=now()
        queued=list(await db.execute(select(KnowledgeIngestion.id,KnowledgeIngestion.attempts).where(
            KnowledgeIngestion.status=='queued').order_by(KnowledgeIngestion.created_at,KnowledgeIngestion.id).limit(100)))
    for jid,attempt in queued:
        # Attempt suffix permits recovery while a stale Redis job id still exists.
        await ctx['redis'].enqueue_job('ingest_source',jid,_job_id=f'source:{jid}:{attempt}',_expires=120)
