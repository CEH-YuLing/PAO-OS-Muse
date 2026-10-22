from uuid import UUID
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal
from ...access import membership, owned_session, owned_run
from ...db import database
from ...config import settings
from ...models import Brain, BrainMember, Brand, ChatSession, Member, Run, now
from ...memory_schemas import MemoryOut
from .access import enabled, require_brain, default_brain, legacy_facts
from .schemas import BrainCreate, DefaultBrain, BrainPatch, BrainOut, BrainGrant, SessionBrain

router = APIRouter(prefix='/v1',tags=['brains'])


def clean_name(value):
    value = value.strip()
    if not value or any(unicodedata.category(c).startswith('C') for c in value):
        raise HTTPException(422,'Tên Brain không hợp lệ')
    return value


def revision_matches(brain, revision):
    if brain.revision != revision:
        raise HTTPException(409,'Brain đã thay đổi; tải lại trước khi sửa')


@router.get('/brains/status')
async def status(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await membership(db,str(workspace_id),who)
    return {'enabled':settings().brain_manager_enabled,'rag_enabled':False,'file_types':['text/plain','text/markdown']}


@router.get('/brains',response_model=list[BrainOut])
async def list_brains(workspace_id: UUID,archived: bool=False,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    enabled(); await membership(db,str(workspace_id),who)
    grant = exists(select(BrainMember.brain_id).where(BrainMember.brain_id==Brain.id,BrainMember.user_id==who.id))
    query = select(Brain).where(Brain.workspace_id==str(workspace_id),or_(Brain.owner_id==who.id,grant))
    if not archived:
        query = query.where(Brain.archived_at.is_(None))
    rows=list(await db.scalars(query.order_by(Brain.created_at,Brain.id).limit(100)))
    roles={brain_id:role for brain_id,role in await db.execute(select(BrainMember.brain_id,BrainMember.role).where(BrainMember.user_id==who.id,BrainMember.workspace_id==str(workspace_id)))}
    return [{**BrainOut.model_validate(row).model_dump(),'effective_role':'owner' if row.owner_id==who.id else roles.get(row.id,'reader')} for row in rows]


@router.post('/brains',response_model=BrainOut,status_code=201)
async def create_brain(body: BrainCreate,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    enabled(); wid=str(body.workspace_id); bid=str(body.brand_id) if body.brand_id else None
    await membership(db,wid,who,True)
    from ...models import User
    await db.execute(select(User.id).where(User.id==who.id).with_for_update())
    if len(list(await db.scalars(select(Brain.id).where(Brain.workspace_id==wid,Brain.owner_id==who.id).limit(100))))>=100:
        raise HTTPException(409,'Đã đạt giới hạn 100 Brain')
    if bid:
        brand = await db.get(Brand,bid)
        if not brand or brand.workspace_id != wid:
            raise HTTPException(404,'Không tìm thấy Brand')
    brain=Brain(workspace_id=wid,owner_id=who.id,brand_id=bid,name=clean_name(body.name))
    db.add(brain); await db.commit(); return brain


@router.post('/brains/default',response_model=BrainOut)
async def get_default(body: DefaultBrain,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    enabled(); await membership(db,str(body.workspace_id),who,True)
    brain=await default_brain(db,who,str(body.workspace_id),str(body.brand_id) if body.brand_id else None)
    await db.commit(); return brain


@router.patch('/brains/{brain_id}',response_model=BrainOut)
async def edit_brain(brain_id: UUID,body: BrainPatch,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,True,allow_archived=True,lock=True)
    if brain.owner_id != who.id:
        raise HTTPException(403,'Chỉ owner được quản lý Brain')
    revision_matches(brain,body.revision)
    if body.archived is True and await db.scalar(select(Run.id).where(Run.brain_id==brain.id,Run.status.in_(['queued','running'])).limit(1)):
        raise HTTPException(409,'Brain đang có run active')
    if body.name is not None:
        brain.name=clean_name(body.name)
    if body.archived is not None:
        brain.archived_at=now() if body.archived else None
    brain.revision+=1; await db.commit(); return brain


@router.put('/brains/{brain_id}/members/{user_id}')
async def grant_member(brain_id: UUID,user_id: UUID,body: BrainGrant,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,True,lock=True)
    if brain.owner_id != who.id or str(user_id)==who.id:
        raise HTTPException(403,'Chỉ owner được cấp quyền cho người khác')
    revision_matches(brain,body.revision)
    if not await db.get(Member,(brain.workspace_id,str(user_id))):
        raise HTTPException(404,'Người dùng không thuộc workspace')
    grant=await db.get(BrainMember,(brain.id,str(user_id)))
    if not grant:
        grant=BrainMember(brain_id=brain.id,workspace_id=brain.workspace_id,user_id=str(user_id),role=body.role)
        db.add(grant)
    else:
        grant.role=body.role
    brain.revision+=1; await db.commit()
    return {'revision':brain.revision,'role':grant.role,'legacy_memory_shared':False}


@router.delete('/brains/{brain_id}/members/{user_id}')
async def revoke_member(brain_id: UUID,user_id: UUID,revision: int=Query(ge=1),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,True,allow_archived=True,lock=True)
    if brain.owner_id != who.id:
        raise HTTPException(403,'Chỉ owner được thu hồi quyền')
    revision_matches(brain,revision)
    grant=await db.get(BrainMember,(brain.id,str(user_id)))
    if grant:
        await db.delete(grant)
    brain.revision+=1; await db.commit(); return {'revision':brain.revision}


@router.get('/brains/{brain_id}/memory',response_model=list[MemoryOut])
async def legacy_memory(brain_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    return await legacy_facts(db,who,brain_id)


@router.get('/sessions/{session_id}/brain')
async def session_brain(session_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    enabled(); chat=await owned_session(db,session_id,who)
    if chat.brain_id:
        await require_brain(db,who,chat.brain_id,allow_archived=True)
    return {'brain_id':chat.brain_id,'version':chat.brain_version}


@router.put('/sessions/{session_id}/brain')
async def switch_brain(session_id: UUID,body: SessionBrain,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    enabled(); await owned_session(db,session_id,who,True)
    chat=await db.scalar(select(ChatSession).where(ChatSession.id==str(session_id)).with_for_update().execution_options(populate_existing=True))
    if chat.brain_version != body.version:
        raise HTTPException(409,'Session đã thay đổi')
    if await db.scalar(select(Run.id).where(Run.session_id==chat.id,Run.status.in_(['queued','running'])).limit(1)):
        raise HTTPException(409,'Không đổi Brain khi run active')
    brain=await require_brain(db,who,body.brain_id,True,lock=True)
    if brain.workspace_id != chat.workspace_id or brain.brand_id != chat.brand_id:
        raise HTTPException(409,'Brain phải cùng workspace/brand với session')
    chat.brain_id=brain.id; chat.brain_version+=1
    await db.commit(); return {'brain_id':chat.brain_id,'version':chat.brain_version}


@router.get('/runs/{run_id}/brain')
async def run_brain(run_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    enabled(); run=await owned_run(db,run_id,who)
    return {'brain_id':run.brain_id,'revision':run.brain_revision,'context':run.brain_context}
