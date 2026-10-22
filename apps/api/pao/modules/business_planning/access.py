"""Business authorization/source access shared by HTTP and fresh workers.

Never import the API/router from an execution service: worker import order differs
from ASGI startup, and must not silently depend on an already initialized router.
"""
from fastapi import HTTPException
from sqlalchemy import select
from ...config import settings
from ...models import Workspace,User,Member,Brand,BusinessProfile,BusinessProfileVersion,MonthlyPlan,MonthlyPlanVersion
from .contracts import digest


def reject(code,status=409):raise HTTPException(status,code)


async def authorize(db,wid,who,*,enabled=True):
    # Serializes business writes, but remains compatible with native resource
    # KEY SHARE locks while a model worker owns its Run row.
    workspace=await db.scalar(select(Workspace).where(Workspace.id==wid).with_for_update(key_share=True))
    user=await db.scalar(select(User).where(User.id==who.id).with_for_update(read=True).execution_options(populate_existing=True))
    member=await db.scalar(select(Member).where(Member.workspace_id==wid,Member.user_id==who.id).with_for_update(read=True).execution_options(populate_existing=True))
    if not workspace or not member or not user or not user.active:reject('business_planning_not_found',404)
    if enabled and member.role not in ('owner','admin'):reject('business_planning_manager_required',403)
    if enabled and not settings().business_planning_enabled:reject('business_planning_disabled',503)
    return member


async def brand_scope(db,wid,brand):
    if brand:
        row=await db.get(Brand,brand)
        if not row or row.workspace_id!=wid:reject('business_planning_not_found',404)


async def profile_scope(db,wid,pid):
    row=await db.scalar(select(BusinessProfile).where(BusinessProfile.id==pid,BusinessProfile.workspace_id==wid))
    if not row:reject('business_planning_not_found',404)
    await brand_scope(db,wid,row.brand_id)
    return row


async def profile_version(db,row,rev=None):
    version=await db.scalar(select(BusinessProfileVersion).where(BusinessProfileVersion.profile_id==row.id,
        BusinessProfileVersion.workspace_id==row.workspace_id,BusinessProfileVersion.revision==(rev or row.revision)))
    if not version:reject('business_planning_not_found',404)
    if digest(version.content)!=version.content_hash:reject('business_planning_integrity_failed')
    return version


async def selected_plan(db,wid,pid,revision=None):
    row=await db.scalar(select(MonthlyPlan).where(MonthlyPlan.id==pid,MonthlyPlan.workspace_id==wid))
    if not row:reject('business_planning_not_found',404)
    version=await db.scalar(select(MonthlyPlanVersion).where(MonthlyPlanVersion.plan_id==row.id,
        MonthlyPlanVersion.revision==(revision or row.revision)))
    if not version:reject('business_planning_not_found',404)
    return row,version
