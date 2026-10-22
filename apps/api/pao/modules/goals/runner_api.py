"""Explicit opt-in runner admission/replan. No browser-facing receipt ingestion."""
from copy import deepcopy
from uuid import UUID
from fastapi import APIRouter,Depends
from pydantic import Field
from sqlalchemy import select
from ...auth import Principal,principal
from ...access import membership
from ...db import database
from ...models import GoalExecution,GoalCommand,GoalEvent,StudioExecution,now
from ..studio import durable
from ..studio.contracts import Closed
from ..studio.service import reject
from . import ledger,runner,iterations
from .evidence import verify_admission

router=APIRouter(prefix='/v1',tags=['goal-runner'])


def view(row):
    return {**ledger.view(row),'implementation':runner.PROFILE,'execution_enabled':runner.enabled(),
        'browser_required':False,'model_calls':False,'business_goal_completed':False}


@router.get('/goal-runners/status')
async def status(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    return {'execution_enabled':runner.enabled(),'profile':runner.PROFILE,'dry_run_only':True,
        'model_calls':False,'browser_required':False,'replan_requires_approval':True}


@router.post('/goals/{goal_id}/dry-run-runners',status_code=201)
async def admit(goal_id:UUID,body:ledger.Admission,who:Principal=Depends(principal),db=Depends(database)):
    if not runner.enabled():reject('goal_runner_disabled',503)
    goal=await ledger.lock_goal(db,goal_id,who)
    from uuid import uuid5
    ident=str(uuid5(UUID(goal.id),ledger.key(body.request_key)))
    existing=await db.get(GoalExecution,ident)
    if existing and not await db.get(GoalEvent,runner.event_id(existing,'bound')):
        reject('goal_runner_cannot_upgrade_legacy_admission',409)
    row=await ledger.admit(db,goal,who,body)
    if not existing:
        await ledger.audit(db,row,row.actor_id,'runner_bound',{'profile':runner.PROFILE},runner.event_id(row,'bound'))
    await db.commit();return view(row)


class GoalRunnerProposal(Closed):
    request_key:str
    version:int=Field(ge=1)
    proposal:dict


@router.post('/goal-executions/{execution_id}/proposal')
async def propose(execution_id:UUID,body:GoalRunnerProposal,who:Principal=Depends(principal),db=Depends(database)):
    if not runner.enabled():reject('goal_runner_disabled',503)
    row=await ledger.lock_execution(db,execution_id)
    await durable.authorize(db,row,who);await verify_admission(db,row)
    ctl=await runner.reconstruct(db,row)
    payload=body.model_dump(exclude={'request_key'})
    from uuid import uuid5
    existing=await db.get(GoalCommand,str(uuid5(UUID(row.id),ledger.key(body.request_key))))
    if existing:
        await ledger.command(db,row,who,body.request_key,'proposal',payload)
        await db.commit();return view(row)
    if not ctl or row.version!=body.version or row.status!='waiting_replan' or row.cancel_requested:
        reject('goal_replan_stale',409)
    pending=await db.scalar(select(GoalCommand.id).where(GoalCommand.execution_id==row.id,
        GoalCommand.operation=='proposal',GoalCommand.status.in_(['pending','processing'])))
    if pending:reject('goal_replan_already_pending',409)
    candidate=deepcopy(ctl)
    try:
        state=candidate.propose(body.proposal,int(now().timestamp()*1000))
        if state['status']!='waiting_approval':reject('goal_replan_budget_or_deadline',409)
    except (ValueError,TypeError,KeyError):reject('goal_replan_invalid',422)
    item,_=await runner.plan(db,row,body.proposal)
    if (await db.get(StudioExecution,item.id) or await db.get(GoalEvent,iterations.claim_id(item.id)) or
        await db.scalar(select(GoalExecution.id).where(GoalExecution.initial_plan_id==item.id))):
        reject('goal_replan_already_owned',409)
    await ledger.audit(db,row,row.actor_id,'runner_plan_reserved',{'plan_id':item.id},iterations.claim_id(item.id))
    await ledger.command(db,row,who,body.request_key,'proposal',payload)
    row.version+=1;row.updated_at=now();await db.commit();return view(row)
