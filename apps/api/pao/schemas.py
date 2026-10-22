from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class Token(BaseModel):
    access_token: str
    token_type: Literal['bearer'] = 'bearer'
    expires_in: int


class Membership(BaseModel):
    id: str
    name: str
    role: str


class Me(BaseModel):
    id: str
    email: str
    workspaces: list[Membership]


class SessionCreate(BaseModel):
    workspace_id: UUID
    brand_id: UUID | None = None
    memory_enabled: bool = True
    title: str = Field(default='Hội thoại mới', min_length=1, max_length=160)


class SessionOut(ReadModel):
    brand_id: str | None
    memory_enabled: bool
    id: str
    workspace_id: str
    title: str
    created_at: datetime


class MessageOut(ReadModel):
    id: str
    run_id: str
    role: str
    content: str
    status: str
    created_at: datetime


class RunCreate(BaseModel):
    session_id: UUID
    message: str = Field(min_length=1, max_length=1048576)
    request_key: str = Field(min_length=8, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')


RunStatus = Literal['queued', 'running', 'completed', 'failed', 'cancelled']


class RunOut(ReadModel):
    id: str
    session_id: str
    status: RunStatus
    response: str
    error_code: str | None
    cancel_requested: bool
    created_at: datetime


class SessionDetail(SessionOut):
    messages: list[MessageOut]
    active_run: RunOut | None


class EventOut(ReadModel):
    run_id: str
    seq: int
    type: Literal['run.queued', 'run.started', 'core.processing', 'core.reasoning',
                  'plan.started', 'plan.created', 'plan.failed',
                  'core.speaking', 'core.standby', 'memory.search.started', 'memory.search.completed', 'memory.search.failed', 'agent.started', 'response.completed',
                  'response.delta', 'agent.completed', 'agent.failed', 'agent.cancelled',
                  'run.completed', 'run.failed', 'run.cancelled']
    data: dict
    created_at: datetime
