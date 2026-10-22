from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConnectionOut(BaseModel):
    configured: bool
    status: str
    remote_user_id: str | None = None
    scopes: list[str] = []
    expires_at: datetime | None = None


class OAuthStart(BaseModel):
    authorization_url: str


class SyncCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    workspace_id: UUID
    request_key: UUID
    grant_id: UUID | None = None
    brand_id: UUID | None = None
    kind: Literal['accounts','historical']
    account_id: str | None = Field(default=None, pattern=r'^act_[0-9]{1,32}$')
    since: date | None = None
    until: date | None = None
    warehouse: bool = False
    granularity: Literal['daily','hourly'] = 'daily'

    @model_validator(mode='after')
    def dates(self):
        if self.grant_id and (self.kind!='historical' or not self.warehouse):
            raise ValueError('Quyền SME chỉ đồng bộ historical warehouse đúng tài khoản')
        if self.brand_id and not self.grant_id:
            raise ValueError('Brand scope cần explicit grant')
        if (self.warehouse and self.kind!='historical') or (self.granularity=='hourly' and not self.warehouse):
            raise ValueError('Warehouse chỉ dùng historical; hourly cần warehouse')
        if self.kind=='historical':
            if not self.account_id or not self.since or not self.until or not 0 <= (self.until-self.since).days < 31 or self.until > date.today():
                raise ValueError('Lịch sử cần tài khoản và khoảng ngày tối đa 31 ngày, không ở tương lai')
        elif self.account_id or self.since or self.until:
            raise ValueError('Đồng bộ tài khoản không nhận bộ lọc lịch sử')
        return self


class SyncOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    account_id: str | None
    since: str | None
    until: str | None
    api_version: str
    warehouse: bool = False
    granularity: str = 'daily'
    status: str
    error_code: str | None
    row_count: int
    created_at: datetime
    updated_at: datetime


class SnapshotOut(BaseModel):
    job: SyncOut | None
    rows: list[dict]
    has_more: bool
