from fastapi import HTTPException
from sqlalchemy import select
from ...access import membership
from ...config import settings
from ...models import Brain, BrainMember, Brand, User


def enabled():
    if not settings().brain_manager_enabled:
        raise HTTPException(503, 'Brain Manager chưa được bật')


async def require_brain(db, who, brain_id, write=False, allow_archived=False, lock=False):
    enabled()
    query = select(Brain).where(Brain.id == str(brain_id))
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    brain = await db.scalar(query)
    if not brain:
        raise HTTPException(404, 'Không tìm thấy Brain')
    await membership(db, brain.workspace_id, who, write)
    grant = await db.get(BrainMember, (brain.id, who.id))
    if brain.owner_id != who.id and not grant:
        raise HTTPException(404, 'Không tìm thấy Brain')
    if write and brain.owner_id != who.id and grant.role != 'editor':
        raise HTTPException(403, 'Brain chỉ cho phép đọc')
    if brain.archived_at and not allow_archived:
        raise HTTPException(409, 'Brain đã archive')
    return brain


async def default_brain(db, who, workspace_id, brand_id=None):
    # Owner lock serializes lazy creation; legacy content remains in memories.
    await membership(db, workspace_id, who)
    await db.execute(select(User.id).where(User.id == who.id).with_for_update())
    if brand_id:
        brand = await db.get(Brand, brand_id)
        if not brand or brand.workspace_id != workspace_id:
            raise HTTPException(404, 'Không tìm thấy Brand')
    brain = await db.scalar(select(Brain).where(Brain.workspace_id == workspace_id,
        Brain.owner_id == who.id, Brain.brand_id == brand_id, Brain.legacy_default.is_(True)))
    if not brain:
        brain = Brain(workspace_id=workspace_id, owner_id=who.id, brand_id=brand_id,
                      name='Legacy private memory', legacy_default=True)
        db.add(brain)
        await db.flush()
    return brain


async def legacy_facts(db, who, brain_id):
    brain = await require_brain(db, who, brain_id, allow_archived=True)
    # Explicit grant never grants the owner's private legacy facts.
    if not brain.legacy_default or brain.owner_id != who.id:
        return []
    from ...memory import scope
    from ...models import Memory
    return list(await db.scalars(select(Memory).where(
        *scope(brain.workspace_id, who.id, brain.brand_id), Memory.status != 'deleted')
        .order_by(Memory.updated_at.desc(), Memory.id).limit(100)))
