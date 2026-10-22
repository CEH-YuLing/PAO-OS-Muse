"""P6.1 data-only DAG compilation; no runner, attempts, model or tool calls."""
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL
from sqlalchemy import select, cast
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import Field
from ...config import settings
from ...models import StudioDefinition, StudioVersion, StudioEvent, Task, TaskDependency, TaskActivity
from .contracts import Closed, canonical, digest, BAD_TEXT, SECRET_KEYS, validate_value
from .service import version, lint, reject


class PlanInput(Closed):
    version_id: str
    request_key: str
    input: dict


class PlanCreate(PlanInput):
    confirmation_hash: str = Field(pattern=r'^[a-f0-9]{64}$')


def require_planning():
    if not settings().workflow_planning_enabled:
        reject('workflow_planning_disabled',503)


async def guard_planned_task(db, task):
    from ..business_planning.review import guard_native
    await guard_native(db,task_id=task.id)
    from ..goals.ledger import guard_goals
    await guard_goals(db,task.goal_id)
    # Check authoritative immutable ledger, never editable task metadata or flags.
    found=await db.scalar(select(StudioEvent.id).where(StudioEvent.workspace_id==task.workspace_id,
        StudioEvent.action=='p61_plan_created',cast(StudioEvent.data,JSONB)['task_ids'].contains([task.id])).limit(1))
    if found:reject('workflow_plan_tasks_frozen_no_runner',409)


def clean_input(value):
    try:
        raw=canonical(value)
        if len(raw.encode())>16384 or BAD_TEXT.search(raw):raise ValueError()
        def walk(item,depth=0):
            if depth>8:raise ValueError()
            if isinstance(item,dict):
                for key,child in item.items():
                    if key.casefold() in SECRET_KEYS:raise ValueError()
                    walk(child,depth+1)
            elif isinstance(item,list):
                for child in item:walk(child,depth+1)
        walk(value)
    except (ValueError,TypeError,OverflowError,RecursionError):reject('workflow_plan_input_unsafe')


def identity(definition,actor,body):
    try:
        request=str(UUID(body.request_key));version_id=str(UUID(body.version_id))
    except ValueError:reject('workflow_plan_ids_invalid')
    return str(uuid5(NAMESPACE_URL,f'p61:{definition.workspace_id}:{definition.id}:{actor}:{request}')),digest({
        'version_id':version_id,'request_key':request,'input':body.input,'actor_id':actor})


async def compile_plan(db,definition,actor,body):
    require_planning();clean_input(body.input)
    if definition.kind!='workflows':reject('workflow_plan_requires_workflow')
    workflow=await version(db,str(UUID(body.version_id)),definition.workspace_id,'workflows')
    if workflow.definition_id!=definition.id:reject('workflow_plan_version_scope')
    value,links=await lint(db,definition,workflow.payload,actor)
    try:validate_value(value['input_schema'],body.input)
    except (ValueError,TypeError):reject('workflow_plan_input_schema')
    ordered=[];remaining={step['id']:step for step in value['steps']}
    while remaining:
        ready=sorted(key for key,item in remaining.items() if set(item['depends_on'])<=set(ordered))
        if not ready:reject('studio_workflow_cycle')
        for key in ready:ordered.append(key);remaining.pop(key)
    steps={step['id']:step for step in value['steps']};pins=[]
    for key in ordered:
        step=steps[key];skill=await version(db,step['skill_version_id'],definition.workspace_id,'skills')
        agent=await version(db,skill.payload['agent_version_id'],definition.workspace_id,'agents')
        for row in (workflow,skill,agent):
            if not await db.scalar(select(StudioEvent.id).where(StudioEvent.version_id==row.id,StudioEvent.action=='review')):
                reject('workflow_plan_review_missing',409)
        preference=agent.payload.get('model_preference') or {'provider':'ollama','model':settings().ollama_model}
        if preference['provider']!='ollama':reject('workflow_plan_local_model_only',409)
        pins.append({'step_id':key,'depends_on':step['depends_on'],
            'skill':{'version_id':skill.id,'hash':skill.content_hash,'payload':skill.payload},
            'agent':{'version_id':agent.id,'hash':agent.content_hash,'payload':agent.payload},
            'model':{**preference,'pin_scope':'model_name_configuration','weights_verified':False},
            'input_bindings':step['inputs'],
            'resolved_workflow_inputs':{field:body.input[binding['field']] for field,binding in step['inputs'].items() if binding['source']=='workflow'},
            'expected_evidence':{'schema':skill.payload['output_schema'],'schema_hash':digest(skill.payload['output_schema']),
                                 'exit_criteria':skill.payload['exit_criteria'],'observed':False}})
    snapshot={'format':'p61-plan-v1','compiler_version':'p61-local-dag-v1','workspace_id':definition.workspace_id,
        'actor_id':actor,'workflow':{'definition_id':definition.id,'version_id':workflow.id,'hash':workflow.content_hash,'payload':value},
        'input':body.input,'input_hash':digest(body.input),'steps':pins,'outputs':value['outputs'],
        'linked_versions':links,'execution_enabled':False,'attempts_created':False,'evidence_verified':False}
    if len(canonical(snapshot).encode())>262144:reject('workflow_plan_snapshot_limit')
    return {**snapshot,'sha256':digest(snapshot)}


async def save_plan(db,definition,actor,body):
    require_planning();clean_input(body.input)
    plan_id,fingerprint=identity(definition,actor,body)
    existing=await db.get(StudioEvent,plan_id)
    if existing:
        if existing.workspace_id!=definition.workspace_id or existing.definition_id!=definition.id or existing.actor_id!=actor:
            reject('workflow_plan_scope',404)
        if existing.action!='p61_plan_created' or existing.data['request_hash']!=fingerprint or existing.data['snapshot']['sha256']!=body.confirmation_hash:
            reject('workflow_plan_request_conflict',409)
        return existing.data
    count=len(list(await db.scalars(select(StudioEvent.id).where(StudioEvent.definition_id==definition.id,
        StudioEvent.action=='p61_plan_created').limit(100))))
    if count>=100:reject('workflow_plan_limit',409)
    snapshot=await compile_plan(db,definition,actor,body)
    if snapshot['sha256']!=body.confirmation_hash:reject('workflow_plan_preview_stale',409)
    ids={step['step_id']:str(uuid5(UUID(plan_id),step['step_id'])) for step in snapshot['steps']}
    tasks=[]
    for step in snapshot['steps']:
        ident=ids[step['step_id']]
        task=Task(id=ident,workspace_id=definition.workspace_id,title=f'{definition.name[:150]} / {step["step_id"]}',
            description='P6.1 immutable planning task. No execution; runner is not enabled.',status='draft',kind='human',
            source='pao',created_by=actor,assignee_type='unassigned',
            dependencies=[ids[key] for key in step['depends_on']],success_criteria=step['expected_evidence']['exit_criteria'] or ['Output must match pinned schema; no output has been produced.'],
            input_references=[{'plan_id':plan_id,'step_id':step['step_id'],'snapshot_hash':snapshot['sha256']}],
            result_reference={'type':'p61_planned_step','plan_id':plan_id,'execution_id':ident,'step_id':step['step_id'],'executed':False})
        db.add(task);tasks.append(task)
    await db.flush()
    for step,task in zip(snapshot['steps'],tasks):
        for key in step['depends_on']:
            db.add(TaskDependency(workspace_id=definition.workspace_id,task_id=task.id,depends_on_task_id=ids[key],created_by=actor))
        db.add(TaskActivity(workspace_id=definition.workspace_id,task_id=task.id,actor_id=actor,
                           event='workflow_planned',data={'plan_id':plan_id,'execution_enabled':False}))
    data={'plan_id':plan_id,'request_hash':fingerprint,'snapshot':snapshot,'task_ids':list(ids.values()),
          'steps':[{'step_id':key,'task_id':ident,'execution_id':ident} for key,ident in ids.items()]}
    db.add(StudioEvent(id=plan_id,workspace_id=definition.workspace_id,definition_id=definition.id,
        version_id=snapshot['workflow']['version_id'],actor_id=actor,action='p61_plan_created',data=data))
    await db.flush()
    return data
