from datetime import date,datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
class ConnectionOut(BaseModel):configured:bool;status:str;scopes:list[str]=[]
class OAuthStart(BaseModel):authorization_url:str
class SyncCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id:UUID;request_key:UUID;kind:Literal['accounts','historical'];account_id:str|None=Field(None,pattern=r'^\d{10}$');since:date|None=None;until:date|None=None;granularity:Literal['daily','hourly']='daily'
    grant_id:UUID|None=None
    brand_id:UUID|None=None
    @model_validator(mode='after')
    def valid(self):
        if self.grant_id and self.kind!='historical':raise ValueError('Quyền SME chỉ historical đúng account')
        if self.brand_id and not self.grant_id:raise ValueError('Brand scope cần explicit grant')
        if self.kind=='historical':
            if not self.account_id or not self.since or not self.until or not 0<=(self.until-self.since).days<31 or self.until>date.today():raise ValueError('Lịch sử Google cần account và tối đa 31 ngày')
        elif self.account_id or self.since or self.until or self.granularity!='daily':raise ValueError('Đồng bộ accounts không nhận bộ lọc')
        return self
class SyncOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str;kind:str;account_id:str|None;since:str|None;until:str|None;api_version:str;granularity:str;status:str;error_code:str|None;row_count:int;created_at:datetime;updated_at:datetime
class AccountOut(BaseModel):
    id:str;name:str|None;currency:str;timezone:str;status:str|None;manager:bool=False
