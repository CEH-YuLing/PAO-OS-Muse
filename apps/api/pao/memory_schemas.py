from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from .schemas import ReadModel


class BrandCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=120)


class BrandOut(ReadModel):
    id: str
    workspace_id: str
    name: str


class Fact(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    key: str = Field(min_length=2, max_length=120)
    value: str = Field(min_length=5, max_length=500)
    importance: int = Field(default=3, ge=1, le=5)


class ExtractedFacts(BaseModel):
    model_config = ConfigDict(extra='forbid')
    facts: list[Fact] = Field(max_length=3)


class MemoryCreate(Fact):
    workspace_id: UUID
    brand_id: UUID | None = None


class MemoryPatch(Fact):
    version: int = Field(ge=1)
    status: Literal['active', 'pending'] = 'active'


class MemoryOut(ReadModel):
    id: str
    workspace_id: str
    brand_id: str | None
    key: str
    value: str
    importance: int
    status: str
    source_run_id: str | None
    embedding_model: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class MemorySearch(BaseModel):
    workspace_id: UUID
    brand_id: UUID | None = None
    query: str = Field(min_length=1, max_length=2000)


class MemoryHit(BaseModel):
    memory: MemoryOut
    score: float


class MemorySearchResult(BaseModel):
    items: list[MemoryHit]
    degraded: bool


class MemoryStatus(BaseModel):
    enabled: bool
    run_id: str | None = None
    job_status: str | None
    extracted: int = 0
    error_code: str | None = None


class MemoryToggle(BaseModel):
    memory_enabled: bool
