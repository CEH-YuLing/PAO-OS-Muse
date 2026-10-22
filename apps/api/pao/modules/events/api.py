"""Read-only unified inbox and bounded outbox diagnostics, no business execution."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal, rate_limit
from ...access import membership
from ...config import settings
from ...db import database, Session
from ...models import Task, ToolCall, AdAction, BusinessEvent, BusinessOutbox, BusinessReceipt, now
from . import approvals

router = APIRouter(prefix='/v1/business-events', tags=['business-events'])


class ApprovalStatus(BaseModel):
    enabled: bool
    producer_enabled: bool
    delivery_enabled: bool
    consumer: Literal['internal.audit.v1'] = 'internal.audit.v1'


class UnifiedApproval(BaseModel):
    id: str
    kind: Literal['task', 'tool', 'ads']
    workspace_id: str
    title: str
    version: int
    input_hash: str
    expires_at: datetime
    can_decide: bool
    ticket: str
    dry_run: bool | None
    review: dict


@router.get('/status', response_model=ApprovalStatus)
async def status(who: Principal = Depends(principal)):
    config = settings()
    return ApprovalStatus(enabled=config.unified_approvals_enabled,
        producer_enabled=config.business_events_enabled,
        delivery_enabled=config.business_events_enabled and config.business_event_delivery_enabled)


@router.get('/approvals', response_model=list[UnifiedApproval])
async def inbox(workspace_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    member = await membership(db, str(workspace_id), who)
    if not settings().unified_approvals_enabled: raise HTTPException(409, 'unified_approvals_disabled')
    wid = str(workspace_id); rows = []
    queries = {
        'task': select(Task).where(Task.workspace_id == wid, Task.status == 'waiting_approval'),
        'tool': select(ToolCall).where(ToolCall.workspace_id == wid, ToolCall.user_id == who.id, ToolCall.status == 'pending'),
        'ads': select(AdAction).where(AdAction.workspace_id == wid, AdAction.approval_status == 'pending', AdAction.execution_status == 'pending'),
    }
    for kind, query in queries.items():
        model = approvals.MODELS[kind]
        for row in await db.scalars(query.order_by(model.created_at.desc(), model.id).limit(50)):
            rows.append(await approvals.item(db, kind, row, who, member.role))
    return rows


class UnifiedDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ticket: str = Field(min_length=32, max_length=4096)
    decision: Literal['approve','reject']


class DecisionResult(BaseModel):
    id: str
    kind: Literal['task','tool','ads']
    status: str
    version: int


@router.post('/approvals/decision', response_model=DecisionResult)
async def decide(body: UnifiedDecision, request: Request, who: Principal = Depends(principal)):
    if not settings().unified_approvals_enabled: raise HTTPException(409,'unified_approvals_disabled')
    await rate_limit(request.app.state.redis,'unified-approval',who.id,20,60)
    claims = approvals.ticket(body.ticket,who)
    kind, ident = claims['kind'], claims['subject_id']
    if kind == 'task':
        from ...task_api import update_task, TaskPatch
        async with Session() as db:
            row = await db.get(Task,ident,with_for_update=True)
            if not row or row.workspace_id != claims['workspace_id']: raise HTTPException(404,'approval_not_found')
            await membership(db,row.workspace_id,who,True)
            if row.version!=claims['version'] or not approvals.pending(kind,row): raise HTTPException(409,'approval_changed')
            await approvals.require_snapshot(db,kind,row,claims['input_hash'])
            row = await update_task(UUID(ident),TaskPatch(version=claims['version'],status='completed' if body.decision=='approve' else 'failed'),who,db)
    elif kind == 'tool':
        from ...tool_gateway import decide as decide_tool
        row = await decide_tool(ident,who.id,body.decision,claims['version'],expected_hash=claims['input_hash'])
    else:
        from ...ads_actions import decide_action
        row = await decide_action(ident,who.id,body.decision,claims['version'],'ui',expected_hash=claims['input_hash'])
    return DecisionResult(id=row.id,kind=kind,status=row.approval_status if kind=='ads' else row.status,version=row.version)


class RevokeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)


@router.post('/approvals/{kind}/{subject_id}/revoke', response_model=DecisionResult)
async def revoke(kind: Literal['tool','ads'], subject_id: UUID, body: RevokeInput,
                 who: Principal = Depends(principal)):
    if not settings().unified_approvals_enabled: raise HTTPException(409,'unified_approvals_disabled')
    async with Session.begin() as db:
        row = await db.get(approvals.MODELS[kind],str(subject_id),with_for_update=True)
        if not row: raise HTTPException(404,'approval_not_found')
        member = await membership(db,row.workspace_id,who,True)
        if (kind=='tool' and row.user_id!=who.id) or (kind=='ads' and member.role not in ('owner','admin')):
            raise HTTPException(404,'approval_not_found')
        state = row.status if kind=='tool' else row.execution_status
        if row.version!=body.version or state not in ('pending','queued'): raise HTTPException(409,'approval_changed_or_already_executing')
        from ...models import now
        row.error_code='approval_revoked';row.version+=1;row.updated_at=now()
        if kind=='tool':
            row.status='cancelled'
            from ...tool_gateway import audit
            from ...models import Run
            audit(db,await db.get(Run,row.run_id),who.id,'approval.revoked',row)
        else:
            row.approval_status='rejected';row.execution_status='cancelled'
            from ...ads_actions import audit
            audit(db,row,who.id,'approval.revoked',channel='ui')
        return DecisionResult(id=row.id,kind=kind,status='cancelled',version=row.version)


class DeliveryDiagnostics(BaseModel):
    workspace_id: str
    states: dict[str,int]
    event_types: dict[str,int]
    receipts: int
    oldest_pending_at: datetime | None
    expired_leases: int
    dead_letters: list[dict]


@router.get('/diagnostics', response_model=DeliveryDiagnostics)
async def diagnostics(workspace_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db,str(workspace_id),who)
    if not settings().unified_approvals_enabled: raise HTTPException(409,'unified_approvals_disabled')
    wid=str(workspace_id)
    states=dict((await db.execute(select(BusinessOutbox.status,func.count()).where(BusinessOutbox.workspace_id==wid).group_by(BusinessOutbox.status))).all())
    types=dict((await db.execute(select(BusinessEvent.event_type,func.count()).where(BusinessEvent.workspace_id==wid).group_by(BusinessEvent.event_type))).all())
    receipts=await db.scalar(select(func.count()).select_from(BusinessReceipt).where(BusinessReceipt.workspace_id==wid))
    oldest=await db.scalar(select(func.min(BusinessOutbox.created_at)).where(BusinessOutbox.workspace_id==wid,BusinessOutbox.status=='pending'))
    expired=await db.scalar(select(func.count()).select_from(BusinessOutbox).where(BusinessOutbox.workspace_id==wid,BusinessOutbox.status=='processing',BusinessOutbox.lease_until<=now()))
    dead=await db.scalars(select(BusinessOutbox).where(BusinessOutbox.workspace_id==wid,BusinessOutbox.status=='dead_letter').order_by(BusinessOutbox.created_at.desc(),BusinessOutbox.id).limit(50))
    return DeliveryDiagnostics(workspace_id=wid,states=states,event_types=types,receipts=receipts,
        oldest_pending_at=oldest,expired_leases=expired,
        dead_letters=[{'id':row.id,'event_id':row.event_id,'attempts':row.attempts,'error_code':row.error_code} for row in dead])


class LedgerItem(BaseModel):
    id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    occurred_at: datetime
    content_hash: str
    payload_reference: dict


@router.get('/ledger', response_model=list[LedgerItem])
async def ledger(workspace_id: UUID, before: datetime | None = None, limit: int = Query(50,ge=1,le=100),
                 who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db,str(workspace_id),who)
    if not settings().unified_approvals_enabled: raise HTTPException(409,'unified_approvals_disabled')
    query=select(BusinessEvent).where(BusinessEvent.workspace_id==str(workspace_id))
    if before is not None: query=query.where(BusinessEvent.occurred_at<before)
    rows=await db.scalars(query.order_by(BusinessEvent.occurred_at.desc(),BusinessEvent.id).limit(limit))
    return [LedgerItem(**{key:getattr(row,key) for key in LedgerItem.model_fields}) for row in rows]
