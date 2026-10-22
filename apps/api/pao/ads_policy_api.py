from datetime import datetime, time
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ads_policy import policy_audit, snapshot
from .auth import Principal, principal, rate_limit
from .access import membership
from .config import settings
from .db import database
from .models import AdEntity, AdsAutopilotPolicy, AdsPolicyAudit, MetaConnection, Workspace, now

router=APIRouter(prefix='/v1/ads/autopilot',tags=['ads-autopilot'])


class PolicyInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    mode: Literal['observer','advisor','copilot','autopilot']='observer'
    halted: bool=True
    pause_allowed: bool=False
    resume_allowed: bool=False
    budget_allowed: bool=False
    max_budget_change_pct: int=Field(10,ge=1,le=20)
    max_daily_budget_minor_units: int|None=Field(None,ge=1,le=10**15)
    minimum_impressions: int=Field(3000,ge=0,le=10**12)
    minimum_conversions: int=Field(3,ge=0,le=10**9)
    minimum_confidence: Decimal=Field(Decimal('.8'),ge=0,le=1,max_digits=5,decimal_places=4)
    freshness_minutes: int=Field(60,ge=15,le=1440)
    quiet_hours_enabled: bool=True
    quiet_start: time=time(23,0)
    quiet_end: time=time(7,0)
    max_actions_per_day: int=Field(3,ge=1,le=100)
    version: int|None=Field(None,ge=1)
    confirmation: str|None=Field(None,max_length=40)

    @model_validator(mode='after')
    def safe_enable(self):
        if self.budget_allowed and self.max_daily_budget_minor_units is None:
            raise ValueError('Budget Autopilot cần max_daily_budget_minor_units')
        if self.mode=='autopilot' and not self.halted and self.confirmation!='ENABLE AUTOPILOT':
            raise ValueError('Cần confirmation ENABLE AUTOPILOT')
        return self


class PolicyOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;connection_id: str;connection_version: int;workspace_id: str;account_id: str
    mode: str;halted: bool;pause_allowed: bool;resume_allowed: bool;budget_allowed: bool
    max_budget_change_pct: int;max_daily_budget_minor_units: int|None
    minimum_impressions: int;minimum_conversions: int;minimum_confidence: Decimal;freshness_minutes: int
    quiet_hours_enabled: bool;quiet_start: time;quiet_end: time;max_actions_per_day: int
    emergency_frozen: bool;freeze_reason: str|None;version: int;updated_by: str;updated_at: datetime;created_at: datetime


class PolicyAuditOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;actor_id: str;event: str;policy_version: int;data: dict;created_at: datetime


class PolicyDetail(BaseModel):
    policy: PolicyOut
    audit: list[PolicyAuditOut]
    global_enabled: bool
    meta_enabled: bool
    effective_autopilot: bool


class FreezeInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version: int=Field(ge=1)
    reason: str=Field(min_length=5,max_length=120)
    confirmation: Literal['FREEZE','UNFREEZE']


class AutopilotRuntimeStatus(BaseModel):
    global_enabled: bool
    meta_enabled: bool
    default_mode: Literal['observer']='observer'
    phase: int=13


@router.get('/status',response_model=AutopilotRuntimeStatus)
async def runtime_status(who: Principal=Depends(principal)):
    config=settings();return AutopilotRuntimeStatus(global_enabled=config.ads_autopilot_global_enabled,
        meta_enabled=config.meta_autopilot_enabled)


async def detail(db,policy):
    audits=list(await db.scalars(select(AdsPolicyAudit).where(AdsPolicyAudit.policy_id==policy.id)
        .order_by(AdsPolicyAudit.created_at,AdsPolicyAudit.id)))
    config=settings();effective=bool(config.ads_autopilot_global_enabled and config.meta_autopilot_enabled and
        policy.mode=='autopilot' and not policy.halted and not policy.emergency_frozen)
    return PolicyDetail(policy=policy,audit=audits,global_enabled=config.ads_autopilot_global_enabled,
        meta_enabled=config.meta_autopilot_enabled,effective_autopilot=effective)


@router.get('/policies',response_model=list[PolicyOut])
async def policies(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await membership(db,str(workspace_id),who)
    return list(await db.scalars(select(AdsAutopilotPolicy).where(AdsAutopilotPolicy.workspace_id==str(workspace_id))
        .order_by(AdsAutopilotPolicy.account_id)))


@router.get('/policies/{policy_id}',response_model=PolicyDetail)
async def get_policy(policy_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    policy=await db.get(AdsAutopilotPolicy,str(policy_id))
    if not policy:raise HTTPException(404,'Không tìm thấy Autopilot policy')
    await membership(db,policy.workspace_id,who)
    return await detail(db,policy)


@router.put('/policies',response_model=PolicyDetail)
async def put_policy(body: PolicyInput,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'ads-policy-write',who.id,10,60)
    member=await membership(db,str(body.workspace_id),who)
    if member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được cấu hình Autopilot')
    await db.execute(select(Workspace.id).where(Workspace.id==str(body.workspace_id)).with_for_update())
    policy=await db.scalar(select(AdsAutopilotPolicy).where(AdsAutopilotPolicy.workspace_id==str(body.workspace_id),
        AdsAutopilotPolicy.account_id==body.account_id).with_for_update())
    conn=await db.scalar(select(MetaConnection).join(AdEntity,(AdEntity.connection_id==MetaConnection.id)&
        (AdEntity.connection_version==MetaConnection.version)).where(MetaConnection.workspace_id==str(body.workspace_id),
        MetaConnection.status=='connected',MetaConnection.expires_at>now(),AdEntity.account_id==body.account_id,
        AdEntity.kind=='account').order_by(MetaConnection.created_at).limit(1))
    if not conn:raise HTTPException(409,'Kết nối và đồng bộ account vào warehouse trước khi cấu hình Autopilot')
    values=body.model_dump(exclude={'workspace_id','account_id','version','confirmation'})
    if policy:
        if body.version!=policy.version:raise HTTPException(409,'Policy đã thay đổi; tải lại trước khi lưu')
        before=snapshot(policy)
        for key,value in values.items():setattr(policy,key,value)
        policy.connection_version=conn.version;policy.updated_by=who.id;policy.version+=1;policy.updated_at=now()
        policy_audit(db,policy,who.id,'policy.updated',before=before,after=snapshot(policy))
    else:
        if body.version is not None:raise HTTPException(409,'Policy chưa tồn tại; bỏ version để tạo mới')
        policy=AdsAutopilotPolicy(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,
            account_id=body.account_id,updated_by=who.id,version=1,emergency_frozen=False,freeze_reason=None,**values)
        db.add(policy);await db.flush();policy_audit(db,policy,who.id,'policy.created',after=snapshot(policy))
    await db.commit();return await detail(db,policy)


async def change_freeze(policy_id,body,who,db,frozen):
    current=await db.get(AdsAutopilotPolicy,str(policy_id))
    if not current:raise HTTPException(404,'Không tìm thấy Autopilot policy')
    member=await membership(db,current.workspace_id,who)
    if member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được điều khiển Autopilot')
    await db.execute(select(Workspace.id).where(Workspace.id==current.workspace_id).with_for_update())
    policy=await db.scalar(select(AdsAutopilotPolicy).where(AdsAutopilotPolicy.id==str(policy_id)).with_for_update())
    if not policy:raise HTTPException(404,'Không tìm thấy Autopilot policy')
    expected='FREEZE' if frozen else 'UNFREEZE'
    if body.confirmation!=expected:raise HTTPException(422,f'Cần confirmation {expected}')
    if body.version!=policy.version:raise HTTPException(409,'Policy đã thay đổi; tải lại trước')
    before=snapshot(policy);policy.emergency_frozen=frozen;policy.freeze_reason=body.reason if frozen else None
    policy.halted=True
    if frozen:policy.mode='advisor'
    policy.version+=1;policy.updated_by=who.id;policy.updated_at=now()
    policy_audit(db,policy,who.id,'policy.frozen' if frozen else 'policy.unfrozen',before=before,reason=body.reason)
    await db.commit();return await detail(db,policy)


@router.post('/policies/{policy_id}/freeze',response_model=PolicyDetail)
async def freeze(policy_id: UUID,body: FreezeInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    return await change_freeze(policy_id,body,who,db,True)


@router.post('/policies/{policy_id}/unfreeze',response_model=PolicyDetail)
async def unfreeze(policy_id: UUID,body: FreezeInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    return await change_freeze(policy_id,body,who,db,False)
