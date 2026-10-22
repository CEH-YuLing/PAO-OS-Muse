from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .ads_actions import create_action, decide_action
from .auth import Principal, principal, rate_limit
from .config import settings
from .db import database,Session
from .integrations.meta.api import connection
from .models import AdAction, AdActionAudit, Member

router=APIRouter(prefix='/v1/ads',tags=['meta-write'])
approval_router=APIRouter(prefix='/v1/approvals',tags=['ads-approval'])


class ActionInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    resource_type: Literal['campaign','adset','ad']
    resource_id: str=Field(pattern=r'^\d{1,64}$')
    action_type: Literal['pause','resume','update_budget']
    budget_minor_units: int|None=Field(None,ge=1,le=10**12)
    reason: str=Field(min_length=5,max_length=1000)
    confidence: Decimal|None=Field(None,ge=0,le=1,max_digits=5,decimal_places=4)
    source_agent: Literal['user','performance_analyst']='user'
    recommendation_id: UUID|None=None
    dry_run: bool=True
    request_key: UUID

    @model_validator(mode='after')
    def shape(self):
        if (self.action_type=='update_budget') != (self.budget_minor_units is not None):raise ValueError('Budget chỉ dùng cho update_budget')
        if self.action_type=='update_budget' and self.resource_type=='ad':raise ValueError('Ad không có daily budget trực tiếp')
        if self.source_agent=='performance_analyst' and not self.recommendation_id:raise ValueError('Performance Analyst action cần recommendation_id')
        return self


class ExecuteInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int=Field(ge=1)
    confirmation: Literal['CONFIRM']


class ApprovalDecision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version: int=Field(ge=1)
    reason: str|None=Field(None,max_length=500)


class ActionOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    recommendation_id: str|None
    platform: str
    account_id: str
    resource_type: str
    resource_id: str
    action_type: str
    before_state: dict
    proposed_state: dict
    after_state: dict
    compensating_action: dict
    reason: str
    confidence: Decimal|None
    source_agent: str
    approval_status: str
    execution_status: str
    dry_run: bool
    version: int
    approval_expires_at: datetime
    decision_channel: str|None
    policy_id: str|None
    policy_version: int|None
    policy_snapshot: dict
    approved_by: str|None
    approved_at: datetime|None
    executed_at: datetime|None
    result_24h: dict
    result_72h: dict
    result_7d: dict
    error_code: str|None
    created_at: datetime
    updated_at: datetime


class ActionAuditOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    actor_id: str
    event: str
    action_version: int
    data: dict
    created_at: datetime


class ActionDetail(BaseModel):
    action: ActionOut
    audit: list[ActionAuditOut]


class WriteStatus(BaseModel):
    enabled: bool
    mode: Literal['copilot']='copilot'
    dry_run_default: bool=True
    formal_approval_phase: int=12
    max_budget_change_pct: int


async def detail(db,action):
    rows=list(await db.scalars(select(AdActionAudit).where(AdActionAudit.action_id==action.id).order_by(AdActionAudit.created_at,AdActionAudit.id)))
    return ActionDetail(action=ActionOut.model_validate(action),audit=rows)


@router.get('/write-status',response_model=WriteStatus)
async def write_status(who: Principal=Depends(principal)):
    return WriteStatus(enabled=settings().meta_write_enabled,max_budget_change_pct=settings().meta_write_max_budget_change_pct)


@router.post('/actions',response_model=ActionDetail,status_code=201)
async def propose(body: ActionInput,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'ads-action-propose',who.id,10,60)
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta trước')
    action=await create_action(db,conn,who.id,body);await db.commit();return await detail(db,action)


@router.get('/actions',response_model=list[ActionOut])
async def actions(workspace_id: UUID,account_id: str|None=Query(None,pattern=r'^act_[0-9]{1,32}$'),
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    conditions=[AdAction.connection_id==conn.id,AdAction.connection_version==conn.version]
    if account_id:conditions.append(AdAction.account_id==account_id)
    return list(await db.scalars(select(AdAction).where(*conditions).order_by(AdAction.created_at.desc()).limit(100)))


@router.get('/actions/{action_id}',response_model=ActionDetail)
async def get_action(action_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    action=await db.get(AdAction,str(action_id))
    if not action or action.user_id!=who.id:raise HTTPException(404,'Không tìm thấy action')
    await connection(db,who,action.workspace_id)
    return await detail(db,action)


@router.post('/actions/{action_id}/execute',response_model=ActionDetail)
async def execute(action_id: UUID,body: ExecuteInput,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    raise HTTPException(409,'Phase 12 yêu cầu duyệt action qua /v1/approvals; worker sẽ thực thi sau khi approve')


async def approval_access(db,who,workspace_id,write=False):
    member=await db.get(Member,(str(workspace_id),who.id))
    if not member:raise HTTPException(404,'Không tìm thấy workspace')
    if write and member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được quyết định Ads approval')
    return member


@approval_router.get('',response_model=list[ActionOut])
async def approvals(workspace_id: UUID,status: Literal['pending','approved','rejected','expired','all']='pending',
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await approval_access(db,who,workspace_id)
    conditions=[AdAction.workspace_id==str(workspace_id)]
    if status!='all':conditions.append(AdAction.approval_status==status)
    return list(await db.scalars(select(AdAction).where(*conditions).order_by(AdAction.created_at.desc()).limit(100)))


@approval_router.get('/{action_id}',response_model=ActionDetail)
async def approval_detail(action_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    action=await db.get(AdAction,str(action_id))
    if not action:raise HTTPException(404,'Không tìm thấy approval')
    await approval_access(db,who,action.workspace_id)
    return await detail(db,action)


async def decision(action_id,body,request,who,kind):
    await rate_limit(request.app.state.redis,'ads-approval-decision',who.id,10,60)
    action=await decide_action(str(action_id),who.id,kind,body.version,'ui',body.reason)
    async with Session() as db:return await detail(db,action)


@approval_router.post('/{action_id}/approve',response_model=ActionDetail)
async def approve(action_id: UUID,body: ApprovalDecision,request: Request,who: Principal=Depends(principal)):
    return await decision(action_id,body,request,who,'approve')


@approval_router.post('/{action_id}/reject',response_model=ActionDetail)
async def reject(action_id: UUID,body: ApprovalDecision,request: Request,who: Principal=Depends(principal)):
    return await decision(action_id,body,request,who,'reject')
