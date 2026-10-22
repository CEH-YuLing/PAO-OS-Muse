"""One PostgreSQL transaction is the in-app delivery; no outbound side effect.

Pending commit precedes consumption. A crash rolls back consumption and the
existing worker retries pending records. Source lock precedes delivery lock
everywhere, including HTTP dedup. Failed authority is never auto retried.
"""
from fastapi import HTTPException
from sqlalchemy import select
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import ResultDelivery,GoalResultDelivery,Member,User,now
from .api import source

async def dispatch_one(Model,ident):
    if not settings().result_inbox_enabled:return
    async with Session.begin() as db:
        item=await db.get(Model,ident)
        if not item or item.status!='pending':return
        # Serialize current account/grant checks with concurrent revocation.
        ids=sorted({item.user_id,item.requested_by}-{None})
        await db.scalars(select(User).where(User.id.in_(ids)).order_by(User.id).with_for_update())
        await db.scalars(select(Member).where(Member.workspace_id==item.workspace_id,Member.user_id.in_(ids)).order_by(Member.user_id).with_for_update())
        reason=None
        sender=await db.get(User,item.requested_by) if item.requested_by else None
        recipient=await db.get(User,item.user_id)
        member=await db.get(Member,(item.workspace_id,item.requested_by)) if sender else None
        if not sender or not sender.active or not member or member.role=='viewer':reason='sender_permission_lost'
        elif not recipient or not recipient.active or not await db.get(Member,(item.workspace_id,item.user_id)):reason='recipient_permission_lost'
        else:
            try:
                _,fingerprint=await source(db,item.source_id,Principal(item.requested_by,0))
                if fingerprint!=item.source_hash:reason='source_changed'
            except HTTPException:reason='source_invalid'
        item=await db.scalar(select(Model).where(Model.id==ident).with_for_update().execution_options(populate_existing=True))
        if item.status!='pending':return
        if item.attempts>=5:reason='delivery_attempts_exhausted'
        else:item.attempts+=1
        item.status='failed' if reason else 'delivered';item.error_code=reason;item.updated_at=now()
        if not reason:item.delivered_at=now()

async def dispatch_results(ctx=None):
    if not settings().result_inbox_enabled:return {'processed':0}
    count=0
    for Model in (ResultDelivery,GoalResultDelivery):
        async with Session() as db:
            ids=list(await db.scalars(select(Model.id).where(Model.status=='pending').order_by(Model.created_at).limit(20)))
        for ident in ids:
            await dispatch_one(Model,ident);count+=1
    return {'processed':count}
