"""Opt-in Temporal -> real DB projection, NOT a goal executor acceptance.

Dispatcher ACK remains an explicit fixture. No child, model or provider calls.
"""
import asyncio
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, func
from temporalio.worker import Worker

from pao.config import settings, ROOT
from pao.db import Session
from pao.models import GoalExecution, GoalEvent, StudioExecution, TaskAttempt, Run
from pao.modules.goals.projection import project_state
from test_goal_projection import fixture as admitted_fixture
from test_goal_admission import goal_gates
from test_goal_temporal_kernel import temporal, GoalW, replay


async def test_real_temporal_pre_child_db_boundary(client, identity, goal_gates, temporal, monkeypatch):
    row, data, control = await admitted_fixture(client, identity)
    env, _ = temporal
    queue = 'p63-pre-child-'+uuid4().hex
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',queue)
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    async with Worker(env.client, task_queue=queue, workflows=[GoalW],
            activities=[project_state], graceful_shutdown_timeout=timedelta(seconds=2)):
        handle = await env.client.start_workflow(GoalW.run, {
            'envelope':row['envelope'],'initial_proposal':row['initial_proposal']},
            id='p63-'+row['execution_id'],task_queue=queue)
        result = await asyncio.wait_for(handle.result(),30)
    assert result['status']=='manual_review' and result['iteration']==0
    assert result['reserved_cost_microusd']==0 and result['model_executed'] is False
    history = await handle.fetch_history()
    activities = [e.activity_task_scheduled_event_attributes.activity_type.name
        for e in history.events if e.HasField('activity_task_scheduled_event_attributes')]
    assert activities == ['p63_project','p63_project']
    assert not any(e.HasField('start_child_workflow_execution_initiated_event_attributes') for e in history.events)
    async with Session() as db:
        stored = await db.get(GoalExecution,row['execution_id'])
        assert stored.status=='manual_review' and stored.sequence==2 and stored.state==result
        assert await db.scalar(select(func.count(GoalEvent.id)))==4
        for model in (StudioExecution,TaskAttempt,Run):
            assert await db.scalar(select(func.count(model.id)))==0
    directory=ROOT/'.runtime'/('p63b2b2a-temporal-'+uuid4().hex)
    directory.mkdir()
    await replay(handle,directory,'pre-child-db')
