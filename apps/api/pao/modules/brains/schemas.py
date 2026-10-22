from datetime import datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class BrainCreate(Input):
    workspace_id: UUID
    brand_id: UUID | None = None
    name: str = Field(min_length=1,max_length=120)


class DefaultBrain(Input):
    workspace_id: UUID
    brand_id: UUID | None = None


class BrainPatch(Input):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None,min_length=1,max_length=120)
    archived: bool | None = None


class BrainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    owner_id: str
    brand_id: str | None
    name: str
    legacy_default: bool
    revision: int
    archived_at: datetime | None
    created_at: datetime
    effective_role: Literal['owner','reader','editor'] | None = None


class BrainGrant(Input):
    role: Literal['reader','editor']
    revision: int = Field(ge=1)


class SessionBrain(Input):
    brain_id: UUID
    version: int = Field(ge=1)
