"""Pinned schedule lifecycle. No credentials, arbitrary engine or auto-approval."""
from datetime import timedelta
from typing import Literal
from uuid import UUID,uuid5,uuid4
from zoneinfo import ZoneInfoNotFoundError
from pydantic import Field
from sqlalchemy import select,func
from ...auth import Principal
from ...config import settings
from ...models import StudioSchedule,StudioScheduleEvent,StudioScheduleSlot,StudioEvent,StudioExecution,now
from ...skills import execution_binding
from ..studio import durable
from ..studio.contracts import Closed,digest
from ..studio.service import reject
from .policy import SchedulePreview,preview,timestamp

OWNER='runtime.dispatch_studio_schedules.v1'

class ScheduleSpec(Closed):
    template_plan_id:UUID=Field(strict=False)
    mode:Literal['once','cron']
    timezone:str=Field(min_length=1,max_length=80)
    cron:str|None=Field(default=None,max_length=120)
    once_at:str|None=Field(default=None,max_length=40)
    misfire:Literal['skip','coalesce']='coalesce'
    grace_seconds:int=Field(default=300,ge=0,le=86400)
    fold:Literal['first','second']='first'
    timeout_seconds:int=Field(default=3600,ge=1,le=86400)

class ScheduleCreate(ScheduleSpec):
    workspace_id:UUID=Field(strict=False)
    request_key:UUID=Field(strict=False)
    confirmation_hash:str=Field(pattern='^[a-f0-9]{64}$')

class ScheduleUpdate(ScheduleSpec):
    version:int=Field(ge=1)
    request_key:UUID=Field(strict=False)
    confirmation_hash:str=Field(pattern='^[a-f0-9]{64}$')

class ScheduleControl(Closed):
    request_key:UUID=Field(strict=False)
    version:int=Field(ge=1)
    action:Literal['enable','disable','archive']

def require_manager():
    if not settings().studio_schedule_manager_enabled:reject('schedule_manager_disabled',503)

def ready():
    c=settings()
    return all((c.studio_schedule_manager_enabled,c.studio_schedule_dispatch_enabled,c.studio_enabled,
        c.workflow_planning_enabled,c.workflow_durable_enabled,c.temporal_enabled,
        c.workflow_dispatch_enabled,c.workflow_worker_enabled))

def iso(value):return value.isoformat() if value else None

def view(row):
    return {'id':row.id,'workspace_id':row.workspace_id,'actor_id':row.actor_id,'version':row.version,
        'spec':row.spec,'spec_hash':row.spec_hash,'status':row.status,'cursor_at':iso(row.cursor_at),
        'next_at':iso(row.next_at),'error_code':row.error_code,'owner':OWNER,'dry_run':True,'model_calls':False}

def evaluate(spec,after,current):
    values={k:spec[k] for k in ('mode','timezone','cron','once_at','misfire','grace_seconds','fold')}
    try:return preview(SchedulePreview(kind='studio_workflow',after=iso(after),now=iso(current),**values))
    except (ValueError,ZoneInfoNotFoundError):reject('schedule_policy_invalid',422)

async def pinned(db,workspace,actor,body):
    require_manager()
    source=await db.get(StudioEvent,str(body.template_plan_id))
    if not source or source.workspace_id!=workspace:reject('schedule_template_not_found',404)
    snapshot=await durable.verify_plan(db,source,actor)
    spec=body.model_dump(mode='json',include=set(ScheduleSpec.model_fields))
    spec.update(snapshot_hash=snapshot['sha256'],source_binding=execution_binding()['sha256'])
    from . import goals
    if isinstance(body,goals.GoalScheduleSpec):spec=await goals.pin(db,workspace,actor,body,spec)
    result=evaluate(spec,now(),now())
    if spec['mode']=='once' and timestamp(spec['once_at'])<=now():reject('schedule_once_requires_future',422)
    if not result['next_at']:reject('schedule_no_occurrence_within_horizon',422)
    return spec,result

async def audit(db,row,actor,action,request_key=None,request_hash=None,details=None):
    ident=str(uuid5(UUID(row.id),str(request_key))) if request_key else str(uuid4())
    data={'projection':view(row),'request_hash':request_hash,'details':details}
    content=digest({'actor_id':actor,'action':action,'data':data})
    db.add(StudioScheduleEvent(id=ident,schedule_id=row.id,workspace_id=row.workspace_id,
        actor_id=actor,action=action,revision=row.version,data=data,content_hash=content))
    await db.flush()

async def verify(db,row):
    event=await db.scalar(select(StudioScheduleEvent).where(StudioScheduleEvent.schedule_id==row.id,
        StudioScheduleEvent.revision==row.version))
    if (row.spec_hash!=digest(row.spec) or not event or event.data['projection']!=view(row) or
        event.content_hash!=digest({'actor_id':event.actor_id,'action':event.action,'data':event.data})):
        reject('schedule_projection_invalid',409)

async def lock(db,ident,who):
    row=await db.scalar(select(StudioSchedule).where(StudioSchedule.id==str(ident)).with_for_update().execution_options(populate_existing=True))
    if not row:reject('schedule_not_found',404)
    await durable.authorize(db,row,who);await verify(db,row)
    return row

async def replay(db,row,who,key,payload):
    event=await db.get(StudioScheduleEvent,str(uuid5(UUID(row.id),str(key))))
    fingerprint=digest({'actor_id':who.id,'payload':payload})
    if event:
        if event.data['request_hash']!=fingerprint:reject('schedule_request_conflict',409)
        return True,fingerprint
    return False,fingerprint

async def create(db,who,body):
    require_manager();workspace=str(body.workspace_id)
    # Workspace lock serializes request-key dedup and the bounded row quota.
    from ...models import Workspace
    await db.scalar(select(Workspace).where(Workspace.id==workspace).with_for_update())
    from ...access import membership
    await membership(db,workspace,who,True)
    ident=str(uuid5(UUID(workspace),who.id+':'+str(body.request_key)))
    row=await db.get(StudioSchedule,ident)
    if row:
        await durable.authorize(db,row,who);await verify(db,row)
        await replay(db,row,who,body.request_key,body.model_dump(mode='json'));return row
    if await db.scalar(select(func.count()).select_from(StudioSchedule).where(StudioSchedule.workspace_id==workspace))>=100:
        reject('schedule_workspace_limit',409)
    spec,result=await pinned(db,workspace,who.id,body)
    if digest(spec)!=body.confirmation_hash:reject('schedule_confirmation_stale',409)
    row=StudioSchedule(id=ident,workspace_id=workspace,actor_id=who.id,spec=spec,spec_hash=digest(spec),
        cursor_at=now(),next_at=timestamp(result['next_at']),status='disabled',version=1)
    db.add(row);await db.flush()
    _,fingerprint=await replay(db,row,who,body.request_key,body.model_dump(mode='json'))
    await audit(db,row,who.id,'created',body.request_key,fingerprint);return row

async def active(db,row):
    from . import goals
    if goals.is_goal(row):return await goals.active(db,row)
    return await db.scalar(select(StudioExecution.id).join(StudioScheduleSlot,StudioScheduleSlot.execution_id==StudioExecution.id)
        .where(StudioScheduleSlot.schedule_id==row.id,StudioExecution.status.not_in(['completed','cancelled'])).limit(1))

async def control(db,row,who,body):
    if body.action=='enable':require_manager()
    done,fingerprint=await replay(db,row,who,body.request_key,body.model_dump(mode='json'))
    if done:return row
    if row.version!=body.version or row.status=='archived':reject('schedule_version_or_status_stale',409)
    stamp=now()
    if body.action=='enable':
        if await active(db,row):reject('schedule_previous_execution_unresolved',409)
        # Enabling does not resurrect slots missed while disabled.
        source=await db.get(StudioEvent,row.spec['template_plan_id'])
        snapshot=await durable.verify_plan(db,source,row.actor_id)
        if snapshot['sha256']!=row.spec['snapshot_hash'] or row.spec['source_binding']!=execution_binding()['sha256']:
            reject('schedule_source_pin_stale',409)
        from . import goals
        if goals.is_goal(row):await goals.verify(db,row)
        result=evaluate(row.spec,stamp,stamp)
        if not result['next_at']:reject('schedule_expired_or_no_next_slot',409)
        row.cursor_at=stamp;row.next_at=timestamp(result['next_at'])
    row.status={'enable':'enabled','disable':'disabled','archive':'archived'}[body.action]
    row.error_code=None;row.version+=1
    await audit(db,row,who.id,body.action,body.request_key,fingerprint);return row

async def update(db,row,who,body):
    require_manager();done,fingerprint=await replay(db,row,who,body.request_key,body.model_dump(mode='json'))
    if done:return row
    if row.version!=body.version or row.status not in ('disabled','manual_review') or await active(db,row):
        reject('schedule_disable_and_drain_before_edit',409)
    spec,result=await pinned(db,row.workspace_id,row.actor_id,body)
    if digest(spec)!=body.confirmation_hash:reject('schedule_confirmation_stale',409)
    row.spec=spec;row.spec_hash=digest(spec);row.cursor_at=now();row.next_at=timestamp(result['next_at'])
    row.status='disabled';row.error_code=None;row.version+=1
    await audit(db,row,who.id,'configured',body.request_key,fingerprint);return row
