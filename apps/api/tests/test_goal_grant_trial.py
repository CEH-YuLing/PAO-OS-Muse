"""Actual experimental Temporal parent/child, with fixture Goal admission ACKs."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from temporalio import activity
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError,WorkflowAlreadyStartedError
from temporalio.client import WorkflowFailureError
from temporalio.service import RPCError,RPCStatusCode
from temporalio.worker import Worker,Replayer
from pao.config import settings
from pao.db import Session
from pao.models import GoalExecution,GoalEvent,TaskAttempt,StudioCommand,Member
from pao.modules.goals import execution_grants as grants
from pao.modules.goals.grant_trial import PaoGrantChildTrialWorkflow as Trial
from pao.modules.studio import durable
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as Child
from test_goal_execution_grants import eligible
from test_goal_iterations import iteration_gates
from test_goal_admission import goal_gates
from test_goal_temporal_kernel import temporal


async def waiting_child(handle):
    for _ in range(100):
        try:
            state=await handle.query('state')
            if state['status']=='waiting_approval':return state
        except RPCError as exc:
            if exc.status!=RPCStatusCode.NOT_FOUND:raise
        await asyncio.sleep(.1)
    pytest.fail('real child did not reach waiting approval')


async def test_concurrent_consumers_only_one(client,identity,iteration_gates):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    results=await asyncio.gather(*(grants.consume_first_grant(data,wf,
        experiment_id='p63-grant-trial-'+row['execution_id']) for _ in range(2)),return_exceptions=True)
    assert sum(isinstance(r,dict) for r in results)==1
    assert sum(isinstance(r,ApplicationError) for r in results)==1
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant_consumed'))==1
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0


@pytest.mark.parametrize('kind',['gate','permission','cancel','origin'])
async def test_reauthorize_before_consumption(client,identity,iteration_gates,kind):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    trial='p63-grant-trial-'+row['execution_id']
    if kind=='gate':settings().goal_iterations_enabled=False
    elif kind=='origin':trial='wrong'
    else:
        async with Session.begin() as db:
            if kind=='cancel':(await db.get(GoalExecution,row['execution_id'])).cancel_requested=True
            else:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    with pytest.raises((ApplicationError,HTTPException)):
        await grants.consume_first_grant(data,wf,experiment_id=trial)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant_consumed'))==0


@pytest.mark.parametrize('lost_ack',[False,True])
async def test_real_trial_child_once_or_fail_closed(client,identity,iteration_gates,temporal,monkeypatch,lost_ack):
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    env,directory=temporal;queue='p63-trial-'+uuid4().hex
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',queue)
    trial_id='p63-grant-trial-'+row['execution_id']
    @activity.defn(name='p63_trial_consume_grant')
    async def lose_ack(item:dict):
        await grants.consume_trial_activity(item)
        raise ApplicationError('synthetic_commit_without_ack',non_retryable=True)
    consume=lose_ack if lost_ack else grants.consume_trial_activity
    async with Worker(env.client,task_queue=queue,workflows=[Trial,Child],
            activities=[consume,durable.project_state],graceful_shutdown_timeout=timedelta(seconds=2)):
        handle=await env.client.start_workflow(Trial.run,data,id=trial_id,task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        if lost_ack:
            with pytest.raises(WorkflowFailureError):await asyncio.wait_for(handle.result(),20)
            # An ambiguous consume must remain spent, including direct retry.
            with pytest.raises(ApplicationError,match='goal_grant_already_consumed'):
                await grants.consume_first_grant(data,wf,experiment_id=trial_id)
        else:
            child=env.client.get_workflow_handle('p62-'+row['initial_proposal']['plan_id'])
            await waiting_child(child)
            await handle.signal('request_cancel')
            assert await asyncio.wait_for(handle.result(),20)=={'status':'cancelled','child_started':True,'dry_run':True}
            child_history=await child.fetch_history()
            attrs=child_history.events[0].workflow_execution_started_event_attributes
            assert attrs.parent_workflow_execution.workflow_id==trial_id
            await Replayer(workflows=[Child]).replay_workflow(child_history)
        with pytest.raises(WorkflowAlreadyStartedError):
            await env.client.start_workflow(Trial.run,data,id=trial_id,task_queue=queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
    history=await handle.fetch_history()
    assert sum(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)==(0 if lost_ack else 1)
    await Replayer(workflows=[Trial]).replay_workflow(history)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant_consumed'))==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        command=await db.scalar(select(StudioCommand).where(StudioCommand.operation=='start'))
        assert command.status=='dead' and command.attempts==0


@pytest.mark.parametrize('revoked',['none','gate','permission'])
async def test_cold_worker_replays_same_child_and_drains_buffered_cancel(
        client,identity,iteration_gates,temporal,monkeypatch,revoked):
    """Graceful worker replacement, not OS crash or Temporal server restart."""
    row,data=await eligible(client,identity);wf='p63-'+row['execution_id']
    await grants.issue_first_grant(data,wf)
    env,_=temporal;queue='p63-cold-trial-'+uuid4().hex
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',queue)
    trial_id='p63-grant-trial-'+row['execution_id']
    def fresh_worker():
        return Worker(env.client,task_queue=queue,workflows=[Trial,Child],
            activities=[grants.consume_trial_activity,durable.project_state],
            graceful_shutdown_timeout=timedelta(seconds=2))
    async with fresh_worker():
        parent=await env.client.start_workflow(Trial.run,data,id=trial_id,task_queue=queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        child=env.client.get_workflow_handle('p62-'+row['initial_proposal']['plan_id'])
        await waiting_child(child)
        before=await child.describe()
    # No worker is polling here. Temporal must persist the cancel until a new
    # Worker instance reconstructs both workflow states from history.
    if revoked=='gate':
        settings().goal_iterations_enabled=False
        settings().goal_admission_enabled=False
        settings().temporal_enabled=False
    elif revoked=='permission':
        async with Session.begin() as db:
            (await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    await parent.signal('request_cancel')
    async with fresh_worker():
        assert await asyncio.wait_for(parent.result(),25)=={
            'status':'cancelled','child_started':True,'dry_run':True}
    after=await child.describe()
    assert before.run_id==after.run_id
    parent_history=await parent.fetch_history();child_history=await child.fetch_history()
    assert sum(e.HasField('start_child_workflow_execution_initiated_event_attributes')
        for e in parent_history.events)==1
    assert sum(e.HasField('workflow_execution_started_event_attributes')
        for e in child_history.events)==1
    assert child_history.events[0].workflow_execution_started_event_attributes.parent_workflow_execution.workflow_id==trial_id
    await Replayer(workflows=[Trial]).replay_workflow(parent_history)
    await Replayer(workflows=[Child]).replay_workflow(child_history)
    with pytest.raises((ApplicationError,HTTPException)):
        await grants.consume_first_grant(data,wf,experiment_id=trial_id)
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='execution_grant_consumed'))==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        command=await db.scalar(select(StudioCommand).where(StudioCommand.operation=='start'))
        assert command.status=='dead' and command.attempts==0
