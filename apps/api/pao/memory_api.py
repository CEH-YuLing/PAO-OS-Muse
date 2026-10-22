from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import Principal, principal, rate_limit
from .access import membership, owned_session
from .db import database
from .models import Brand, Memory, MemoryJob, Run, now
from .memory import scope, fingerprint, normalize, lock_owner, store_fact, vectorize, retrieve
from .memory_schemas import (BrandCreate, BrandOut, MemoryCreate, MemoryPatch, MemoryOut,
    MemorySearch, MemorySearchResult, MemoryHit, MemoryStatus, MemoryToggle)
from .schemas import SessionOut
from .config import settings
from .modules.connections.embedding_resources import authorize
from .modules.engines.contract import EngineFailure

router = APIRouter(prefix='/v1', tags=['memory'])


async def fresh_scope(db,wid,actor,bid,write):
    try:await authorize(db,wid,actor,bid,None,write,None,lock=write)
    except EngineFailure as error:raise HTTPException(403,error.code) from None


async def require_scope(db, who, workspace_id, brand_id=None, write=False):
    await membership(db, workspace_id, who, write)
    if brand_id:
        brand = await db.get(Brand, brand_id)
        if not brand or brand.workspace_id != workspace_id:
            raise HTTPException(404, 'Không tìm thấy brand trong workspace')


async def owned_memory(db, who, memory_id, write=False):
    memory = await db.get(Memory, str(memory_id))
    if not memory or memory.user_id != who.id or memory.status == 'deleted':
        raise HTTPException(404, 'Không tìm thấy memory')
    await membership(db, memory.workspace_id, who, write)
    return memory


@router.get('/brands', response_model=list[BrandOut])
async def brands(workspace_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db, str(workspace_id), who)
    return list(await db.scalars(select(Brand).where(Brand.workspace_id == str(workspace_id)).order_by(Brand.name).limit(100)))


@router.post('/brands', response_model=BrandOut, status_code=201)
async def create_brand(body: BrandCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .models import Workspace
    await membership(db, str(body.workspace_id), who, True)
    await db.execute(select(Workspace.id).where(Workspace.id == str(body.workspace_id)).with_for_update())
    existing = await db.scalar(select(Brand).where(Brand.workspace_id == str(body.workspace_id), Brand.name == body.name))
    if existing:
        return existing
    brand = Brand(workspace_id=str(body.workspace_id), name=body.name)
    db.add(brand); await db.commit()
    return brand


@router.patch('/sessions/{session_id}', response_model=SessionOut)
async def toggle_memory(session_id: UUID, body: MemoryToggle, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    session = await owned_session(db, session_id, who, True)
    session.memory_enabled = body.memory_enabled
    await db.commit()
    return session


@router.get('/memory/status', response_model=MemoryStatus)
async def memory_status(session_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    session = await owned_session(db, session_id, who)
    job = await db.scalar(select(MemoryJob).join(Run, Run.id == MemoryJob.run_id)
        .where(Run.session_id == session.id).order_by(Run.created_at.desc()).limit(1))
    return MemoryStatus(enabled=settings().memory_enabled and session.memory_enabled,
        run_id=job.run_id if job else None,
        job_status=job.status if job else None, extracted=job.extracted if job else 0,
        error_code=job.error_code if job else None)


@router.get('/memory', response_model=list[MemoryOut])
async def list_memory(workspace_id: UUID, brand_id: UUID | None = None,
                      offset: int = Query(0, ge=0), who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    wid, bid = str(workspace_id), str(brand_id) if brand_id else None
    await require_scope(db, who, wid, bid)
    return list(await db.scalars(select(Memory).where(*scope(wid, who.id, bid), Memory.status != 'deleted')
        .order_by(Memory.updated_at.desc(), Memory.id).offset(offset).limit(100)))


@router.post('/memory', response_model=MemoryOut, status_code=201)
async def create_memory(body: MemoryCreate, request: Request, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    wid, bid = str(body.workspace_id), str(body.brand_id) if body.brand_id else None
    await require_scope(db, who, wid, bid, True)
    await rate_limit(request.app.state.redis, 'memory-write', who.id, 20, 60)
    await db.rollback() # No request transaction through embedding I/O.
    vector, model = await vectorize(f'{body.key}: {body.value}',workspace_id=wid,
        actor_id=who.id,brand_id=bid,write=True,purpose='memory_create')
    await lock_owner(db, who.id)
    await fresh_scope(db,wid,who.id,bid,True)
    memory, _ = await store_fact(db, wid, who.id, bid, body, vector, model)
    if memory.status == 'deleted':
        raise HTTPException(409, 'Thông tin này đã bị xóa; không tự phục hồi bản đã xóa')
    await db.commit()
    return memory


@router.post('/memory/search', response_model=MemorySearchResult)
async def search_memory(body: MemorySearch, request: Request, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    wid, bid = str(body.workspace_id), str(body.brand_id) if body.brand_id else None
    await require_scope(db, who, wid, bid)
    await rate_limit(request.app.state.redis, 'memory-search', who.id, 20, 60)
    await db.rollback()
    try:hits, degraded = await retrieve(wid, who.id, bid, body.query)
    except EngineFailure as error:raise HTTPException(403,error.code) from None
    return MemorySearchResult(items=[MemoryHit(memory=MemoryOut.model_validate(m), score=score) for m, score in hits], degraded=degraded)


@router.patch('/memory/{memory_id}', response_model=MemoryOut)
async def edit_memory(memory_id: UUID, body: MemoryPatch, request: Request,
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    current=await owned_memory(db, who, memory_id, True)
    wid,bid=current.workspace_id,current.brand_id
    if current.version!=body.version:raise HTTPException(409,'Memory đã thay đổi. Tải lại trước khi sửa')
    await rate_limit(request.app.state.redis, 'memory-write', who.id, 20, 60)
    await db.rollback()
    async def check(fresh):
        row=await owned_memory(fresh,who,memory_id,True)
        if row.version!=body.version or row.workspace_id!=wid or row.brand_id!=bid:
            raise HTTPException(409,'Memory đã thay đổi. Tải lại trước khi sửa')
    vector, model = await vectorize(f'{body.key}: {body.value}',workspace_id=wid,
        actor_id=who.id,brand_id=bid,write=True,purpose='memory_edit',check=check)
    await lock_owner(db, who.id)
    await fresh_scope(db,wid,who.id,bid,True)
    memory = await db.scalar(select(Memory).where(Memory.id == str(memory_id)).with_for_update().execution_options(populate_existing=True))
    if memory.status == 'deleted' or memory.version != body.version:
        raise HTTPException(409, 'Memory đã thay đổi. Tải lại trước khi sửa')
    filters = scope(memory.workspace_id, who.id, memory.brand_id)
    duplicate = await db.scalar(select(Memory.id).where(*filters, Memory.id != memory.id,
        Memory.fingerprint == fingerprint(body.value)))
    if duplicate:
        raise HTTPException(409, 'Nội dung trùng một memory khác')
    key = normalize(body.key)
    if body.status == 'active':
        await db.execute(update(Memory).where(*filters, Memory.id != memory.id, Memory.key == key, Memory.status == 'active')
            .values(status='superseded', version=Memory.version + 1, updated_at=now()))
    memory.key, memory.value, memory.importance, memory.status = key, body.value, body.importance, body.status
    memory.fingerprint, memory.embedding, memory.embedding_model = fingerprint(body.value), vector, model
    memory.version += 1; memory.updated_at = now()
    await db.commit()
    return memory


@router.delete('/memory/{memory_id}', status_code=204)
async def delete_memory(memory_id: UUID, version: int = Query(ge=1),
                        who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await owned_memory(db, who, memory_id, True)
    await lock_owner(db, who.id)
    memory = await db.scalar(select(Memory).where(Memory.id == str(memory_id)).with_for_update().execution_options(populate_existing=True))
    if memory.version != version or memory.status == 'deleted':
        raise HTTPException(409, 'Memory đã thay đổi. Tải lại trước khi xóa')
    memory.status, memory.key, memory.value = 'deleted', '', ''
    memory.embedding, memory.embedding_model = None, None
    memory.version += 1; memory.updated_at = now()
    await db.commit()
