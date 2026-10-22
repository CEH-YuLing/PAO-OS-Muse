import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .access import membership
from .auth import Principal,principal
from .config import settings
from .db import database
from .models import AutomationOutbox,AutomationWorkflow,AutomationWorkflowAudit,Member,now

router=APIRouter(prefix='/v1/automation',tags=['automation'])

class StartIn(BaseModel):
    workspace_id: UUID
    request_key: str=Field(min_length=8,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')
    kind: Literal['approval_wait','follow_up']
    payload: dict=Field(default_factory=dict)
    approval_required: bool=True
    approval_timeout_hours: int=Field(default=24,ge=1,le=168)
    wait_until: datetime|None=None
    @field_validator('payload')
    @classmethod
    def bounded(cls,v):
        import json
        if len(json.dumps(v,ensure_ascii=False))>16_000:raise ValueError('payload quá lớn')
        return v
    @field_validator('wait_until')
    @classmethod
    def future(cls,v):
        if v and (v.tzinfo is None or v<=datetime.now(timezone.utc)):raise ValueError('wait_until phải ở tương lai và có timezone')
        return v

class DecisionIn(BaseModel):
    version:int=Field(ge=1)
    decision:Literal['approve','reject']

class WorkflowOut(BaseModel):
    model_config={'from_attributes':True}
    id:str;workspace_id:str;request_key:str;temporal_workflow_id:str;temporal_run_id:str|None
    kind:str;status:str;approval_status:str;payload:dict;result:dict;error_code:str|None
    wait_until:datetime|None;version:int;created_at:datetime;updated_at:datetime;completed_at:datetime|None


def request_fingerprint(body: StartIn) -> str:
    canonical = {
        'kind': body.kind,
        'payload': body.payload,
        'approval_required': body.approval_required,
        'approval_timeout_hours': body.approval_timeout_hours,
        'wait_until': body.wait_until.astimezone(timezone.utc).isoformat() if body.wait_until else None,
    }
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def enqueue(db: AsyncSession, row: AutomationWorkflow, operation: str, payload: dict,
            *, signal_name: str | None = None, suffix: str) -> None:
    db.add(AutomationOutbox(
        workflow_id=row.id, workspace_id=row.workspace_id,
        dedupe_key=f'{row.id}:{suffix}', operation=operation,
        signal_name=signal_name, payload=payload,
    ))

@router.get('/status')
async def status():
    return {'enabled':settings().temporal_enabled,'address':settings().temporal_address if settings().temporal_enabled else None,
            'namespace':settings().temporal_namespace,'task_queue':settings().temporal_task_queue}

@router.post('/workflows',response_model=WorkflowOut,status_code=202)
async def start(body:StartIn,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    member=await membership(db,str(body.workspace_id),who,True)
    if member.role not in ('owner','admin','operator'):raise HTTPException(403,'Cần quyền operator trở lên')
    if not settings().temporal_enabled:raise HTTPException(503,'Temporal chưa được bật')
    fingerprint=request_fingerprint(body)
    existing=await db.scalar(select(AutomationWorkflow).where(AutomationWorkflow.workspace_id==str(body.workspace_id),AutomationWorkflow.request_key==body.request_key))
    if existing:
        if existing.request_fingerprint!=fingerprint:raise HTTPException(409,'request_key đã dùng với nội dung khác')
        return existing
    row=AutomationWorkflow(workspace_id=str(body.workspace_id),user_id=who.id,request_key=body.request_key,
        request_fingerprint=fingerprint,temporal_workflow_id=f'pao-{body.workspace_id}-{body.request_key}',kind=body.kind,status='starting',
        approval_status='pending' if body.approval_required else 'not_required',payload=body.payload,wait_until=body.wait_until)
    db.add(row)
    try:
        await db.flush()
        db.add(AutomationWorkflowAudit(workflow_id=row.id,workspace_id=row.workspace_id,actor_id=who.id,event='created',workflow_version=1,data={'kind':row.kind}))
        item={'id':row.id,'kind':row.kind,'payload':row.payload,'approval_required':body.approval_required,
              'approval_timeout_hours':body.approval_timeout_hours,'wait_until':body.wait_until.isoformat() if body.wait_until else None}
        enqueue(db,row,'start',item,suffix='start')
        await db.commit()
    except IntegrityError:
        # Two callers may pass the initial lookup together. The database unique
        # constraint chooses the winner; the loser receives normal idempotency.
        await db.rollback()
        existing=await db.scalar(select(AutomationWorkflow).where(
            AutomationWorkflow.workspace_id==str(body.workspace_id),
            AutomationWorkflow.request_key==body.request_key))
        if existing and existing.request_fingerprint==fingerprint:return existing
        raise HTTPException(409,'request_key đã dùng với nội dung khác')
    return row

async def owned(db,wid,who,write=False,lock=False):
    statement=select(AutomationWorkflow).where(AutomationWorkflow.id==str(wid))
    if lock:statement=statement.with_for_update()
    row=await db.scalar(statement)
    if not row:raise HTTPException(404,'Không tìm thấy workflow')
    await membership(db,row.workspace_id,who,write);return row

@router.get('/workflows',response_model=list[WorkflowOut])
async def listing(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await membership(db,str(workspace_id),who)
    return list(await db.scalars(select(AutomationWorkflow).where(AutomationWorkflow.workspace_id==str(workspace_id)).order_by(AutomationWorkflow.created_at.desc()).limit(100)))

@router.get('/workflows/{workflow_id}',response_model=WorkflowOut)
async def get(workflow_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):return await owned(db,workflow_id,who)

@router.post('/workflows/{workflow_id}/decision',response_model=WorkflowOut)
async def decision(workflow_id:UUID,body:DecisionIn,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await owned(db,workflow_id,who,True,True);member=await db.get(Member,(row.workspace_id,who.id))
    if member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được phê duyệt')
    if row.version!=body.version:raise HTTPException(409,'Workflow version đã thay đổi')
    if row.status!='waiting_approval' or row.approval_status!='pending':raise HTTPException(409,'Workflow không chờ phê duyệt')
    signal_payload={'actor_id':who.id,'version':row.version}
    row.approval_status='approved' if body.decision=='approve' else 'rejected';row.status='running' if body.decision=='approve' else 'cancelled';row.version+=1;row.updated_at=now()
    if row.status=='cancelled':row.completed_at=now()
    enqueue(db,row,'signal',signal_payload,signal_name=body.decision,suffix=f'{body.decision}:{row.version}')
    db.add(AutomationWorkflowAudit(workflow_id=row.id,workspace_id=row.workspace_id,actor_id=who.id,event=body.decision,workflow_version=row.version,data={}))
    await db.commit();return row

@router.post('/workflows/{workflow_id}/cancel',response_model=WorkflowOut)
async def cancel(workflow_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await owned(db,workflow_id,who,True,True)
    if row.status in ('completed','failed','cancelled'):return row
    payload={'actor_id':who.id};row.status='cancelled';row.completed_at=now();row.updated_at=now();row.version+=1
    enqueue(db,row,'signal',payload,signal_name='request_cancel',suffix=f'cancel:{row.version}')
    db.add(AutomationWorkflowAudit(workflow_id=row.id,workspace_id=row.workspace_id,actor_id=who.id,event='cancelled',workflow_version=row.version,data={}))
    await db.commit();return row
