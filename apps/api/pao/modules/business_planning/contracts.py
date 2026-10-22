"""Data-only contracts: unknown is null, never fabricated KPI or balance zero."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Closed(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)

    @model_validator(mode='before')
    @classmethod
    def safe_text(cls,value):
        def walk(item,depth=0):
            if depth>12:raise ValueError('Nested input exceeds limit')
            if isinstance(item,str):
                item.encode('utf-8')
                if any(ord(char)<32 and char not in '\n\r\t' for char in item):raise ValueError('Invalid control character')
            elif isinstance(item,dict):
                for key,child in item.items():walk(key,depth+1);walk(child,depth+1)
            elif isinstance(item,list):
                for child in item:walk(child,depth+1)
        try:walk(value)
        except UnicodeError:raise ValueError('Invalid Unicode') from None
        return value


class KPI(Closed):
    name: str=Field(min_length=1,max_length=100)
    target: Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=4)
    unit: str=Field(min_length=1,max_length=32)

    @field_validator('target',mode='before')
    @classmethod
    def exact(cls,value):
        if isinstance(value,(float,bool)):raise ValueError('Use decimal strings')
        return value


class ProfileContent(Closed):
    description: str=Field(default='',max_length=4000)
    products: list[str]=Field(default_factory=list,max_length=30)
    audience: str=Field(default='',max_length=2000)
    brand_voice: str=Field(default='',max_length=2000)
    objectives: list[str]=Field(default_factory=list,max_length=20)
    kpis: list[KPI]=Field(default_factory=list,max_length=20)
    resources: str=Field(default='',max_length=2000)
    monthly_budget: Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=2)
    currency: str=Field(pattern=r'^[A-Z]{3}$')
    timezone: str=Field(min_length=1,max_length=64)

    @field_validator('monthly_budget',mode='before')
    @classmethod
    def exact(cls,value):
        if isinstance(value,(float,bool)):raise ValueError('Use decimal strings')
        return value

    @field_validator('products','objectives')
    @classmethod
    def short_items(cls,values):
        if any(not item.strip() or len(item)>500 for item in values):raise ValueError('Invalid item')
        return [item.strip() for item in values]

    @field_validator('timezone')
    @classmethod
    def zone(cls,value):
        try:ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):raise ValueError('Invalid timezone') from None
        return value


class ProfileSave(Closed):
    expected_revision: int=Field(ge=0,strict=True)
    request_key: UUID
    content: ProfileContent


class Deliverable(Closed):
    key: str=Field(pattern=r'^[a-z][a-z0-9_-]{0,39}$')
    title: str=Field(min_length=1,max_length=200)
    specialist: Literal['content','creative','ads','analyst']
    due_date: date
    brief: str=Field(min_length=1,max_length=4000)
    acceptance: list[str]=Field(min_length=1,max_length=10)
    depends_on: list[str]=Field(default_factory=list,max_length=20)

    @field_validator('acceptance')
    @classmethod
    def criteria(cls,items):
        if any(not item.strip() or len(item)>500 for item in items):raise ValueError('Invalid criterion')
        return [item.strip() for item in items]


class PlanContent(Closed):
    title: str=Field(min_length=1,max_length=200)
    month: date
    campaign_brief: str=Field(min_length=1,max_length=8000)
    deliverables: list[Deliverable]=Field(min_length=1,max_length=50)

    @model_validator(mode='after')
    def bounded_dag(self):
        if self.month.day!=1:raise ValueError('Use first day of month')
        rows={item.key:item for item in self.deliverables}
        if len(rows)!=len(self.deliverables):raise ValueError('Duplicate key')
        completed=set()
        for item in self.deliverables:
            if (item.due_date.year,item.due_date.month)!=(self.month.year,self.month.month):raise ValueError('Due date outside month')
            if len(set(item.depends_on))!=len(item.depends_on) or any(key not in rows for key in item.depends_on):raise ValueError('Invalid dependency')
        for _ in rows:
            completed.update(key for key,item in rows.items() if set(item.depends_on)<=completed)
        if len(completed)!=len(rows):raise ValueError('Dependency cycle')
        for item in rows.values():
            if any(rows[key].due_date>item.due_date for key in item.depends_on):raise ValueError('Dependency due after consumer')
        return self


class PlanSave(Closed):
    expected_revision: int=Field(ge=0,strict=True)
    request_key: UUID
    profile_id: UUID
    profile_revision: int=Field(ge=1,strict=True)
    content: PlanContent


def digest(content):
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def missing(content):
    fields=('description','products','audience','brand_voice','objectives','kpis','resources')
    result=[key for key in fields if not content.get(key)]
    if content.get('monthly_budget') is None:result.append('monthly_budget')
    result.extend('kpis.'+str(index)+'.target' for index,kpi in enumerate(content.get('kpis',[])) if kpi.get('target') is None)
    return result
