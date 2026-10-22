"""Closed tool allowlist. Provider URLs never come from model or user arguments."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .skills import PeriodInput, AdsInput, validate_input


class Arguments(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class KpiArgs(PeriodInput):
    platform: Literal['meta', 'google_ads'] | None = None
    account_id: str | None = None

    @model_validator(mode='after')
    def account_scope(self):
        if self.platform is not None or self.account_id is not None:
            AdsInput.model_validate(self.model_dump(exclude_none=True))
        return self


class SearchArgs(Arguments):
    query: str = Field(min_length=2, max_length=300)


class CalendarArgs(Arguments):
    title: str = Field(min_length=2, max_length=160)
    starts_at: datetime
    ends_at: datetime
    @model_validator(mode='after')
    def times(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None or self.ends_at <= self.starts_at:
            raise ValueError('Use timezone-aware start/end, end after start')
        return self


class EmailArgs(Arguments):
    to: str = Field(min_length=5,max_length=254,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    subject: str = Field(min_length=2,max_length=160)
    body: str = Field(min_length=2,max_length=2000)


class ToolRequest(Arguments):
    name: Literal['web.search','calendar.mock_create','email.mock_send','business.kpi.read','business.tasks.read','business.ads.intelligence.read','business.creative.read','business.attribution.read']
    agent: Literal['chief_of_staff','researcher','marketing','editor','performance_analyst'] = 'chief_of_staff'
    arguments: dict


TOOLS = {
    'business.attribution.read': {'schema':AdsInput,'agents':{'chief_of_staff','performance_analyst'},'approval':False,'mock':False},
    'business.ads.intelligence.read': {'schema':AdsInput,'agents':{'chief_of_staff','performance_analyst'},'approval':False,'mock':False},
    'business.creative.read': {'schema':AdsInput,'agents':{'chief_of_staff','performance_analyst','marketing'},'approval':False,'mock':False},
    'business.kpi.read': {'schema':KpiArgs,'agents':{'chief_of_staff','performance_analyst'},'approval':False,'mock':False},
    'business.tasks.read': {'schema':PeriodInput,'agents':{'chief_of_staff'},'approval':False,'mock':False},
    'web.search': {'schema':SearchArgs,'agents':{'chief_of_staff','researcher','marketing'},'approval':False,'mock':False},
    'calendar.mock_create': {'schema':CalendarArgs,'agents':{'chief_of_staff'},'approval':True,'mock':True},
    'email.mock_send': {'schema':EmailArgs,'agents':{'chief_of_staff'},'approval':True,'mock':True},
}


def validate_request(request):
    request = ToolRequest.model_validate(request)
    spec = TOOLS[request.name]
    if request.agent not in spec['agents']:
        raise PermissionError('agent_tool_denied')
    arguments = spec['schema'].model_validate(request.arguments).model_dump(mode='json', exclude_none=True)
    if request.name.startswith('business.'):
        skill_id = {'business.attribution.read': 'investigate-ads-drop', 'business.ads.intelligence.read': 'investigate-ads-drop',
                    'business.creative.read': 'creative-fatigue-review'}.get(request.name, 'daily-business-brief')
        if request.name == 'business.kpi.read' and arguments.get('platform') is not None:
            skill_id = 'investigate-ads-drop'
        validate_input(skill_id, request.agent, arguments, [request.name])
    return request.model_copy(update={'arguments':arguments})
