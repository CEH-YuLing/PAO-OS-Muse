"""Catalog, preflight and explicitly requested SELECT-only daily preview."""
import asyncio
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .access import membership
from .auth import Principal, principal
from .db import database, Session
from .skills import REGISTRY, SkillManifest, SkillResult, snapshot, validate_input
from .business_tools import daily_brief_preview, read_intelligence, read_creative, read_attribution

router = APIRouter(prefix='/v1/skills', tags=['skills'])


class SkillPreflight(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_id: UUID
    agent: str = Field(min_length=1, max_length=80)
    input: dict
    requested_tools: list[str] = Field(default_factory=list, max_length=10)


class ExecutionBindingView(BaseModel):
    model_config = ConfigDict(extra='forbid')
    policy: Literal['exact-backend-source-v1']
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class SkillView(SkillManifest):
    input_schema: dict
    output_schema: dict
    hash: str
    execution_binding: ExecutionBindingView


class PreflightOut(BaseModel):
    valid: Literal[True]
    skill: SkillView
    input: dict
    execution_available: Literal[False]


class BriefPreviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_id: UUID
    input: dict


class ToolReadOut(BaseModel):
    tool: Literal['business.kpi.read', 'business.tasks.read', 'business.ads.intelligence.read', 'business.creative.read', 'business.attribution.read']
    status: Literal['completed', 'insufficient_data']
    data: dict
    source_references: list[str]
    missing_data: list[str]


class BriefPreviewOut(BaseModel):
    skill: SkillView
    input: dict
    read_only: Literal[True]
    result: SkillResult
    tools: list[ToolReadOut]
    retrieved_at: str


@router.post('/investigate-ads-drop/attribution-preview', response_model=BriefPreviewOut)
async def attribution_preview(body: BriefPreviewInput, who: Principal = Depends(principal),
                              db: AsyncSession = Depends(database)):
    await membership(db, str(body.workspace_id), who)
    try:
        args = validate_input('investigate-ads-drop', 'chief_of_staff', body.input, ['business.attribution.read'])
        pinned = snapshot('investigate-ads-drop')
        async with asyncio.timeout(10):
            async with Session.begin() as read_db:
                await read_db.execute(text('SET TRANSACTION READ ONLY'))
                await read_db.execute(text("SET LOCAL statement_timeout = '8000'"))
                tool = await read_attribution(read_db, who, str(body.workspace_id), args)
        from .skills import evaluate_result
        from .models import now
        result = {'status': 'insufficient_data', 'summary':
                  'Chỉ đọc snapshot attribution đã lưu; không tự phân tích. Doanh thu Ads, doanh thu orders được phân bổ và tổng doanh thu doanh nghiệp không đồng nhất.',
                  'source_references': tool['source_references'], 'missing_data': tool['missing_data']}
        return {'skill': pinned, 'input': args, 'read_only': True, 'result': evaluate_result(pinned, result),
                'tools': [tool], 'retrieved_at': now().isoformat()}
    except ValidationError:
        raise HTTPException(422, 'Input không đúng contract của skill')
    except TimeoutError:
        raise HTTPException(504, 'Quá thời gian đọc attribution snapshot')


@router.post('/{skill_id}/analysis-preview', response_model=BriefPreviewOut)
async def analysis_preview(skill_id: str, body: BriefPreviewInput, who: Principal = Depends(principal),
                           db: AsyncSession = Depends(database)):
    await membership(db, str(body.workspace_id), who)
    handlers = {'investigate-ads-drop': read_intelligence, 'creative-fatigue-review': read_creative}
    if skill_id not in handlers:
        raise HTTPException(404, 'Chưa có preview cho skill này')
    try:
        args = validate_input(skill_id, 'chief_of_staff', body.input)
        pinned = snapshot(skill_id)
        async with asyncio.timeout(10):
            async with Session.begin() as read_db:
                await read_db.execute(text('SET TRANSACTION READ ONLY'))
                await read_db.execute(text("SET LOCAL statement_timeout = '8000'"))
                tool = await handlers[skill_id](read_db, who, str(body.workspace_id), args)
        result = {'status': 'insufficient_data',
                  'summary': 'Bản xem trước snapshot phân tích đã lưu. Tín hiệu không chứng minh nguyên nhân; chưa thực hiện hành động.',
                  'source_references': tool['source_references'],
                  'missing_data': tool['missing_data'] + ['causal_validation: chưa đối chiếu dữ liệu/baseline để kết luận nguyên nhân']}
        from .models import now
        from .skills import evaluate_result
        return {'skill': pinned, 'input': args, 'read_only': True, 'result': evaluate_result(pinned, result),
                'tools': [tool], 'retrieved_at': now().isoformat()}
    except ValidationError:
        raise HTTPException(422, 'Input không đúng contract của skill')
    except TimeoutError:
        raise HTTPException(504, 'Quá thời gian đọc snapshot')


@router.post('/daily-business-brief/preview', response_model=BriefPreviewOut)
async def preview(body: BriefPreviewInput, who: Principal = Depends(principal),
                  db: AsyncSession = Depends(database)):
    await membership(db, str(body.workspace_id), who)
    try:
        async with asyncio.timeout(10):
            # Separate transaction: principal already queried its own session.
            # PostgreSQL enforces no writes, independently of tool code.
            async with Session.begin() as read_db:
                await read_db.execute(text('SET TRANSACTION READ ONLY'))
                await read_db.execute(text("SET LOCAL statement_timeout = '8000'"))
                return await daily_brief_preview(read_db, who, str(body.workspace_id), body.input)
    except ValidationError:
        raise HTTPException(422, 'Input không đúng contract của skill')
    except TimeoutError:
        raise HTTPException(504, 'Quá thời gian đọc dữ liệu; chưa có hành động được thực hiện')


@router.get('', response_model=list[SkillView])
async def catalog(workspace_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db, str(workspace_id), who)
    return [snapshot(key) for key in REGISTRY]


@router.post('/{skill_id}/validate', response_model=PreflightOut)
async def preflight(skill_id: str, body: SkillPreflight, who: Principal = Depends(principal),
                    db: AsyncSession = Depends(database)):
    await membership(db, str(body.workspace_id), who)
    try:
        validated = validate_input(skill_id, body.agent, body.input, body.requested_tools)
        pinned = snapshot(skill_id)
    except KeyError:
        raise HTTPException(404, 'Không tìm thấy skill đã duyệt')
    except PermissionError:
        raise HTTPException(403, 'Agent hoặc tool không được skill cho phép')
    except ValidationError:
        raise HTTPException(422, 'Input không đúng contract của skill')
    return {'valid': True, 'skill': pinned, 'input': validated, 'execution_available': False}
