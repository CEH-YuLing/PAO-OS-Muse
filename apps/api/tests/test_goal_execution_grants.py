"""Real immutable grant ledger; parent/transport still explicit fixtures."""
import asyncio
from datetime import timedelta
import pytest
from sqlalchemy import select,func
from sqlalchemy.exc import DBAPIError
from fastapi import HTTPException
from temporalio.exceptions import ApplicationError
from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,GoalCommand,StudioExecution,StudioCommand,TaskAttempt,Member,now
from pao.modules.goals import iterations,first_projection,execution_grants as grants
from test_goal_admission import goal_gates
from test_goal_iterations import ready,iteration_gates
from test_goal_first_projection import frame


async def eligible(client,identity):
    row,data=await ready(client,identity)
    await iterations.prepare_first(data,'p63-'+row['execution_id'])
    await first_projection.project_first(frame(data,child=False),'p63-'+row['execution_id'])
    return row,{'envelope':data['envelope'],'proposal_hash':data['state']['proposal_hash']}


async def test_grant_once_revalidated_no_child_or_budget_change(client,identity,iteration_gates):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    async with Session() as db:
        before=await db.get(GoalExecution,row['execution_id']);version=before.version;state=before.state
    values=await asyncio.gather(*(grants.issue_first_grant(data,wf) for _ in range(2)))
    assert values[0]==values[1] and values[0]['child_started'] is False
    proof=await grants.verify_first_grant(data,wf)
    assert proof['reserved_cost_microusd']==5 and proof['dry_run'] is True
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.version==version and saved.state==state and saved.reserved_cost_microusd==5
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant'))==1
        child=await db.get(StudioExecution,row['initial_proposal']['plan_id'])
        assert child.status=='starting' and child.sequence==0
    async with Session() as db:
        event=await db.get(GoalEvent,values[0]['grant_id']);event.data={}
        with pytest.raises(DBAPIError):await db.commit()


@pytest.mark.parametrize('kind',['permission','gate','cancel','deadline','budget','parent_ack','decision_ack','child','child_ack','state','proposal','origin'])
async def test_invalid_grant_keeps_reservation_and_no_event(client,identity,iteration_gates,monkeypatch,kind):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    async with Session.begin() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        if kind=='permission':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif kind=='cancel':saved.cancel_requested=True
        elif kind=='budget':saved.reserved_cost_microusd=0
        elif kind in ('parent_ack','decision_ack'):
            item=await db.scalar(select(GoalCommand).where(GoalCommand.operation=='start' if kind=='parent_ack' else GoalCommand.operation=='decision'))
            item.status='pending'
        elif kind=='child':(await db.get(StudioExecution,row['initial_proposal']['plan_id'])).status='running'
        elif kind=='child_ack':
            item=await db.scalar(select(StudioCommand).where(StudioCommand.operation=='start'))
            item.status='delivered';item.attempts=1;item.delivered_at=now()
        elif kind=='state':saved.state={**saved.state,'receipt_hash':'b'*64}
    if kind=='gate':settings().goal_iterations_enabled=False
    if kind=='deadline':monkeypatch.setattr(grants,'now',lambda:now()+timedelta(seconds=120))
    if kind=='proposal':data={**data,'proposal_hash':'b'*64}
    if kind=='origin':wf='p63-'+row['goal_id']
    with pytest.raises((ApplicationError,HTTPException)):await grants.issue_first_grant(data,wf)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant'))==0
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==(0 if kind=='budget' else 5)


@pytest.mark.parametrize('kind',['permission','gate','cancel','deadline'])
async def test_issued_grant_is_not_a_permanent_permission(client,identity,iteration_gates,monkeypatch,kind):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    if kind=='permission':
        async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    elif kind=='cancel':
        async with Session.begin() as db:(await db.get(GoalExecution,row['execution_id'])).cancel_requested=True
    elif kind=='gate':settings().goal_admission_enabled=False
    else:monkeypatch.setattr(grants,'now',lambda:now()+timedelta(seconds=120))
    with pytest.raises((ApplicationError,HTTPException)):await grants.verify_first_grant(data,wf)
    with pytest.raises((ApplicationError,HTTPException)):await grants.issue_first_grant(data,wf)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant'))==1
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


async def test_changed_backend_cannot_reuse_old_grant(client,identity,iteration_gates,monkeypatch):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    old=grants.execution_binding()
    monkeypatch.setattr(grants,'execution_binding',lambda:{**old,'sha256':'b'*64})
    with pytest.raises(ApplicationError):await grants.verify_first_grant(data,wf)
    with pytest.raises(ApplicationError):await grants.issue_first_grant(data,wf)


async def test_lost_mutable_child_projection_never_regrants(client,identity,iteration_gates):
    from pao.modules.studio import durable,step_jobs as jobs
    from test_durable_admission import state
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    async with Session() as db:
        child=await db.get(StudioExecution,row['initial_proposal']['plan_id']);command=child.command
    first=command['steps'][0];args=(child.id,first['step_id'],first['execution_id'])
    await durable.project_state(state({'plan_id':child.id,'snapshot':{'sha256':child.snapshot_hash}},1,'running'))
    await jobs.reserve(*args);assert (await jobs.claim(*args))['claimed'] is True
    async with Session.begin() as db:
        await db.delete(await db.get(TaskAttempt,first['execution_id']))
        child=await db.get(StudioExecution,child.id);child.status='starting';child.sequence=0;child.state={}
    with pytest.raises(ApplicationError):await grants.verify_first_grant(data,wf)
    with pytest.raises(ApplicationError):await grants.issue_first_grant(data,wf)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant'))==1
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
