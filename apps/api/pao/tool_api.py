from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import Principal, principal, rate_limit
from .access import owned_run
from .db import database
from .models import ToolCall, ToolAudit
from .schemas import ReadModel
from .tool_registry import TOOLS, ToolRequest
from .tool_gateway import propose, decide
from .config import settings

router=APIRouter(prefix='/v1',tags=['tools'])


class ToolOut(ReadModel):
    id: str
    run_id: str
    name: str
    agent_key: str
    arguments: dict
    result: dict
    status: str
    version: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class AuditOut(ReadModel):
    id: str
    tool_call_id: str | None
    event: str
    data: dict
    created_at: datetime


class ToolSnapshot(BaseModel):
    calls: list[ToolOut]
    audit: list[AuditOut]


class ToolInfo(BaseModel):
    name: str
    agents: list[str]
    requires_approval: bool
    simulated: bool
    enabled: bool
    input_schema: dict


class ToolPropose(ToolRequest):
    request_key: str = Field(min_length=8,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')


class Decision(BaseModel):
    decision: Literal['approve','reject']
    version: int = Field(ge=1)


@router.get('/tools',response_model=list[ToolInfo])
async def registry(who: Principal=Depends(principal)):
    return [ToolInfo(name=name,agents=sorted(spec['agents']),requires_approval=spec['approval'],
        simulated=spec['mock'],enabled=settings().tools_enabled,input_schema=spec['schema'].model_json_schema()) for name,spec in TOOLS.items()]


@router.get('/runs/{run_id}/tools',response_model=ToolSnapshot)
async def snapshot(run_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await owned_run(db,run_id,who)
    calls=list(await db.scalars(select(ToolCall).where(ToolCall.run_id==str(run_id)).order_by(ToolCall.created_at,ToolCall.id)))
    logs=list(await db.scalars(select(ToolAudit).where(ToolAudit.run_id==str(run_id)).order_by(ToolAudit.created_at,ToolAudit.id).limit(200)))
    return ToolSnapshot(calls=[ToolOut.model_validate(c) for c in calls],audit=[AuditOut.model_validate(a) for a in logs])


@router.post('/runs/{run_id}/tools',response_model=ToolOut,status_code=201)
async def create(run_id: UUID,body: ToolPropose,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await owned_run(db,run_id,who,True)
    await rate_limit(request.app.state.redis,'tool-request',who.id,20,60)
    await db.rollback()
    return await propose(str(run_id),who.id,body.request_key,ToolRequest(name=body.name,agent=body.agent,arguments=body.arguments))


@router.post('/tools/calls/{call_id}/decision',response_model=ToolOut)
async def approval(call_id: UUID,body: Decision,who: Principal=Depends(principal)):
    return await decide(str(call_id),who.id,body.decision,body.version)
