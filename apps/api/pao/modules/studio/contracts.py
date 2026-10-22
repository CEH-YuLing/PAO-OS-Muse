"""Bounded data-only contracts: no executable code, remote references or secrets."""
import json,re,hashlib,math
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field
Kind=Literal['agents','skills','workflows']
RESERVED={'help','status','brain','tasks','memory','model','usage','compact','export','stop','goal','skill','daily-business-brief','investigate-ads-drop','creative-fatigue-review'}
READ_TOOLS={'business.kpi.read','business.tasks.read','business.attribution.read','business.ads.intelligence.read','business.creative.read'}
SCHEMA_KEYS={'type','properties','required','additionalProperties','maxLength','minLength','maximum','minimum','items','maxItems','minItems','enum','description'}
BAD_TEXT=re.compile(r'(?i)(sk-[a-z0-9_-]{12,}|Bearer\s+[a-z0-9_.-]{12,}|-----BEGIN .*PRIVATE KEY|ignore\s+(all|previous)\s+(rules|instructions)|override\s+permissions|disable\s+approval|<\/?system>|import os|eval\(|exec\(|subprocess\.|os\.system|powershell -|cmd /c)')
SECRET_KEYS={'api_key','password','token','secret','authorization','code','shell','command','endpoint','env'}
class Closed(BaseModel):model_config=ConfigDict(extra='forbid',strict=True)
class ModelPreference(Closed):
    provider:Literal['ollama','openai','openrouter','anthropic','gemini','codex_cli','muse']
    model:str=Field(min_length=1,max_length=120,pattern=r'^[^\s\x00-\x1f\x7f]+$')
    installation_resource_id:str|None=Field(default=None,pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    reasoning_effort:str|None=Field(default=None,pattern=r'^[a-z][a-z0-9_-]{0,23}$')
class Agent(Closed):
    instruction:str=Field(min_length=5,max_length=6000)
    model_preference:ModelPreference|None=None
    brain_id:str|None=None
class Skill(Closed):
    mode:Literal['llm_text']='llm_text'
    instruction:str=Field(min_length=5,max_length=6000)
    agent_version_id:str
    input_schema:dict
    output_schema:dict
    allowed_tools:list[str]=Field(default_factory=list,max_length=5)
    timeout_seconds:int=Field(default=45,ge=1,le=120)
    token_budget:int=Field(default=4096,ge=128,le=65536)
    output_tokens:int=Field(default=256,ge=16,le=512)
    generation_cap:Literal[1]=1
    exit_criteria:list[str]=Field(default_factory=list,max_length=5)
class Binding(Closed):
    source:Literal['workflow','step']
    field:str=Field(min_length=1,max_length=60)
    step:str|None=None
class Step(Closed):
    id:str=Field(pattern=r'^[a-z][a-z0-9-]{1,39}$')
    skill_version_id:str
    depends_on:list[str]=Field(default_factory=list,max_length=8)
    inputs:dict[str,Binding]
class Workflow(Closed):
    input_schema:dict
    output_schema:dict
    steps:list[Step]=Field(min_length=1,max_length=12)
    outputs:dict[str,Binding]
TYPES={'agents':Agent,'skills':Skill,'workflows':Workflow}
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def safe_schema(schema,depth=0):
    if not isinstance(schema,dict) or depth>3 or set(schema)-SCHEMA_KEYS:raise ValueError('studio_schema_subset_only')
    kind=schema.get('type')
    if kind not in ('object','array','string','integer','number','boolean'):raise ValueError('studio_schema_type')
    permitted={'type','description','enum'}|({'properties','required','additionalProperties'} if kind=='object' else {'items','maxItems','minItems'} if kind=='array' else {'minLength','maxLength'} if kind=='string' else {'minimum','maximum'} if kind in ('integer','number') else set())
    if set(schema)-permitted:raise ValueError('studio_schema_keywords')
    if 'description' in schema and (not isinstance(schema['description'],str) or len(schema['description'])>300):raise ValueError('studio_schema_description')
    for key in ('minLength','maxLength','maxItems','minItems','minimum','maximum'):
        if key in schema and (type(schema[key]) not in (int,float) or not math.isfinite(schema[key])):raise ValueError('studio_schema_bounds')
        if key in schema and key in ('minLength','maxLength','minItems','maxItems') and type(schema[key]) is not int:raise ValueError('studio_schema_bounds')
    if schema.get('minimum',-1e100)>schema.get('maximum',1e100):raise ValueError('studio_schema_bounds')
    if kind=='object':
        props=schema.get('properties');required=schema.get('required',[])
        if not isinstance(props,dict) or len(props)>16 or schema.get('additionalProperties') is not False:raise ValueError('studio_schema_object_closed')
        if not isinstance(required,list) or not all(isinstance(k,str) and k in props for k in required) or len(set(required))!=len(required):raise ValueError('studio_schema_required')
        for key,value in props.items():
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]{0,59}',key) or key.lower() in SECRET_KEYS:raise ValueError('studio_schema_field')
            safe_schema(value,depth+1)
    if kind=='string' and (type(schema.get('maxLength')) is not int or not 1<=schema['maxLength']<=4096 or not 0<=schema.get('minLength',0)<=schema['maxLength']):raise ValueError('studio_schema_string_bound')
    if kind=='array':
        if type(schema.get('maxItems')) is not int or not 0<=schema['maxItems']<=20 or not 0<=schema.get('minItems',0)<=schema['maxItems']:raise ValueError('studio_schema_array_bound')
        safe_schema(schema.get('items'),depth+1)
    if 'enum' in schema:
        if not isinstance(schema['enum'],list) or not 1<=len(schema['enum'])<=20:raise ValueError('studio_schema_enum')
        for item in schema['enum']:
            if type(item) not in (str,int,float,bool):raise ValueError('studio_schema_enum')
            validate_value({k:v for k,v in schema.items() if k!='enum'},item)
    return schema
def validate_value(schema,value):
    kind=schema['type']
    if kind=='object':
        if not isinstance(value,dict) or set(value)-set(schema['properties']) or set(schema.get('required',[]))-set(value):raise ValueError('studio_value_object')
        for key,item in value.items():validate_value(schema['properties'][key],item)
    elif kind=='string':
        if not isinstance(value,str) or not schema.get('minLength',0)<=len(value)<=schema['maxLength']:raise ValueError('studio_value_string')
    elif kind=='array':
        if not isinstance(value,list) or not schema.get('minItems',0)<=len(value)<=schema['maxItems']:raise ValueError('studio_value_array')
        for item in value:validate_value(schema['items'],item)
    elif kind=='boolean':
        if type(value) is not bool:raise ValueError('studio_value_boolean')
    elif kind in ('integer','number'):
        if type(value) not in ((int,) if kind=='integer' else (int,float)) or not math.isfinite(value):raise ValueError('studio_value_number')
        if value<schema.get('minimum',-1e100) or value>schema.get('maximum',1e100):raise ValueError('studio_value_bounds')
    if 'enum' in schema and not any(type(value) is type(item) and value==item for item in schema['enum']):raise ValueError('studio_value_enum')
    return value
def clean(kind,payload):
    raw=canonical(payload)
    if len(raw.encode())>24576 or BAD_TEXT.search(raw):raise ValueError('studio_unsafe_definition')
    value=TYPES[kind].model_validate(payload).model_dump(mode='json')
    if kind=='agents' and value.get('model_preference'):
        # Additive fields must not change canonical historical definitions.
        for key in ('installation_resource_id','reasoning_effort'):
            if value['model_preference'].get(key) is None:value['model_preference'].pop(key,None)
    if kind=='agents' and value['brain_id']:UUID(value['brain_id'])
    if kind=='skills':
        UUID(value['agent_version_id'])
        if len(set(value['allowed_tools']))!=len(value['allowed_tools']) or any(tool not in READ_TOOLS and not re.fullmatch(r'mcp\.[0-9a-f]{32}\.[a-zA-Z][a-zA-Z0-9_-]{0,19}',tool) for tool in value['allowed_tools']):raise ValueError('studio_tool_escalation_denied')
        if any(not 1<=len(item)<=120 for item in value['exit_criteria']):raise ValueError('studio_exit_criteria')
        for item in value['exit_criteria']:
            match=re.fullmatch(r'(non_empty|equals_input):([a-zA-Z][a-zA-Z0-9_]{0,59})',item)
            if not match:raise ValueError('studio_exit_criteria_subset')
            rule,field=match.groups()
            output=value['output_schema'].get('properties',{}).get(field)
            if not output or output.get('type')!='string' or field not in value['output_schema'].get('required',[]):raise ValueError('studio_exit_criteria_field')
            if rule=='equals_input' and field not in value['input_schema'].get('required',[]):raise ValueError('studio_exit_criteria_input')
    if kind in ('skills','workflows'):
        for key in ('input_schema','output_schema'):
            safe_schema(value[key])
            if value[key]['type']!='object':raise ValueError('studio_schema_root_object')
    if kind=='workflows':
        for step in value['steps']:UUID(step['skill_version_id'])
    return value
def compatible(source,target):
    if source.get('type')!=target.get('type'):return False
    for low,high in (('minLength','maxLength'),('minItems','maxItems'),('minimum','maximum')):
        if source.get(low,0 if low!='minimum' else -1e100)<target.get(low,0 if low!='minimum' else -1e100) or source.get(high,1e100)>target.get(high,1e100):return False
    if target.get('enum') and (not source.get('enum') or not set(source['enum'])<=set(target['enum'])):return False
    if source['type']=='object':return canonical(source)==canonical(target)
    if source['type']=='array':return compatible(source['items'],target['items'])
    return True
def shadow(text,definitions):
    words=set(re.findall(r'\w+',text.casefold()))
    scores=[{'definition_id':row.id,'score':len(words & set(re.findall(r'\w+',row.name.casefold())))} for row in definitions]
    return {'mode':'shadow','execution_allowed':False,'candidates':sorted(scores,key=lambda row:-row['score'])[:3]}
