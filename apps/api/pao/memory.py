"""Scoped SQL facts and pgvector retrieval. No provider calls outside the gateway."""
import asyncio
import hashlib
import re
import unicodedata
from datetime import timedelta
from sqlalchemy import select, func
from fastapi import HTTPException
from .config import settings
from .db import Session
from .models import Memory, MemoryJob, Run, ChatSession, User, Member, now
from .gateway import OllamaGateway
from .modules.engines.contract import EngineFailure


def normalize(value):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def fingerprint(value):
    return hashlib.sha256(normalize(value).encode()).hexdigest()


def scope(workspace_id, user_id, brand_id):
    return (Memory.workspace_id == workspace_id, Memory.user_id == user_id,
            Memory.brand_id == brand_id if brand_id else Memory.brand_id.is_(None))


async def lock_owner(db, user_id):
    await db.execute(select(User.id).where(User.id == user_id).with_for_update())


async def vectorize(value, gateway=None, **scope_args):
    try:
        from .modules.connections.embedding_resources import embed
        return await embed(value,gateway=gateway,**scope_args)
    except Exception:
        return None, None


async def store_fact(db, workspace_id, user_id, brand_id, fact, vector, model, source_run_id=None):
    # All writers hold the owner row lock; unique indexes enforce final invariants.
    filters = scope(workspace_id, user_id, brand_id)
    existing = await db.scalar(select(Memory).where(*filters, Memory.fingerprint == fingerprint(fact.value)))
    if existing:
        return existing, False
    if await db.scalar(select(func.count()).select_from(Memory).where(*filters)) >= 1000:
        raise HTTPException(409, 'Phạm vi memory đã đạt giới hạn 1000 bản ghi')
    conflict = await db.scalar(select(Memory.id).where(*filters, Memory.key == normalize(fact.key), Memory.status == 'active'))
    memory = Memory(workspace_id=workspace_id, user_id=user_id, brand_id=brand_id,
                    key=normalize(fact.key), value=fact.value, fingerprint=fingerprint(fact.value),
                    status='pending' if conflict else 'active', importance=fact.importance,
                    embedding=vector, embedding_model=model, source_run_id=source_run_id)
    db.add(memory)
    await db.flush()
    return memory, True


def words(value):
    plain = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))
    stop = {'toi','la','gi','cua','va','cho','co','the','a','is','what','my','the','in','to','thi','nao','ban'}
    return set(re.findall(r'\w+', plain)) - stop


async def retrieve(workspace_id, user_id, brand_id, query, gateway=None, *,engine_pin=None,require_pin=False):
    filters = (*scope(workspace_id, user_id, brand_id), Memory.status == 'active')
    async with Session() as db:
        if not await db.scalar(select(Memory.id).where(*filters).limit(1)):
            return [], False
    # Reserve most of the run budget for the reply even when embedding stalls.
    try:
        async with asyncio.timeout(min(30, settings().memory_timeout_seconds)):
            vector, model = ((None,None) if require_pin and not engine_pin else
                await vectorize(query,gateway,workspace_id=workspace_id,actor_id=user_id,
                    brand_id=brand_id,purpose='memory_query',engine_pin=engine_pin))
    except TimeoutError:
        vector = None
    degraded = vector is None
    async with Session() as db:
        from .modules.connections.embedding_resources import authorize
        await authorize(db,workspace_id,user_id,brand_id,None,False,None)
        candidates = {m.id: (m, 0.0) for m in await db.scalars(select(Memory).where(*filters)
            .order_by(Memory.updated_at.desc()).limit(1000))}
        if vector is not None:
            distance = Memory.embedding.cosine_distance(vector)
            rows = await db.execute(select(Memory, distance).where(*filters,
                Memory.embedding_model == model, Memory.embedding.is_not(None))
                .order_by(distance).limit(40))
            for memory, dist in rows:
                candidates[memory.id] = (memory, max(0.0, min(1.0, 1 - float(dist))))
        query_words = words(query)
        ranked = []
        for memory, similarity in candidates.values():
            overlap = len(query_words & words(memory.key + ' ' + memory.value)) / max(1, len(query_words))
            if similarity < settings().memory_min_similarity and not overlap:
                continue
            recency = 1 / (1 + max(0, (now() - memory.updated_at).total_seconds()) / (30 * 86400))
            score = 0.65 * similarity + 0.15 * overlap + 0.1 * recency + 0.1 * memory.importance / 5
            ranked.append((memory, round(score, 5)))
        ranked.sort(key=lambda pair: (-pair[1], pair[0].id))
        return ranked[:settings().memory_top_k], degraded


async def extract_memory(ctx, run_id):
    extraction_gateway = None
    async with Session.begin() as db:
        job = await db.scalar(select(MemoryJob).where(MemoryJob.run_id == run_id).with_for_update())
        if not job or job.status != 'queued':
            return
        run = await db.get(Run, run_id)
        chat = await db.get(ChatSession, run.session_id)
        user = await db.get(User, chat.user_id)
        member = await db.get(Member, (chat.workspace_id, chat.user_id))
        if not user.active or not member or member.role == 'viewer':
            job.status, job.error_code = 'failed', 'access_revoked'
            return
        if not settings().memory_enabled or not chat.memory_enabled or run.status != 'completed':
            job.status, job.error_code = 'completed', 'memory_disabled'
            return
        job.status, job.updated_at = 'running', now()
        job.attempts += 1
        attempt = job.attempts
        prompt, workspace_id, user_id, brand_id = run.prompt, chat.workspace_id, chat.user_id, chat.brand_id
        if run.brain_id:
            from .modules.brains.context import memory_scope as pinned_scope
            try:
                pinned = await pinned_scope(db, run, chat)
            except Exception:
                pinned = None
            if not pinned:
                job.status, job.error_code = 'completed', 'brain_memory_disabled'
                return
            workspace_id, user_id, brand_id = pinned
        if settings().chat_features_enabled:
            pinned = (run.engine_snapshot or {}).get('memory_engine')
            if not pinned:
                job.status, job.error_code = 'failed', 'memory_engine_not_pinned'
                return
            from .modules.chat.ledger import AccountingEngine
            if pinned == {'mode': 'run_engine'}:
                from .modules.engines.service import gateway_for_run
                try:
                    selected = await gateway_for_run(db, run)
                except EngineFailure as failure:
                    job.status, job.error_code = 'failed', failure.code
                    return
                extraction_gateway = AccountingEngine(selected, run,
                    source_prefix='memory_extraction', request_key=f'memory:{attempt}')
            else:
                extraction_gateway = AccountingEngine(ctx.get('memory_gateway') or OllamaGateway(
                    model=pinned['model'],url=pinned['url']),run,source_prefix='memory_extraction',request_key=f'memory:{attempt}')
        else:
            from .modules.connections.model_fence import unregistered
            try:
                await unregistered(db, workspace_id)
                from .modules.connections.resources import require_accounted
                await require_accounted(db,workspace_id) # Also before injected/test gateways.
            except EngineFailure as failure:
                job.status, job.error_code = 'failed', failure.code
                return
    # Production leaves this unset so admission constructs the pinned local
    # adapter; never pass an unpinned default that follows changed host settings.
    embedding_gateway = ctx.get('embedding_gateway') or ctx.get('memory_gateway')
    try:
        async with asyncio.timeout(settings().memory_timeout_seconds):
            extracted = await extraction_gateway.extract(prompt)
            # Validate even test/custom gateways; model cannot choose the storage scope.
            from .memory_schemas import ExtractedFacts
            extracted = ExtractedFacts.model_validate(extracted)
            valid = [f for f in extracted.facts if f.value in prompt and f.importance >= 3]
            embedding_pin=(run.engine_snapshot or {}).get('embedding_engine')
            async def still_owned(fresh):
                from .modules.brains.context import memory_scope as pinned_scope,check_run_brain
                current=await fresh.get(Run,run_id);chat=await fresh.get(ChatSession,current.session_id)
                pending=await fresh.get(MemoryJob,run_id)
                if (not settings().memory_enabled or not settings().chat_features_enabled or not chat.memory_enabled
                    or pending.status!='running' or pending.attempts!=attempt):
                    raise EngineFailure('embedding_access_revoked')
                await check_run_brain(fresh,current,chat)
                if current.brain_id and await pinned_scope(fresh,current,chat)!=(workspace_id,user_id,brand_id):
                    raise EngineFailure('embedding_scope_denied')
            vectors = [await vectorize(f'{f.key}: {f.value}',embedding_gateway,
                workspace_id=workspace_id,actor_id=user_id,brand_id=brand_id,write=True,
                purpose='memory_fact',request_key='memory-vector:'+run_id+':'+fingerprint(f'{f.key}: {f.value}'),
                check=still_owned,engine_pin=embedding_pin) if embedding_pin else (None,None) for f in valid]
        async with Session.begin() as db:
            if not settings().chat_features_enabled:
                from .modules.connections.model_fence import unregistered
                try:
                    await unregistered(db, workspace_id)
                    from .modules.connections.resources import require_accounted
                    await require_accounted(db,workspace_id)
                except EngineFailure as failure:
                    job = await db.scalar(select(MemoryJob).where(MemoryJob.run_id == run_id).with_for_update())
                    if job.status == 'running' and job.attempts == attempt:
                        job.status, job.error_code, job.updated_at = 'failed', failure.code, now()
                    return
            await lock_owner(db, user_id)
            job = await db.scalar(select(MemoryJob).where(MemoryJob.run_id == run_id).with_for_update())
            if job.status != 'running' or job.attempts != attempt:
                return
            # Recheck revocation/opt-out after slow provider work, before writing facts.
            user = await db.get(User, user_id)
            member = await db.get(Member, (workspace_id, user_id))
            chat = await db.get(ChatSession, run.session_id)
            if not user.active or not member or member.role == 'viewer' or not chat.memory_enabled:
                job.status, job.error_code, job.updated_at = 'failed', 'access_revoked_or_disabled', now()
                return
            if run.brain_id:
                try:
                    pinned = await pinned_scope(db, run, chat)
                except Exception:
                    pinned = None
                if pinned != (workspace_id, user_id, brand_id):
                    job.status, job.error_code, job.updated_at = 'failed', 'brain_access_revoked', now()
                    return
            count = 0
            for fact, (vector, model) in zip(valid, vectors):
                _, created = await store_fact(db, workspace_id, user_id, brand_id, fact, vector, model, run_id)
                count += int(created)
            job.status, job.extracted, job.updated_at = 'completed', count, now()
            job.error_code = 'embedding_unavailable' if any(v is None for v, _ in vectors) else None
    except asyncio.CancelledError:
        raise  # Durable running lease is recovered by dispatch after process failure.
    except Exception as failure:
        # Authority failures are terminal: do not retry against a changed
        # default connection or silently choose local after revocation.
        async with Session.begin() as db:
            job = await db.scalar(select(MemoryJob).where(MemoryJob.run_id == run_id).with_for_update())
            if job.status == 'running' and job.attempts == attempt:
                terminal = isinstance(failure,EngineFailure) and failure.code in (
                    'tenant_resource_accounting_required','engine_attempt_replay_denied','tenant_resource_replay_denied',
                    'engine_connection_authority_not_activated','engine_connection_access_revoked',
                    'engine_connection_changed','engine_connection_unavailable')
                job.status = 'failed' if terminal else 'queued' if attempt < 2 else 'failed'
                job.error_code, job.updated_at = failure.code if terminal else 'extraction_unavailable', now()


async def dispatch_memory(ctx):
    async with Session.begin() as db:
        stale = list(await db.scalars(select(MemoryJob).where(MemoryJob.status == 'running',
            MemoryJob.updated_at < now() - timedelta(seconds=settings().memory_timeout_seconds + 60))
            .with_for_update(skip_locked=True)))
        for job in stale:
            job.status = 'queued' if job.attempts < 2 else 'failed'
            job.error_code, job.updated_at = 'memory_worker_lost', now()
        pending = list(await db.scalars(select(MemoryJob.run_id).where(MemoryJob.status == 'queued')
            .order_by(MemoryJob.updated_at).limit(50)))
    for run_id in pending:
        await ctx['redis'].enqueue_job('extract_memory', run_id, _job_id=f'memory:{run_id}', _expires=3600)
