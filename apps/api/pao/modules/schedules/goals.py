"""Schedule -> existing bounded Goal admission. No kernel edits/auto-approval."""
from uuid import UUID,uuid5
from pydantic import Field
from sqlalchemy import select
from fastapi import HTTPException
from ...auth import Principal
from ...models import GoalExecution,GoalScheduleSlot,StudioEvent,now
from ..goals import ledger,runner
from ..goals.evidence import source_pin
from . import store

class GoalScheduleSpec(store.ScheduleSpec):
    goal_id:UUID=Field(strict=False)
    goal_version:int=Field(ge=1,le=2147483647)
    max_iterations:int=Field(default=2,ge=1,le=20)
    max_cost_microusd:int=Field(default=0,ge=0,le=1000000000)
    max_elapsed_seconds:int=Field(default=300,ge=1,le=86400)
    cost_ceiling_microusd:int=Field(default=0,ge=0,le=1000000000)
    max_duration_seconds:int=Field(default=60,ge=1,le=120)
    success_criteria:list[dict]=Field(min_length=1,max_length=5)

class GoalScheduleCreate(GoalScheduleSpec):
    workspace_id:UUID=Field(strict=False)
    request_key:UUID=Field(strict=False)
    confirmation_hash:str=Field(pattern='^[a-f0-9]{64}$')

class GoalScheduleUpdate(GoalScheduleSpec):
    version:int=Field(ge=1)
    request_key:UUID=Field(strict=False)
    confirmation_hash:str=Field(pattern='^[a-f0-9]{64}$')

def is_goal(row):return row.spec.get('kind')=='bounded_goal'

def ready():return store.ready() and runner.enabled()

def draft(spec,plan_id,key):
    # Deadline is a server-time per-run bound, capped by the pinned Goal due_at
    # in ledger.prepare. A schedule confirmation NEVER approves this proposal.
    deadline=int(now().timestamp()*1000)+spec['max_elapsed_seconds']*1000
    return ledger.Draft(request_key=key,goal_version=spec['goal_version'],
        proposal={'plan_id':plan_id,'snapshot_hash':spec['snapshot_hash'],
            'cost_ceiling_microusd':spec['cost_ceiling_microusd'],'max_duration_seconds':spec['max_duration_seconds']},
        policy={'max_iterations':spec['max_iterations'],'max_cost_microusd':spec['max_cost_microusd'],
            'max_elapsed_seconds':spec['max_elapsed_seconds'],'deadline_unix_ms':deadline},
        success_criteria=spec['success_criteria'])

async def pin(db,workspace,actor,body,spec):
    who=Principal(actor,0);goal=await ledger.lock_goal(db,body.goal_id,who)
    if goal.workspace_id!=workspace:store.reject('schedule_goal_scope',404)
    if body.max_elapsed_seconds>body.timeout_seconds:store.reject('schedule_goal_timeout_invalid',422)
    spec.update(body.model_dump(mode='json',include=set(GoalScheduleSpec.model_fields)))
    spec.update(kind='bounded_goal',goal_source=source_pin(goal),runner_profile=runner.PROFILE)
    key=str(uuid5(UUID(goal.id),'schedule-preview'))
    await ledger.prepare(db,goal,who,draft(spec,spec['template_plan_id'],key))
    return spec

async def verify(db,row):
    goal=await ledger.lock_goal(db,row.spec['goal_id'],Principal(row.actor_id,0))
    if (goal.workspace_id!=row.workspace_id or source_pin(goal)!=row.spec['goal_source'] or
        row.spec['runner_profile']!=runner.PROFILE):store.reject('schedule_goal_pin_stale',409)
    # Reuse the existing closed Goal contract + current plan/approver fence.
    await ledger.prepare(db,goal,Principal(row.actor_id,0),
        draft(row.spec,row.spec['template_plan_id'],str(uuid5(UUID(goal.id),'schedule-preview'))))
    return goal

async def active(db,row):
    goal=await ledger.lock_goal(db,row.spec['goal_id'],Principal(row.actor_id,0))
    # Cross-schedule/manual admission must not overlap on the same business Goal.
    # manual_review is unresolved even with a zero-cost Echo reservation.
    if await db.scalar(select(GoalExecution.id).where(GoalExecution.goal_id==goal.id,
        GoalExecution.status=='manual_review').limit(1)):return True
    try:await ledger.guard_goals(db,goal.id)
    except HTTPException as error:
        if error.detail=='goal_owned_by_runner':return True
        raise
    return False

async def admit(db,row,plan,key,slot):
    if not ready():store.reject('schedule_goal_runner_disabled',503)
    goal=await ledger.lock_goal(db,row.spec['goal_id'],Principal(row.actor_id,0))
    if source_pin(goal)!=row.spec['goal_source']:store.reject('schedule_goal_pin_stale',409)
    ident=str(uuid5(UUID(goal.id),key))
    if await db.get(GoalExecution,ident):store.reject('schedule_goal_existing_admission_conflict',409)
    body=draft(row.spec,plan['plan_id'],key)
    _,_,confirmation=await ledger.prepare(db,goal,Principal(row.actor_id,0),body)
    execution=await ledger.admit(db,goal,Principal(row.actor_id,0),ledger.Admission(
        **body.model_dump(),confirmation_hash=confirmation))
    await ledger.audit(db,execution,row.actor_id,'runner_bound',{'profile':runner.PROFILE},runner.event_id(execution,'bound'))
    db.add(GoalScheduleSlot(id=key,schedule_id=row.id,workspace_id=row.workspace_id,
        slot_key=slot,spec_hash=row.spec_hash,execution_id=execution.id))
    return execution
