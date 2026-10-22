import hashlib
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .access import membership
from .auth import Principal, principal
from .db import database
from .models import (Goal, Member, Project, Run, Task, TaskActivity, TaskAttempt,
                     TaskComment, TaskDependency, now)
from .skills import snapshot, validate_input, evaluate_result, SkillVersionMismatch
from .skill_artifacts import SkillReplay, build_artifact, read_artifact

router = APIRouter(prefix='/v1', tags=['tasks'])

ProjectStatus = Literal['active', 'on_hold', 'completed', 'archived']
GoalStatus = Literal['draft', 'active', 'completed', 'failed', 'cancelled']
TaskStatus = Literal['draft', 'ready', 'running', 'waiting_approval', 'blocked', 'completed', 'failed', 'cancelled']
TaskKind = Literal['human', 'ai', 'agent']
Priority = Literal['low', 'medium', 'high', 'critical']
AssigneeType = Literal['user', 'agent', 'unassigned']
TaskSource = Literal['user', 'pao', 'automation']
AttemptStatus = Literal['completed', 'failed', 'cancelled']
TASK_TRANSITIONS = {
    'draft': {'ready', 'cancelled'},
    'ready': {'running', 'blocked', 'completed', 'cancelled'},
    'running': {'waiting_approval', 'blocked', 'failed', 'cancelled'},
    'waiting_approval': {'completed', 'running', 'failed', 'cancelled'},
    'blocked': {'ready', 'failed', 'cancelled'},
    'failed': {'ready', 'running', 'cancelled'},
    'cancelled': {'ready', 'running'},
    'completed': set(),
}
GOAL_TRANSITIONS = {
    'draft': {'active', 'cancelled'},
    'active': {'completed', 'failed', 'cancelled'},
    'failed': {'active', 'cancelled'},
    'cancelled': {'active'},
    'completed': set(),
}


# Compatibility aliases; schema validators retain the same function identity.
from .modules.tasks.values import bounded_json, clean_criteria, attempt_fingerprint
from .modules.events.producer import completed as record_task_completed
from .modules.events.producer import requested as record_approval_requested


class GoalCreate(BaseModel):
    workspace_id: UUID
    project_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=8000)
    success_criteria: list[str] = Field(min_length=1, max_length=20)
    owner_id: UUID | None = None
    due_at: datetime | None = None

    _criteria = field_validator('success_criteria')(clean_criteria)


class GoalPatch(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    success_criteria: list[str] | None = Field(default=None, min_length=1, max_length=20)
    status: GoalStatus | None = None
    owner_id: UUID | None = None
    due_at: datetime | None = None

    _criteria = field_validator('success_criteria')(clean_criteria)


class GoalOut(BaseModel):
    model_config = {'from_attributes': True}
    id: str
    workspace_id: str
    project_id: str | None
    title: str
    description: str
    success_criteria: list
    status: str
    owner_id: str
    created_by: str
    due_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class ProjectCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=4000)
    status: ProjectStatus = 'active'
    owner_id: UUID | None = None
    due_at: datetime | None = None


class ProjectPatch(BaseModel):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    status: ProjectStatus | None = None
    owner_id: UUID | None = None
    due_at: datetime | None = None


class ProjectOut(BaseModel):
    model_config = {'from_attributes': True}
    id: str
    workspace_id: str
    name: str
    description: str
    status: str
    owner_id: str | None
    created_by: str
    due_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    workspace_id: UUID
    project_id: UUID | None = None
    goal_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=8000)
    status: TaskStatus = 'draft'
    kind: TaskKind = 'human'
    priority: Priority = 'medium'
    assignee_type: AssigneeType = 'unassigned'
    assignee_id: str | None = Field(default=None, max_length=80)
    progress: int = Field(default=0, ge=0, le=100)
    due_at: datetime | None = None
    source: TaskSource = 'user'
    run_id: UUID | None = None
    skill_id: str | None = Field(default=None, max_length=100, pattern=r'^[a-z0-9][a-z0-9_.-]*$')
    success_criteria: list[str] = Field(default_factory=list, max_length=20)
    input_references: list[dict] = Field(default_factory=list, max_length=50)
    budget: dict = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list, max_length=50)
    result_reference: dict = Field(default_factory=dict)
    required: bool = True
    dependencies: list[UUID] = Field(default_factory=list, max_length=20)
    files: list[dict] = Field(default_factory=list, max_length=20)

    @field_validator('dependencies')
    @classmethod
    def unique_dependencies(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('dependencies không được trùng')
        return value

    _criteria = field_validator('success_criteria')(clean_criteria)

    @field_validator('input_references', 'budget', 'evidence', 'result_reference', 'files')
    @classmethod
    def bounded_structures(cls, value):
        return bounded_json(value)


class TaskPatch(BaseModel):
    version: int = Field(ge=1)
    project_id: UUID | None = None
    goal_id: UUID | None = None
    parent_task_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=8000)
    status: TaskStatus | None = None
    kind: TaskKind | None = None
    priority: Priority | None = None
    assignee_type: AssigneeType | None = None
    assignee_id: str | None = Field(default=None, max_length=80)
    progress: int | None = Field(default=None, ge=0, le=100)
    due_at: datetime | None = None
    run_id: UUID | None = None
    skill_id: str | None = Field(default=None, max_length=100, pattern=r'^[a-z0-9][a-z0-9_.-]*$')
    success_criteria: list[str] | None = Field(default=None, max_length=20)
    input_references: list[dict] | None = Field(default=None, max_length=50)
    budget: dict | None = None
    evidence: list[dict] | None = Field(default=None, max_length=50)
    result_reference: dict | None = None
    required: bool | None = None
    dependencies: list[UUID] | None = Field(default=None, max_length=20)
    files: list[dict] | None = Field(default=None, max_length=20)

    @field_validator('dependencies')
    @classmethod
    def unique_dependencies(cls, value):
        if value is not None and len(set(value)) != len(value):
            raise ValueError('dependencies không được trùng')
        return value

    _criteria = field_validator('success_criteria')(clean_criteria)

    @field_validator('input_references', 'budget', 'evidence', 'result_reference', 'files')
    @classmethod
    def bounded_structures(cls, value):
        return bounded_json(value) if value is not None else value


class TaskOut(BaseModel):
    model_config = {'from_attributes': True}
    id: str
    workspace_id: str
    project_id: str | None
    goal_id: str | None
    parent_task_id: str | None
    title: str
    description: str
    status: str
    kind: str
    priority: str
    assignee_type: str
    assignee_id: str | None
    progress: int
    due_at: datetime | None
    source: str
    run_id: str | None
    skill_id: str | None
    success_criteria: list
    input_references: list
    budget: dict
    evidence: list
    result_reference: dict
    required: bool
    dependencies: list
    files: list
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class AttemptCreate(BaseModel):
    request_key: str = Field(min_length=8, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    input: dict = Field(default_factory=dict)
    run_id: UUID | None = None

    @field_validator('input')
    @classmethod
    def bounded_input(cls, value):
        return bounded_json(value)


class AttemptPatch(BaseModel):
    version: int = Field(ge=1)
    status: AttemptStatus
    result: dict = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list, max_length=50)
    error_code: str | None = Field(default=None, max_length=64, pattern=r'^[a-z0-9_.-]+$')

    @field_validator('result', 'evidence')
    @classmethod
    def bounded_output(cls, value):
        return bounded_json(value)


class AttemptOut(BaseModel):
    model_config = {'from_attributes': True}
    id: str
    workspace_id: str
    task_id: str
    run_id: str | None
    request_key: str
    attempt_no: int
    status: str
    input: dict
    skill_snapshot: dict | None
    skill_artifact: dict | None
    result: dict
    evidence: list
    error_code: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    started_at: datetime
    finished_at: datetime | None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CommentOut(BaseModel):
    model_config = {'from_attributes': True}
    id: str
    task_id: str
    workspace_id: str
    author_id: str
    body: str
    created_at: datetime


class ActivityOut(BaseModel):
    model_config = {'from_attributes': True}
    id: str
    task_id: str
    workspace_id: str
    actor_id: str | None
    event: str
    data: dict
    created_at: datetime


async def project_in_workspace(db: AsyncSession, project_id, workspace_id: str) -> Project:
    row = await db.scalar(select(Project).where(Project.id == str(project_id), Project.workspace_id == workspace_id))
    if not row:
        raise HTTPException(422, 'Project không thuộc workspace')
    return row


async def goal_in_workspace(db: AsyncSession, goal_id, workspace_id: str) -> Goal:
    row = await db.scalar(select(Goal).where(Goal.id == str(goal_id), Goal.workspace_id == workspace_id))
    if not row:
        raise HTTPException(422, 'Goal không thuộc workspace')
    return row


async def task_owned(db: AsyncSession, task_id, who: Principal, write=False) -> Task:
    row = await db.scalar(select(Task).where(Task.id == str(task_id)).with_for_update()) if write else await db.get(Task, str(task_id))
    if not row:
        raise HTTPException(404, 'Không tìm thấy task')
    await membership(db, row.workspace_id, who, write)
    await ensure_task_visible(db, row)
    return row


def task_deleted(task_id):
    # A scoped tombstone preserves comments, approval events and immutable history.
    return select(TaskActivity.id).where(
        TaskActivity.task_id == task_id, TaskActivity.event == 'task.deleted'
    ).exists()


async def ensure_task_visible(db, task):
    if await db.scalar(select(task_deleted(task.id))):
        raise HTTPException(404, 'Công việc đã được xóa khỏi bảng')


async def validate_owner(db: AsyncSession, owner_id, workspace_id: str):
    if owner_id is not None and not await db.get(Member, (workspace_id, str(owner_id))):
        raise HTTPException(422, 'Owner không thuộc workspace')


async def validate_run(db: AsyncSession, run_id, workspace_id: str):
    if run_id is None:
        return
    row = await db.get(Run, str(run_id))
    if not row or row.workspace_id != workspace_id:
        raise HTTPException(422, 'Run không thuộc workspace')


async def validate_dependencies(db: AsyncSession, dependencies, workspace_id: str, task_id: str | None = None):
    ids = [str(item) for item in dependencies or []]
    if task_id and task_id in ids:
        raise HTTPException(422, 'Task không thể phụ thuộc vào chính nó')
    if not ids:
        return ids
    rows = list(await db.scalars(select(Task).where(Task.id.in_(ids), Task.workspace_id == workspace_id).order_by(Task.id).with_for_update()))
    if len(rows) != len(ids):
        raise HTTPException(422, 'Dependency không thuộc workspace')
    for row in rows:
        await ensure_task_visible(db, row)
    if task_id:
        frontier = set(ids)
        seen = set(ids)
        while frontier:
            nested = set(await db.scalars(select(TaskDependency.depends_on_task_id).where(
                TaskDependency.task_id.in_(frontier), TaskDependency.workspace_id == workspace_id)))
            if task_id in nested:
                raise HTTPException(422, 'Dependency tạo thành vòng lặp')
            nested -= seen
            seen.update(nested)
            if len(seen) > 500:
                raise HTTPException(422, 'Cây dependency quá lớn')
            frontier = nested
    return ids


async def sync_dependencies(db: AsyncSession, task: Task, dependency_ids: list[str], actor_id: str):
    await db.execute(delete(TaskDependency).where(TaskDependency.task_id == task.id))
    for dependency_id in dependency_ids:
        db.add(TaskDependency(workspace_id=task.workspace_id, task_id=task.id,
                              depends_on_task_id=dependency_id, created_by=actor_id))
    task.dependencies = dependency_ids  # compatibility cache for existing UI/contracts


async def validate_parent(db: AsyncSession, parent_id, workspace_id: str, task_id: str | None = None):
    if parent_id is None:
        return None
    if task_id and str(parent_id) == task_id:
        raise HTTPException(422, 'Task không thể là parent của chính nó')
    parent = await db.scalar(select(Task).where(Task.id == str(parent_id), Task.workspace_id == workspace_id).with_for_update())
    if not parent:
        raise HTTPException(422, 'Parent task không thuộc workspace')
    await ensure_task_visible(db, parent)
    cursor = parent
    seen = {str(parent_id)}
    while cursor.parent_task_id:
        if cursor.parent_task_id == task_id:
            raise HTTPException(422, 'Parent task tạo thành vòng lặp')
        if cursor.parent_task_id in seen or len(seen) > 100:
            raise HTTPException(422, 'Cây parent task không hợp lệ')
        seen.add(cursor.parent_task_id)
        cursor = await db.get(Task, cursor.parent_task_id)
        if not cursor or cursor.workspace_id != workspace_id:
            raise HTTPException(422, 'Parent task không hợp lệ')
    return parent


async def ensure_dependencies_completed(db: AsyncSession, task: Task):
    dependencies = list(await db.scalars(select(Task).join(
        TaskDependency,
        (TaskDependency.depends_on_task_id == Task.id) & (TaskDependency.workspace_id == Task.workspace_id),
    ).where(TaskDependency.task_id == task.id)))
    incomplete = [row.id for row in dependencies if row.status != 'completed']
    if incomplete:
        raise HTTPException(409, {'code': 'dependencies_incomplete', 'task_ids': incomplete})
    if task.parent_task_id:
        parent = await db.get(Task, task.parent_task_id)
        if not parent or parent.workspace_id != task.workspace_id or parent.status != 'completed':
            raise HTTPException(409, {'code': 'parent_incomplete', 'task_id': task.parent_task_id})




@router.get('/goals', response_model=list[GoalOut])
async def list_goals(workspace_id: UUID, status: GoalStatus | None = None,
                     who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db, str(workspace_id), who)
    query = select(Goal).where(Goal.workspace_id == str(workspace_id))
    if status:
        query = query.where(Goal.status == status)
    return list(await db.scalars(query.order_by(Goal.updated_at.desc()).limit(200)))


@router.post('/goals', response_model=GoalOut, status_code=201)
async def create_goal(body: GoalCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    workspace_id = str(body.workspace_id)
    await membership(db, workspace_id, who, True)
    if body.project_id:
        await project_in_workspace(db, body.project_id, workspace_id)
    owner_id = str(body.owner_id) if body.owner_id else who.id
    await validate_owner(db, owner_id, workspace_id)
    criteria = [item.strip() for item in body.success_criteria if item.strip()]
    if not criteria:
        raise HTTPException(422, 'Goal cần ít nhất một tiêu chí thành công')
    row = Goal(workspace_id=workspace_id, project_id=str(body.project_id) if body.project_id else None,
               title=body.title.strip(), description=body.description.strip(), success_criteria=criteria,
               owner_id=owner_id, created_by=who.id, due_at=body.due_at)
    db.add(row)
    await db.commit()
    return row


@router.get('/goals/{goal_id}', response_model=GoalOut)
async def get_goal(goal_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await db.get(Goal, str(goal_id))
    if not row:
        raise HTTPException(404, 'Không tìm thấy goal')
    await membership(db, row.workspace_id, who)
    return row


@router.patch('/goals/{goal_id}', response_model=GoalOut)
async def update_goal(goal_id: UUID, body: GoalPatch, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await db.scalar(select(Goal).where(Goal.id == str(goal_id)).with_for_update())
    if not row:
        raise HTTPException(404, 'Không tìm thấy goal')
    await membership(db, row.workspace_id, who, True)
    if row.version != body.version:
        raise HTTPException(409, 'Goal version đã thay đổi')
    from .modules.goals.ledger import guard_goals
    await guard_goals(db,row.id)
    fields = body.model_fields_set - {'version'}
    if 'owner_id' in fields:
        if body.owner_id is None:
            raise HTTPException(422, 'Goal luôn cần owner')
        await validate_owner(db, body.owner_id, row.workspace_id)
    if 'success_criteria' in fields:
        body.success_criteria = [item.strip() for item in body.success_criteria or [] if item.strip()]
        if not body.success_criteria:
            raise HTTPException(422, 'Goal cần ít nhất một tiêu chí thành công')
    if 'status' in fields and body.status != row.status:
        if body.status not in GOAL_TRANSITIONS[row.status]:
            raise HTTPException(409, f'Không thể chuyển goal từ {row.status} sang {body.status}')
        if body.status == 'completed':
            tasks = list(await db.scalars(select(Task).where(Task.goal_id == row.id, Task.required.is_(True))))
            if not tasks or any(task.status != 'completed' or not task.evidence for task in tasks):
                raise HTTPException(409, 'Goal chỉ hoàn thành khi mọi task bắt buộc có evidence và đã completed')
            row.completed_at = now()
        elif row.status == 'completed':
            row.completed_at = None
    for field in fields:
        value = getattr(body, field)
        if field == 'owner_id':
            value = str(value)
        if field in ('title', 'description') and value is not None:
            value = value.strip()
        setattr(row, field, value)
    row.version += 1
    row.updated_at = now()
    await db.commit()
    return row


@router.get('/projects', response_model=list[ProjectOut])
async def list_projects(workspace_id: UUID, status: ProjectStatus | None = None,
                        who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db, str(workspace_id), who)
    query = select(Project).where(Project.workspace_id == str(workspace_id))
    if status:
        query = query.where(Project.status == status)
    return list(await db.scalars(query.order_by(Project.updated_at.desc()).limit(200)))


@router.post('/projects', response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    workspace_id = str(body.workspace_id)
    await membership(db, workspace_id, who, True)
    await validate_owner(db, body.owner_id, workspace_id)
    row = Project(workspace_id=workspace_id, name=body.name.strip(), description=body.description.strip(),
                  status=body.status, owner_id=str(body.owner_id) if body.owner_id else None,
                  created_by=who.id, due_at=body.due_at)
    db.add(row)
    await db.commit()
    return row


@router.patch('/projects/{project_id}', response_model=ProjectOut)
async def update_project(project_id: UUID, body: ProjectPatch, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await db.scalar(select(Project).where(Project.id == str(project_id)).with_for_update())
    if not row:
        raise HTTPException(404, 'Không tìm thấy project')
    await membership(db, row.workspace_id, who, True)
    if row.version != body.version:
        raise HTTPException(409, 'Project version đã thay đổi')
    fields = body.model_fields_set - {'version'}
    if 'owner_id' in fields:
        await validate_owner(db, body.owner_id, row.workspace_id)
    for field in fields:
        value = getattr(body, field)
        if field == 'owner_id':
            value = str(value) if value else None
        if field in ('name', 'description') and value is not None:
            value = value.strip()
        setattr(row, field, value)
    row.version += 1
    row.updated_at = now()
    await db.commit()
    return row


@router.get('/tasks', response_model=list[TaskOut])
async def list_tasks(workspace_id: UUID, project_id: UUID | None = None, goal_id: UUID | None = None,
                     status: TaskStatus | None = None,
                     kind: TaskKind | None = None, limit: int = Query(200, ge=1, le=500),
                     who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    workspace_id = str(workspace_id)
    await membership(db, workspace_id, who)
    query = select(Task).where(Task.workspace_id == workspace_id, ~task_deleted(Task.id))
    if project_id:
        query = query.where(Task.project_id == str(project_id))
    if goal_id:
        query = query.where(Task.goal_id == str(goal_id))
    if status:
        query = query.where(Task.status == status)
    if kind:
        query = query.where(Task.kind == kind)
    return list(await db.scalars(query.order_by(Task.updated_at.desc()).limit(limit)))


@router.post('/tasks', response_model=TaskOut, status_code=201)
async def create_task(body: TaskCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    workspace_id = str(body.workspace_id)
    await membership(db, workspace_id, who, True)
    project = await project_in_workspace(db, body.project_id, workspace_id) if body.project_id else None
    goal = await goal_in_workspace(db, body.goal_id, workspace_id) if body.goal_id else None
    from .modules.goals.ledger import guard_goals
    await guard_goals(db,body.goal_id)
    parent = await validate_parent(db, body.parent_task_id, workspace_id)
    if goal and project and goal.project_id and goal.project_id != project.id:
        raise HTTPException(422, 'Goal và task phải thuộc cùng project')
    if parent and parent.goal_id != (goal.id if goal else None):
        raise HTTPException(422, 'Parent task phải thuộc cùng goal')
    await validate_run(db, body.run_id, workspace_id)
    dependencies = await validate_dependencies(db, body.dependencies, workspace_id)
    if body.assignee_type == 'unassigned' and body.assignee_id:
        raise HTTPException(422, 'Task chưa phân công không được có assignee_id')
    criteria = [item.strip() for item in body.success_criteria if item.strip()]
    if body.status == 'completed' and (not criteria or not body.evidence):
        raise HTTPException(409, 'Task cần success criteria và evidence trước khi completed')
    row = Task(workspace_id=workspace_id, project_id=str(body.project_id) if body.project_id else None,
               goal_id=str(body.goal_id) if body.goal_id else None,
               parent_task_id=str(body.parent_task_id) if body.parent_task_id else None,
               title=body.title.strip(), description=body.description.strip(), status=body.status,
               kind=body.kind, priority=body.priority, assignee_type=body.assignee_type,
               assignee_id=body.assignee_id, progress=100 if body.status == 'done' else body.progress,
               due_at=body.due_at, source=body.source, run_id=str(body.run_id) if body.run_id else None,
               skill_id=body.skill_id, success_criteria=criteria, input_references=body.input_references,
               budget=body.budget, evidence=body.evidence, result_reference=body.result_reference,
               required=body.required, dependencies=dependencies, files=body.files, created_by=who.id,
               completed_at=now() if body.status == 'completed' else None)
    db.add(row)
    await db.flush()
    await sync_dependencies(db, row, dependencies, who.id)
    db.add(TaskActivity(task_id=row.id, workspace_id=workspace_id, actor_id=who.id,
                        event='task.created', data={'status': row.status, 'source': row.source}))
    if row.status == 'completed':
        await record_task_completed(db, row, who)
    elif row.status == 'waiting_approval':
        await record_approval_requested(db,row,who,'task')
    await db.commit()
    return row


@router.get('/tasks/{task_id}', response_model=TaskOut)
async def get_task(task_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    return await task_owned(db, task_id, who)


@router.patch('/tasks/{task_id}', response_model=TaskOut)
async def update_task(task_id: UUID, body: TaskPatch, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await db.scalar(select(Task).where(Task.id == str(task_id)).with_for_update())
    if not row:
        raise HTTPException(404, 'Không tìm thấy task')
    await membership(db, row.workspace_id, who, True)
    await ensure_task_visible(db, row)
    from .modules.studio.planning import guard_planned_task
    from .modules.goals.ledger import guard_goals
    if row.version != body.version:
        raise HTTPException(409, 'Task version đã thay đổi')
    fields = body.model_fields_set - {'version'}
    project = await project_in_workspace(db, body.project_id, row.workspace_id) if 'project_id' in fields and body.project_id else None
    goal = await goal_in_workspace(db, body.goal_id, row.workspace_id) if 'goal_id' in fields and body.goal_id else None
    if 'parent_task_id' in fields:
        await validate_parent(db, body.parent_task_id, row.workspace_id, row.id)
    next_project_id = str(body.project_id) if 'project_id' in fields and body.project_id else row.project_id
    next_goal = goal if 'goal_id' in fields else (await db.get(Goal, row.goal_id) if row.goal_id else None)
    await guard_goals(db,row.goal_id,next_goal.id if next_goal else None)
    await guard_planned_task(db,row)
    if next_goal and next_goal.project_id and next_project_id and next_goal.project_id != next_project_id:
        raise HTTPException(422, 'Goal và task phải thuộc cùng project')
    if 'run_id' in fields:
        await validate_run(db, body.run_id, row.workspace_id)
    dependency_ids = row.dependencies
    if 'dependencies' in fields:
        dependency_ids = await validate_dependencies(db, body.dependencies, row.workspace_id, row.id)
        body.dependencies = dependency_ids
    next_assignee_type = body.assignee_type if 'assignee_type' in fields else row.assignee_type
    next_assignee_id = body.assignee_id if 'assignee_id' in fields else row.assignee_id
    if next_assignee_type == 'unassigned' and next_assignee_id:
        raise HTTPException(422, 'Task chưa phân công không được có assignee_id')
    if 'status' in fields and body.status != row.status:
        if body.status not in TASK_TRANSITIONS[row.status]:
            raise HTTPException(409, f'Không thể chuyển task từ {row.status} sang {body.status}')
        if row.kind != 'human' and body.status in ('running', 'waiting_approval'):
            raise HTTPException(409, 'Task AI/agent phải chuyển trạng thái qua Task Attempt')
        if row.kind != 'human' and body.status == 'completed' and row.status != 'waiting_approval':
            raise HTTPException(409, 'Task AI/agent chỉ hoàn thành sau attempt và approval')
        if body.status in ('running', 'completed'):
            dependencies = list(await db.scalars(select(Task).where(
                Task.id.in_(dependency_ids), Task.workspace_id == row.workspace_id))) if dependency_ids else []
            incomplete = [item.id for item in dependencies if item.status != 'completed']
            if incomplete:
                raise HTTPException(409, {'code': 'dependencies_incomplete', 'task_ids': incomplete})
        if body.status == 'completed':
            evidence = body.evidence if 'evidence' in fields else row.evidence
            criteria = body.success_criteria if 'success_criteria' in fields else row.success_criteria
            if not evidence or not criteria:
                raise HTTPException(409, 'Task cần success criteria và evidence trước khi completed')
    changes = {}
    for field in fields:
        value = getattr(body, field)
        if field in ('project_id', 'goal_id', 'parent_task_id', 'run_id'):
            value = str(value) if value else None
        if field in ('title', 'description') and value is not None:
            value = value.strip()
        old = getattr(row, field)
        if old != value:
            changes[field] = {'from': old, 'to': value}
            setattr(row, field, value)
    if 'dependencies' in fields:
        await sync_dependencies(db, row, dependency_ids, who.id)
    if 'status' in changes:
        if row.status == 'completed':
            row.progress, row.completed_at = 100, now()
        else:
            row.completed_at = None
        if row.status == 'cancelled':
            attempts = list(await db.scalars(select(TaskAttempt).where(
                TaskAttempt.task_id == row.id, TaskAttempt.status == 'running').with_for_update()))
            for attempt in attempts:
                attempt.status = 'cancelled'
                attempt.error_code = 'task_cancelled'
                attempt.finished_at = now()
                attempt.updated_at = now()
    row.version += 1
    row.updated_at = now()
    db.add(TaskActivity(task_id=row.id, workspace_id=row.workspace_id, actor_id=who.id,
                        event='task.updated', data={'changes': changes}))
    if changes.get('status', {}).get('to') == 'completed':
        await record_task_completed(db, row, who)
    elif changes.get('status', {}).get('to') == 'waiting_approval':
        await record_approval_requested(db,row,who,'task')
    await db.commit()
    return row


@router.delete('/tasks/{task_id}', response_model=TaskOut)
async def delete_task(task_id: UUID, version: int = Query(ge=1),
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await db.scalar(select(Task).where(Task.id == str(task_id)).with_for_update())
    if not row:
        raise HTTPException(404, 'Không tìm thấy công việc')
    member = await membership(db, row.workspace_id, who, True)
    if member.role != 'owner' and row.created_by != who.id:
        raise HTTPException(403, 'Chỉ chủ doanh nghiệp hoặc người tạo được xóa công việc')
    # Retrying the exact request after a lost response is harmless and auditable.
    tombstone = await db.scalar(select(TaskActivity).where(
        TaskActivity.task_id == row.id, TaskActivity.event == 'task.deleted'))
    if tombstone:
        if tombstone.actor_id == who.id and tombstone.data.get('version') == version:
            return row
        raise HTTPException(404, 'Công việc đã được xóa khỏi bảng')
    if row.version != version:
        raise HTTPException(409, 'Công việc đã thay đổi. Hãy tải lại và kiểm tra trước khi xóa.')
    from .modules.studio.planning import guard_planned_task
    await guard_planned_task(db, row)
    if row.status in ('running', 'completed') or row.run_id or row.goal_id or row.parent_task_id:
        raise HTTPException(409, 'Không thể xóa việc đang chạy, đã hoàn tất hoặc thuộc mục tiêu/quy trình. Hãy xử lý trong quy trình gốc.')
    if row.source != 'user' or row.kind != 'human' or row.evidence or row.result_reference:
        raise HTTPException(409, 'Chỉ xóa công việc tạo thủ công chưa có kết quả. Công việc AI cần xử lý trong quy trình gốc.')
    linked = await db.scalar(select(Task.id).where(Task.parent_task_id == row.id).limit(1))
    dependency = await db.scalar(select(TaskDependency.id).where(
        (TaskDependency.task_id == row.id) | (TaskDependency.depends_on_task_id == row.id)).limit(1))
    attempted = await db.scalar(select(TaskAttempt.id).where(TaskAttempt.task_id == row.id).limit(1))
    if linked or dependency or attempted or row.dependencies:
        raise HTTPException(409, 'Công việc có công việc con, phụ thuộc hoặc lịch sử thực thi; không thể xóa khỏi bảng.')
    previous = row.status
    row.status = 'cancelled'
    row.version += 1
    row.updated_at = now()
    db.add(TaskActivity(task_id=row.id, workspace_id=row.workspace_id, actor_id=who.id,
                        event='task.deleted', data={'version': version, 'previous_status': previous}))
    await db.commit()
    return row


@router.get('/tasks/{task_id}/attempts', response_model=list[AttemptOut])
async def list_attempts(task_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await task_owned(db, task_id, who)
    return list(await db.scalars(select(TaskAttempt).where(TaskAttempt.task_id == row.id)
                                 .order_by(TaskAttempt.attempt_no)))


@router.post('/tasks/{task_id}/attempts', response_model=AttemptOut, status_code=201)
async def create_attempt(task_id: UUID, body: AttemptCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    task = await db.scalar(select(Task).where(Task.id == str(task_id)).with_for_update())
    if not task:
        raise HTTPException(404, 'Không tìm thấy task')
    await membership(db, task.workspace_id, who, True)
    await ensure_task_visible(db, task)
    from .modules.studio.planning import guard_planned_task
    await guard_planned_task(db,task)
    fingerprint = attempt_fingerprint(body.input, body.run_id)
    existing = await db.scalar(select(TaskAttempt).where(
        TaskAttempt.task_id == task.id, TaskAttempt.request_key == body.request_key))
    if existing:
        if existing.input_fingerprint != fingerprint:
            raise HTTPException(409, 'request_key đã dùng với input khác')
        return existing
    if task.status not in ('ready', 'failed', 'cancelled'):
        raise HTTPException(409, f'Task ở trạng thái {task.status} chưa thể tạo attempt')
    if not task.success_criteria:
        raise HTTPException(409, 'Task cần success criteria trước khi thực thi')
    await ensure_dependencies_completed(db, task)
    await validate_run(db, body.run_id, task.workspace_id)
    pinned = None
    if task.skill_id:
        try:
            agent = task.assignee_id if task.assignee_type == 'agent' else 'chief_of_staff'
            validate_input(task.skill_id, agent, body.input)
            pinned = snapshot(task.skill_id)
        except KeyError:
            raise HTTPException(422, 'Skill chưa được đăng ký và duyệt')
        except PermissionError:
            raise HTTPException(403, 'Agent không được skill cho phép')
        except ValidationError:
            raise HTTPException(422, 'Input không đúng contract của skill')
    attempt_no = (await db.scalar(select(func.max(TaskAttempt.attempt_no)).where(
        TaskAttempt.task_id == task.id)) or 0) + 1
    attempt = TaskAttempt(
        workspace_id=task.workspace_id, task_id=task.id,
        run_id=str(body.run_id) if body.run_id else None,
        request_key=body.request_key, input_fingerprint=fingerprint,
        attempt_no=attempt_no, status='running', input=body.input,
        skill_snapshot=pinned,
    )
    db.add(attempt)
    await db.flush()
    task.status = 'running'
    task.run_id = attempt.run_id
    task.completed_at = None
    task.version += 1
    task.updated_at = now()
    db.add(TaskActivity(task_id=task.id, workspace_id=task.workspace_id, actor_id=who.id,
                        event='attempt.started', data={'attempt_id': attempt.id, 'attempt_no': attempt_no}))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.scalar(select(TaskAttempt).where(
            TaskAttempt.task_id == str(task_id), TaskAttempt.request_key == body.request_key))
        if existing and existing.input_fingerprint == fingerprint:
            return existing
        raise HTTPException(409, 'Attempt trùng hoặc task đã thay đổi')
    return attempt


@router.patch('/tasks/{task_id}/attempts/{attempt_id}', response_model=AttemptOut)
async def update_attempt(task_id: UUID, attempt_id: UUID, body: AttemptPatch,
                         who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    attempt = await db.scalar(select(TaskAttempt).where(
        TaskAttempt.id == str(attempt_id), TaskAttempt.task_id == str(task_id)).with_for_update())
    if not attempt:
        raise HTTPException(404, 'Không tìm thấy attempt')
    await membership(db, attempt.workspace_id, who, True)
    if attempt.version != body.version:
        raise HTTPException(409, 'Attempt version đã thay đổi')
    if attempt.status != 'running':
        raise HTTPException(409, 'Attempt đã kết thúc')
    task = await db.scalar(select(Task).where(Task.id == attempt.task_id).with_for_update())
    from .modules.studio.planning import guard_planned_task
    await guard_planned_task(db,task)
    if task.status == 'cancelled':
        raise HTTPException(409, 'Task đã bị hủy; không nhận kết quả muộn')
    if body.status == 'completed' and (not body.result or not body.evidence):
        raise HTTPException(409, 'Attempt hoàn tất cần result và evidence')
    if body.status == 'failed' and not body.error_code:
        raise HTTPException(422, 'Attempt thất bại cần error_code')
    if body.status == 'completed' and attempt.skill_snapshot:
        try:
            evaluated = evaluate_result(attempt.skill_snapshot, body.result)
        except SkillVersionMismatch:
            raise HTTPException(409, 'skill_version_incompatible: không nhận kết quả bằng executable khác phiên bản')
        except ValueError:
            raise HTTPException(422, 'Result không đúng evaluator đã pin của skill')
        if evaluated['status'] == 'insufficient_data':
            raise HTTPException(409, 'Thiếu dữ liệu: ghi attempt failed với error_code insufficient_data')
        try:
            attempt.skill_artifact = build_artifact('attempt', attempt.id, attempt.workspace_id,
                attempt.skill_snapshot, attempt.input, evaluated, evidence=body.evidence)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, 'Không thể lưu artifact theo contract đã pin')
    attempt.status = body.status
    attempt.result = evaluated if body.status == 'completed' and attempt.skill_snapshot else body.result
    attempt.evidence = body.evidence
    attempt.error_code = body.error_code
    attempt.version += 1
    attempt.updated_at = now()
    attempt.finished_at = now()
    if body.status == 'completed':
        task.status = 'waiting_approval'
        task.evidence = body.evidence
        task.result_reference = {'type': 'task_attempt', 'attempt_id': attempt.id}
        task.progress = max(task.progress, 90)
    elif body.status == 'failed':
        task.status = 'failed'
    else:
        task.status = 'cancelled'
    task.version += 1
    task.updated_at = now()
    db.add(TaskActivity(task_id=task.id, workspace_id=task.workspace_id, actor_id=who.id,
                        event=f'attempt.{body.status}', data={'attempt_id': attempt.id,
                                                            'attempt_no': attempt.attempt_no,
                                                            'error_code': body.error_code}))
    if task.status == 'waiting_approval':
        await db.flush()
        await record_approval_requested(db,task,who,'task')
    await db.commit()
    return attempt


@router.get('/tasks/{task_id}/attempts/{attempt_id}/skill-replay', response_model=SkillReplay)
async def attempt_skill_replay(task_id: UUID, attempt_id: UUID, who: Principal = Depends(principal),
                               db: AsyncSession = Depends(database)):
    task = await task_owned(db, task_id, who)
    attempt = await db.scalar(select(TaskAttempt).where(TaskAttempt.id == str(attempt_id),
                                                       TaskAttempt.task_id == task.id))
    if not attempt:
        raise HTTPException(404, 'Không tìm thấy attempt')
    if attempt.status != 'completed' or not attempt.skill_artifact:
        raise HTTPException(409, 'Chưa có artifact hoàn tất; không tự chạy lại attempt')
    try:
        value = read_artifact(attempt.skill_artifact, 'attempt', attempt.id, task.workspace_id)
        if value.result.model_dump() != {**attempt.result, 'missing_data': attempt.result.get('missing_data', [])} or value.evidence != attempt.evidence:
            raise ValueError('skill_archive_record_mismatch')
        return value
    except (ValueError, TypeError, KeyError):
        raise HTTPException(409, 'Artifact không hợp lệ; không chạy evaluator hoặc tool mới')


@router.get('/tasks/{task_id}/comments', response_model=list[CommentOut])
async def list_comments(task_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await task_owned(db, task_id, who)
    return list(await db.scalars(select(TaskComment).where(TaskComment.task_id == row.id).order_by(TaskComment.created_at)))


@router.post('/tasks/{task_id}/comments', response_model=CommentOut, status_code=201)
async def create_comment(task_id: UUID, body: CommentCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await task_owned(db, task_id, who, True)
    comment = TaskComment(task_id=row.id, workspace_id=row.workspace_id, author_id=who.id, body=body.body.strip())
    db.add(comment)
    await db.flush()
    db.add(TaskActivity(task_id=row.id, workspace_id=row.workspace_id, actor_id=who.id,
                        event='comment.created', data={'comment_id': comment.id}))
    await db.commit()
    return comment


@router.get('/tasks/{task_id}/activity', response_model=list[ActivityOut])
async def list_activity(task_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row = await task_owned(db, task_id, who)
    return list(await db.scalars(select(TaskActivity).where(TaskActivity.task_id == row.id)
                                 .order_by(TaskActivity.created_at.desc()).limit(200)))
