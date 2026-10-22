from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field

class KnowledgeSourceInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['file','note']
    origin_id:UUID

class KnowledgeSourcePatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    archived:bool

class KnowledgeSourceOut(BaseModel):
    id:str
    brain_id:str
    kind:Literal['file','note']
    origin_id:str
    title:str
    current_version:int
    revision:int
    archived_at:datetime|None
    stale:bool
    origin_trashed:bool
    version_id:str
    source_sha256:str
    parser_version:str
    job_id:str
    parse_status:Literal['queued','running','completed','failed']

class SourceVersionOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str
    source_id:str
    number:int
    origin_version:int
    source_sha256:str
    source_size:int
    title:str
    created_at:datetime

class IngestionOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str
    version_id:str
    parser_version:str
    status:Literal['queued','running','completed','failed']
    attempts:int
    error_code:str|None
    parsed_sha256:str|None
    line_count:int|None
    updated_at:datetime

class SourcePreview(BaseModel):
    source_id:str
    version_id:str
    version:int
    source_sha256:str
    parsed_sha256:str
    parser_version:str
    start_line:int
    end_line:int
    content:str
    truncated:bool
    format:Literal['plain_text']='plain_text'
