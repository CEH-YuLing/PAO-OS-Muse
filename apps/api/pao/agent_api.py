from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .access import owned_run
from .auth import Principal, principal
from .db import database
from .models import AgentRun
from .schemas import ReadModel
from .agents import REGISTRY
from .config import settings
from .tool_registry import TOOLS
from .skill_artifacts import SkillReplay, read_artifact

router = APIRouter(prefix='/v1', tags=['agents'])


class AgentOut(BaseModel):
    key: str
    name: str
    prompt_version: str
    enabled: bool
    tools: list[str]


class AgentExecution(ReadModel):
    id: str
    agent_key: str
    step_index: int
    task: str
    output: str
    status: str
    model: str
    prompt_version: str
    usage: dict
    created_at: datetime
    finished_at: datetime | None


class ExecutionSnapshot(BaseModel):
    plan: dict
    agents: list[AgentExecution]


@router.get('/runs/{run_id}/skill-replay', response_model=SkillReplay)
async def skill_replay(run_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    run = await owned_run(db, run_id, who)
    artifact = (run.execution_plan or {}).get('skill_artifact')
    if run.status != 'completed' or not artifact:
        raise HTTPException(409, 'Chưa có artifact hoàn tất; không tự chạy lại job cũ')
    try:
        value = read_artifact(artifact, 'run', run.id, run.workspace_id)
        if value.response != run.response or value.result.model_dump() != run.execution_plan.get('skill_result'):
            raise ValueError('skill_archive_record_mismatch')
        return value
    except (ValueError, TypeError, KeyError):
        raise HTTPException(409, 'Artifact không hợp lệ; không đọc lại nguồn hoặc thực thi code cũ')


@router.get('/agents', response_model=list[AgentOut])
async def registry(who: Principal = Depends(principal)):
    return [AgentOut(key=a.key, name=a.name, prompt_version=a.prompt_version,
        enabled=a.key == 'chief_of_staff' or settings().agent_runtime_enabled,
        tools=[name for name,spec in TOOLS.items() if a.key in spec['agents']] if settings().tools_enabled else []) for a in REGISTRY.values()]


@router.get('/runs/{run_id}/execution', response_model=ExecutionSnapshot)
async def execution(run_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    run = await owned_run(db, run_id, who)
    agents = list(await db.scalars(select(AgentRun).where(AgentRun.run_id == str(run_id)).order_by(AgentRun.step_index)))
    return ExecutionSnapshot(plan=run.execution_plan, agents=[AgentExecution.model_validate(a) for a in agents])
