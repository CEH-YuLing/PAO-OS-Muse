"""Native DB no-claim fence; NOT a real Temporal/ARQ queue-drain test."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from temporalio.exceptions import ApplicationError

from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,GoalCommand,StudioExecution,StudioCommand,TaskAttempt,Member,now
from pao.modules.goals import cancel_recovery,iterations
from pao.modules.studio import durable,step_jobs as jobs
from test_goal_admission import goal_gates
from test_goal_iterations import iteration_gates
from test_goal_recovery import stopped
from test_durable_admission import state


async def cancelled(client,identity,monkeypatch,reserved=False,claimed=False):
    row,data=await stopped(client,identity,monkeypatch,with_result=False,cancel=True)
    plan_id=row['initial_proposal']['plan_id']
    async with Session() as db:child=await db.get(StudioExecution,plan_id);command=child.command
    value={'plan_id':plan_id,'snapshot':{'sha256':command['snapshot_hash']}}
    if reserved:
        await durable.project_state(state(value,1,'running'))
        first=command['steps'][0]
        await jobs.reserve(plan_id,first['step_id'],first['execution_id'])
        if claimed:assert (await jobs.claim(plan_id,first['step_id'],first['execution_id']))['claimed'] is True
    assert (await client.post('/v1/studio/executions/'+plan_id+'/cancel',headers=identity['owner'],
        json={'request_key':str(uuid4())})).status_code==200
    # Explicit simulated delivery ACKs, not real dispatcher/transport evidence.
    async with Session.begin() as db:
        for model in (GoalCommand,StudioCommand):
            item=await db.scalar(select(model).where(model.operation=='cancel'))
            item.status='delivered';item.attempts=1;item.delivered_at=now()
    if reserved:await jobs.recover(plan_id,command['steps'][0]['step_id'],command['steps'][0]['execution_id'])
    await durable.project_state(state(value,2 if reserved else 1,'cancelled',cancel_requested=True,reason='requested'))
    return row,data,command


@pytest.mark.parametrize('reserved',[False,True])
async def test_cancel_no_claim_concurrent_and_late_claim_fenced(client,identity,iteration_gates,monkeypatch,reserved):
    row,data,command=await cancelled(client,identity,monkeypatch,reserved);ident='p63-'+row['execution_id']
    settings().goal_admission_enabled=False;settings().goal_iterations_enabled=False
    values=await asyncio.gather(*(cancel_recovery.reconcile_cancelled_before_claim(data,ident) for _ in range(2)))
    assert values[0]==values[1] and values[0]['known_no_effect'] is True and values[0]['resumed'] is False
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id']);version=saved.version
        assert saved.status=='manual_review' and saved.reserved_cost_microusd==0
        assert saved.state['reserved_cost_microusd']==0 and saved.state['cancel_requested'] is True
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='cancel_before_claim_reconciled'))==1
    first=command['steps'][0]
    with pytest.raises(HTTPException):await jobs.claim(command['plan_id'],first['step_id'],first['execution_id'])
    await cancel_recovery.reconcile_cancelled_before_claim(data,ident)
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).version==version


@pytest.mark.parametrize('kind',['permission','parent_ack','child_ack','child_flag','child_projection','ledger','attempt'])
async def test_invalid_cancel_proof_holds_reservation(client,identity,iteration_gates,monkeypatch,kind):
    row,data,command=await cancelled(client,identity,monkeypatch)
    async with Session.begin() as db:
        if kind=='permission':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif kind in ('parent_ack','child_ack'):
            model=GoalCommand if kind=='parent_ack' else StudioCommand
            (await db.scalar(select(model).where(model.operation=='cancel'))).status='pending'
        elif kind=='child_flag':(await db.get(StudioExecution,command['plan_id'])).cancel_requested=False
        elif kind=='child_projection':(await db.get(StudioExecution,command['plan_id'])).state={'status':'cancelled'}
        elif kind=='ledger':
            saved=await db.get(GoalExecution,row['execution_id']);saved.state={**saved.state,'reason':'forged'}
        else:
            first=command['steps'][0]
            db.add(TaskAttempt(id=first['execution_id'],workspace_id=identity['workspace'],task_id=first['execution_id'],
                request_key='p62:'+first['execution_id'],input_fingerprint='b'*64,attempt_no=1,status='running',input={},skill_snapshot={},result={},evidence=[]))
    with pytest.raises((ApplicationError,HTTPException)):
        await cancel_recovery.reconcile_cancelled_before_claim(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='cancel_before_claim_reconciled'))==0


@pytest.mark.parametrize('delete_attempt',[False,True])
async def test_claimed_then_cancelled_is_not_absence(client,identity,iteration_gates,monkeypatch,delete_attempt):
    row,data,command=await cancelled(client,identity,monkeypatch,reserved=True,claimed=True)
    if delete_attempt:
        async with Session.begin() as db:
            await db.delete(await db.get(TaskAttempt,command['steps'][0]['execution_id']))
    with pytest.raises(ApplicationError,match='step_claimed'):
        await cancel_recovery.reconcile_cancelled_before_claim(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
