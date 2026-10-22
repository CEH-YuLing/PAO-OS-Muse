"""P6.3B2a admission/outbox only. No Temporal dispatch or receipt ingestion."""
from uuid import UUID, uuid5
from typing import Literal
from pydantic import Field
from sqlalchemy import select, func, or_
from ...models import Goal, GoalExecution, GoalCommand, GoalEvent, StudioEvent, StudioDefinition, StudioExecution, now
from ...config import settings
from ...auth import Principal
from ..studio import durable
from ..studio.contracts import Closed, digest, BAD_TEXT
from ..studio.service import reject
from .control import GoalControl, TERMINAL, validate, uuid
from .evidence import source_pin, verify_admission


class Draft(Closed):
    request_key: str
    goal_version: int=Field(ge=1,le=2147483647)
    proposal: dict
    policy: dict
    success_criteria: list[dict]=Field(min_length=1,max_length=5)


class Admission(Draft):
    confirmation_hash: str=Field(pattern=r'^[a-f0-9]{64}$')


class Decision(Closed):
    request_key: str
    version: int=Field(ge=1)
    proposal_hash: str=Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['approve','reject']


class Cancel(Closed):
    request_key: str


def key(value):
    try: uuid(value)
    except (ValueError,TypeError,AttributeError): reject('goal_request_key_invalid')
    return value


def require_admission():
    if not all((settings().goal_admission_enabled, settings().studio_enabled, settings().workflow_planning_enabled)):
        reject('goal_admission_disabled',503)


async def guard_goals(db, *ids):
    from ..business_planning.review import guard_native
    # Same Goal locks/order for task moves and admissions: no check/commit race.
    for ident in sorted({str(i) for i in ids if i}):
        await db.scalar(select(Goal).where(Goal.id==ident).with_for_update())
        await guard_native(db,goal_id=ident)
        active=await db.scalar(select(GoalExecution.id).where(GoalExecution.goal_id==ident,
            or_(GoalExecution.status.not_in(TERMINAL),GoalExecution.reserved_cost_microusd>0,
                select(GoalCommand.id).where(GoalCommand.execution_id==GoalExecution.id,
                    GoalCommand.status.in_(['pending','processing'])).exists())).limit(1))
        if active: reject('goal_owned_by_runner',409)


async def lock_goal(db, ident, who):
    row=await db.scalar(select(Goal).where(Goal.id==str(ident)).with_for_update().execution_options(populate_existing=True))
    if not row: reject('goal_not_found',404)
    await durable.authorize(db,row,who)
    from ..business_planning.review import guard_native
    await guard_native(db,goal_id=row.id)
    return row


async def lock_execution(db,ident):
    row=await db.scalar(select(GoalExecution).where(GoalExecution.id==str(ident)).with_for_update().execution_options(populate_existing=True))
    if not row: reject('goal_execution_not_found',404)
    return row


def view(row):
    return {'execution_id':row.id,'goal_id':row.goal_id,'workspace_id':row.workspace_id,
        'status':row.status,'version':row.version,'sequence':row.sequence,'state':row.state,
        'envelope':row.envelope,'initial_proposal':row.initial_proposal,'admission_hash':row.admission_hash,
        'reserved_cost_microusd':row.reserved_cost_microusd,'cancel_requested':row.cancel_requested,
        'dry_run':True,'model_executed':False,'execution_enabled':False,'implementation':'admission_ledger_only'}


async def prepare(db, goal, who, body):
    key(body.request_key)
    if goal.version!=body.goal_version or goal.status not in ('draft','active'):
        reject('goal_version_or_status_stale',409)
    ident=str(uuid5(UUID(goal.id),body.request_key))
    p=body.proposal
    if type(p) is not dict or type(p.get('plan_id')) is not str: reject('goal_proposal_invalid')
    envelope={'format':'p63-dryrun-goal-v1','execution_id':ident,'goal_id':goal.id,
        'goal_version':goal.version,'actor_id':who.id,'workspace_id':goal.workspace_id,
        'plan_id':p['plan_id'],'snapshot_hash':p.get('snapshot_hash'),
        'policy':dict(body.policy),'success_criteria':body.success_criteria}
    try:
        validate(envelope)
        if goal.due_at:
            envelope['policy']['deadline_unix_ms']=min(envelope['policy']['deadline_unix_ms'],int(goal.due_at.timestamp()*1000))
        for criterion in envelope['success_criteria']:
            if criterion['value'] is not None and BAD_TEXT.search(criterion['value']):
                raise ValueError('goal_criteria_unsafe')
        stamp=int(now().timestamp()*1000)
        control=GoalControl(envelope,stamp)
        state=control.propose(p,stamp)
        if state['status']!='waiting_approval':reject('goal_budget_or_deadline',409)
    except (ValueError,TypeError,AttributeError): reject('goal_contract_invalid')
    plan=await db.get(StudioEvent,p['plan_id'])
    if not plan or plan.action!='p61_plan_created' or plan.workspace_id!=goal.workspace_id:
        reject('goal_plan_not_found',404)
    # Serializes P6.2 standalone starts versus goal admission of the same plan.
    await db.scalar(select(StudioDefinition).where(StudioDefinition.id==plan.definition_id).with_for_update())
    if await db.get(StudioExecution,plan.id) or await db.scalar(select(GoalExecution.id).where(GoalExecution.initial_plan_id==plan.id)):
        reject('goal_plan_already_owned',409)
    snapshot=await durable.verify_plan(db,plan,who.id)
    if snapshot['sha256']!=p['snapshot_hash']:reject('goal_plan_pin_stale',409)
    # Pin free-text Goal content without duplicating sensitive text into another
    # ledger/preview/history. Criteria for the fixture subset are separate.
    source=source_pin(goal)
    # Text criteria are an explicitly approved dry-run subset, not a proof of
    # the free-text M1 Goal's business completion. Never auto-complete M1 here.
    fingerprint=digest({'envelope':envelope,'initial_proposal':p,'goal_snapshot':source})
    return envelope,source,fingerprint


async def audit(db,row,actor,action,data,ident):
    db.add(GoalEvent(id=ident,execution_id=row.id,workspace_id=row.workspace_id,actor_id=actor,
        action=action,data=data,content_hash=digest({'action':action,'data':data,'actor_id':actor})))


async def command(db,row,who,key_value,operation,payload):
    ident=str(uuid5(UUID(row.id),key(key_value)))
    fingerprint=digest({'operation':operation,'payload':payload,'actor_id':who.id})
    existing=await db.get(GoalCommand,ident)
    if existing:
        if existing.content_hash!=fingerprint:reject('goal_request_conflict',409)
        return existing,True
    ordinal=(await db.scalar(select(func.max(GoalCommand.ordinal)).where(GoalCommand.execution_id==row.id)) or 0)+1
    item=GoalCommand(id=ident,workspace_id=row.workspace_id,execution_id=row.id,actor_id=who.id,
        request_key=key_value,ordinal=ordinal,operation=operation,payload=payload,content_hash=fingerprint)
    db.add(item)
    await audit(db,row,who.id,'command',{'command_id':ident,'operation':operation,'ordinal':ordinal},str(uuid5(UUID(ident),'audit')))
    await db.flush()
    return item,False


async def admit(db,goal,who,body):
    require_admission();key(body.request_key)
    ident=str(uuid5(UUID(goal.id),body.request_key))
    existing=await db.get(GoalExecution,ident)
    payload=body.model_dump()
    if existing:
        if existing.actor_id!=who.id:reject('goal_admission_actor_mismatch',403)
        await command(db,existing,who,body.request_key,'start',payload)
        return existing
    await guard_goals(db,goal.id)
    envelope,source,fingerprint=await prepare(db,goal,who,body)
    if fingerprint!=body.confirmation_hash:reject('goal_confirmation_stale',409)
    row=GoalExecution(id=ident,workspace_id=goal.workspace_id,goal_id=goal.id,actor_id=who.id,
        initial_plan_id=envelope['plan_id'],temporal_id='p63-'+ident,envelope=envelope,
        goal_snapshot=source,initial_proposal=body.proposal,admission_hash=fingerprint,
        state={'reason':'awaiting_unimplemented_dispatch','dry_run':True,'model_executed':False})
    db.add(row);await db.flush()
    await audit(db,row,who.id,'admitted',{'admission_hash':fingerprint,'goal_version':goal.version},str(uuid5(UUID(ident),'admission-audit')))
    await command(db,row,who,body.request_key,'start',payload)
    return row


async def decide(db,row,who,body):
    await durable.authorize(db,row,who);require_admission()
    await verify_admission(db,row)
    payload=body.model_dump(exclude={'request_key'})
    ident=str(uuid5(UUID(row.id),key(body.request_key)))
    if await db.get(GoalCommand,ident):
        await command(db,row,who,body.request_key,'decision',payload)
        return row
    if row.version!=body.version or row.status!='waiting_approval' or row.cancel_requested or row.state.get('proposal_hash')!=body.proposal_hash:
        reject('goal_decision_stale',409)
    prior=await db.scalar(select(GoalCommand.id).where(GoalCommand.execution_id==row.id,
        GoalCommand.operation=='decision',GoalCommand.payload['proposal_hash'].as_string()==body.proposal_hash))
    if prior:reject('goal_proposal_already_decided',409)
    # Check admission actor, Goal snapshot and plan again before any approval.
    goal=await db.get(Goal,row.goal_id)
    await durable.authorize(db,row,Principal(row.actor_id,0))
    if goal.version!=row.envelope['goal_version']:reject('goal_pin_changed',409)
    plan_id=row.state.get('proposal',{}).get('plan_id')
    plan=await db.get(StudioEvent,plan_id) if plan_id else None
    snapshot=await durable.verify_plan(db,plan,row.actor_id)
    if snapshot['sha256']!=row.state['proposal'].get('snapshot_hash'):reject('goal_plan_pin_stale',409)
    await command(db,row,who,body.request_key,'decision',payload)
    row.version+=1;row.updated_at=now()
    return row


async def cancel(db,row,who,body):
    await durable.authorize(db,row,who)  # works even when admission rolled back
    item,replay=await command(db,row,who,body.request_key,'cancel',{})
    if replay:return row
    if row.status in TERMINAL and row.reserved_cost_microusd==0:
        item.status='delivered';item.delivered_at=now();return row
    row.cancel_requested=True;row.version+=1;row.updated_at=now()
    start=await db.scalar(select(GoalCommand).where(GoalCommand.execution_id==row.id,GoalCommand.operation=='start').with_for_update())
    if row.status=='starting' and row.sequence==0 and row.reserved_cost_microusd==0 and start.status=='pending' and start.attempts==0:
        start.status='dead';start.error_code='cancelled_before_dispatch'
        item.status='delivered';item.delivered_at=now();row.status='cancelled'
        row.state={'reason':'cancelled_before_dispatch','dry_run':True,'model_executed':False}
    return row
