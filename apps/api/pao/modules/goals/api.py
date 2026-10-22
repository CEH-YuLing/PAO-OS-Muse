"""Admission resources only: explicitly NOT a working goal executor."""
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ...auth import Principal, principal
from ...db import database
from ...access import membership
from ...config import settings
from ...models import GoalExecution, GoalCommand, GoalEvent
from ..studio.service import reject
from . import ledger

router=APIRouter(prefix='/v1',tags=['goal-admission'])


@router.get('/goal-executions/status')
async def admission_status(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    return {'admission_enabled':settings().goal_admission_enabled,'execution_enabled':False,
        'implementation':'admission_ledger_only','dry_run_only':True,'model_calls':False}


@router.post('/goals/{goal_id}/dry-run-admission-preview')
async def preview(goal_id:UUID,body:ledger.Draft,who:Principal=Depends(principal),db=Depends(database)):
    ledger.require_admission()
    goal=await ledger.lock_goal(db,goal_id,who)
    await ledger.guard_goals(db,goal.id)
    envelope,source,fingerprint=await ledger.prepare(db,goal,who,body)
    return {'confirmation_hash':fingerprint,'envelope':envelope,'goal_snapshot':source,
        'initial_proposal':body.proposal,'execution_enabled':False,'dry_run':True}


@router.post('/goals/{goal_id}/dry-run-admissions',status_code=201)
async def admit(goal_id:UUID,body:ledger.Admission,who:Principal=Depends(principal),db=Depends(database)):
    goal=await ledger.lock_goal(db,goal_id,who)
    try:
        row=await ledger.admit(db,goal,who,body)
        await db.commit()
    except IntegrityError:
        await db.rollback();reject('goal_admission_conflict',409)
    return ledger.view(row)


@router.get('/goal-executions/{execution_id}')
async def read(execution_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    row=await db.get(GoalExecution,str(execution_id))
    if not row:reject('goal_execution_not_found',404)
    await membership(db,row.workspace_id,who)
    commands=list(await db.scalars(select(GoalCommand).where(GoalCommand.execution_id==row.id).order_by(GoalCommand.ordinal)))
    events=list(await db.scalars(select(GoalEvent).where(GoalEvent.execution_id==row.id).order_by(GoalEvent.created_at).limit(200)))
    from . import runner
    profile=await db.get(GoalEvent,runner.event_id(row,'bound'))
    value=ledger.view(row)
    if profile:
        await runner.bound(db,row)
        value={**value,'implementation':runner.PROFILE,'execution_enabled':runner.enabled(),'browser_required':False}
    return {**value,'commands':[{'id':c.id,'operation':c.operation,'status':c.status,'attempts':c.attempts,'error_code':c.error_code} for c in commands],
        'events':[{'id':e.id,'action':e.action,'data':e.data,'content_hash':e.content_hash} for e in events]}


@router.post('/goal-executions/{execution_id}/decision')
async def decide(execution_id:UUID,body:ledger.Decision,who:Principal=Depends(principal),db=Depends(database)):
    row=await ledger.lock_execution(db,execution_id)
    await ledger.decide(db,row,who,body);await db.commit()
    return ledger.view(row)


@router.post('/goal-executions/{execution_id}/cancel')
async def cancel(execution_id:UUID,body:ledger.Cancel,who:Principal=Depends(principal),db=Depends(database)):
    row=await ledger.lock_execution(db,execution_id)
    await ledger.cancel(db,row,who,body);await db.commit()
    return ledger.view(row)
