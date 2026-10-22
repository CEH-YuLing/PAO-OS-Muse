"""Authenticated policy preview; NEVER creates a second schedule poller."""
from uuid import UUID
from zoneinfo import ZoneInfoNotFoundError
from fastapi import APIRouter,Depends,HTTPException,Request
from ...access import membership
from ...auth import Principal,principal,rate_limit
from ...db import database
from .policy import SchedulePreview,OWNERS,preview
from sqlalchemy import select
from ...models import StudioSchedule,StudioScheduleSlot,StudioScheduleEvent
from ..studio import durable
from . import store,goals

router=APIRouter(prefix='/v1/schedules',tags=['schedule-policy'])


@router.get('/workflows/status')
async def workflow_status(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    from ...config import settings
    return {'manager_enabled':settings().studio_schedule_manager_enabled,'dispatch_enabled':store.ready(),
        'owner':store.OWNER,'dry_run_only':True,'model_calls':False,'step_approval_required':True,
        'overlap_policy':'latest_eligible_skip_busy','recovery_horizon_days':7}


@router.post('/workflows/preview')
async def workflow_preview(request:Request,workspace_id:UUID,body:store.ScheduleSpec,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who,True)
    await rate_limit(request.app.state.redis,'studio-schedule-preview',who.id,10,60)
    spec,result=await store.pinned(db,str(workspace_id),who.id,body)
    return {'spec':spec,'confirmation_hash':store.digest(spec),'next_at':result['next_at'],
        'owner':store.OWNER,'creates_execution':False,'dry_run_only':True,'model_calls':False}


@router.post('/workflows',status_code=201)
async def create_workflow_schedule(body:store.ScheduleCreate,who:Principal=Depends(principal),db=Depends(database)):
    row=await store.create(db,who,body);await db.commit();return store.view(row)


@router.get('/workflows')
async def list_workflow_schedules(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    rows=list(await db.scalars(select(StudioSchedule).where(StudioSchedule.workspace_id==str(workspace_id),
        StudioSchedule.spec['kind'].as_string().is_distinct_from('bounded_goal')).order_by(StudioSchedule.created_at.desc()).limit(100)))
    for row in rows:await store.verify(db,row)
    return [store.view(row) for row in rows]


@router.get('/workflows/{schedule_id}')
async def read_workflow_schedule(schedule_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    row=await db.get(StudioSchedule,str(schedule_id))
    if not row or goals.is_goal(row):store.reject('schedule_not_found',404)
    await membership(db,row.workspace_id,who);await store.verify(db,row)
    slots=list(await db.scalars(select(StudioScheduleSlot).where(StudioScheduleSlot.schedule_id==row.id).order_by(StudioScheduleSlot.created_at.desc()).limit(100)))
    events=list(await db.scalars(select(StudioScheduleEvent).where(StudioScheduleEvent.schedule_id==row.id).order_by(StudioScheduleEvent.revision.desc()).limit(100)))
    return {**store.view(row),'slots':[{'slot_key':s.slot_key,'spec_hash':s.spec_hash,'execution_id':s.execution_id} for s in slots],
        'events':[{'action':e.action,'revision':e.revision,'data':e.data,'content_hash':e.content_hash} for e in events]}


@router.post('/workflows/{schedule_id}/control')
async def control_workflow_schedule(schedule_id:UUID,body:store.ScheduleControl,who:Principal=Depends(principal),db=Depends(database)):
    row=await store.lock(db,schedule_id,who)
    if goals.is_goal(row):store.reject('schedule_not_found',404)
    await store.control(db,row,who,body);await db.commit();return store.view(row)


@router.patch('/workflows/{schedule_id}')
async def update_workflow_schedule(schedule_id:UUID,body:store.ScheduleUpdate,who:Principal=Depends(principal),db=Depends(database)):
    row=await store.lock(db,schedule_id,who)
    if goals.is_goal(row):store.reject('schedule_not_found',404)
    await store.update(db,row,who,body);await db.commit();return store.view(row)


@router.get('/goals/status')
async def goal_status(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    from ...config import settings
    return {'manager_enabled':settings().studio_schedule_manager_enabled,'dispatch_enabled':goals.ready(),
        'owner':store.OWNER,'kind':'bounded_goal','runner_profile':goals.runner.PROFILE,
        'dry_run_only':True,'model_calls':False,'iteration_approval_required':True,'step_approval_required':True}


@router.post('/goals/preview')
async def goal_preview(request:Request,workspace_id:UUID,body:goals.GoalScheduleSpec,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who,True)
    await rate_limit(request.app.state.redis,'goal-schedule-preview',who.id,10,60)
    spec,result=await store.pinned(db,str(workspace_id),who.id,body)
    return {'spec':spec,'confirmation_hash':store.digest(spec),'next_at':result['next_at'],
        'owner':store.OWNER,'creates_execution':False,'dry_run_only':True,'model_calls':False}


@router.post('/goals',status_code=201)
async def create_goal_schedule(body:goals.GoalScheduleCreate,who:Principal=Depends(principal),db=Depends(database)):
    row=await store.create(db,who,body);await db.commit();return store.view(row)


@router.get('/goals')
async def list_goal_schedules(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    rows=list(await db.scalars(select(StudioSchedule).where(StudioSchedule.workspace_id==str(workspace_id),
        StudioSchedule.spec['kind'].as_string()=='bounded_goal').order_by(StudioSchedule.created_at.desc()).limit(100)))
    for row in rows:await store.verify(db,row)
    return [store.view(row) for row in rows]


@router.get('/goals/{schedule_id}')
async def read_goal_schedule(schedule_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    row=await db.get(StudioSchedule,str(schedule_id))
    if not row or not goals.is_goal(row):store.reject('schedule_not_found',404)
    await membership(db,row.workspace_id,who);await store.verify(db,row)
    slots=list(await db.scalars(select(goals.GoalScheduleSlot).where(goals.GoalScheduleSlot.schedule_id==row.id).order_by(goals.GoalScheduleSlot.created_at.desc()).limit(100)))
    events=list(await db.scalars(select(StudioScheduleEvent).where(StudioScheduleEvent.schedule_id==row.id).order_by(StudioScheduleEvent.revision.desc()).limit(100)))
    return {**store.view(row),'slots':[{'slot_key':s.slot_key,'spec_hash':s.spec_hash,'execution_id':s.execution_id} for s in slots],
        'events':[{'action':e.action,'revision':e.revision,'data':e.data,'content_hash':e.content_hash} for e in events]}


@router.post('/goals/{schedule_id}/control')
async def control_goal_schedule(schedule_id:UUID,body:store.ScheduleControl,who:Principal=Depends(principal),db=Depends(database)):
    row=await store.lock(db,schedule_id,who)
    if not goals.is_goal(row):store.reject('schedule_not_found',404)
    await store.control(db,row,who,body);await db.commit();return store.view(row)


@router.patch('/goals/{schedule_id}')
async def update_goal_schedule(schedule_id:UUID,body:goals.GoalScheduleUpdate,who:Principal=Depends(principal),db=Depends(database)):
    row=await store.lock(db,schedule_id,who)
    if not goals.is_goal(row):store.reject('schedule_not_found',404)
    await store.update(db,row,who,body);await db.commit();return store.view(row)


@router.get('/owners')
async def owners(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    return {'owners':OWNERS,'preview_only':True,'execution_enabled':False}


@router.post('/preview')
async def plan(request:Request,workspace_id:UUID,body:SchedulePreview,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    await rate_limit(request.app.state.redis,'schedule-preview',who.id,10,60)
    try:return preview(body)
    except (ValueError,ZoneInfoNotFoundError):
        raise HTTPException(422,'schedule_policy_invalid')
