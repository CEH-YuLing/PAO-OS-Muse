"""Real DB pre-child projections; no live goal dispatcher/worker acceptance."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from temporalio.exceptions import ApplicationError

from pao.config import settings
from pao.db import Session
from pao.models import GoalExecution, GoalCommand, GoalEvent, Member, now, StudioExecution, Run, TaskAttempt
from pao.modules.goals.control import GoalControl
from pao.modules.goals import projection
from test_goal_admission import goal_gates
from test_goal_evidence import admitted


async def fixture(client, identity):
    goal, row, body = await admitted(client, identity)
    # Explicit simulated dispatcher ACK; not a real Temporal transport test.
    async with Session.begin() as db:
        start = await db.scalar(select(GoalCommand).where(GoalCommand.execution_id==row['execution_id']))
        start.status='delivered'; start.attempts=1; start.delivered_at=now()
    stamp = int(now().timestamp()*1000)
    control = GoalControl(row['envelope'], stamp)
    state = {**control.propose(body['proposal'], stamp), 'sequence':1,
             'child_id':None, 'transport_reason':None}
    return row, {'envelope':row['envelope'], 'state':state}, control


async def test_atomic_concurrent_retry_and_actual_api_view(client, identity, goal_gates):
    row, data, control = await fixture(client, identity)
    results = await asyncio.gather(*(projection.project_pre_child(data, 'p63-'+row['execution_id']) for _ in range(2)))
    assert results == [{'allow_iteration':False,'cancel_requested':False}]*2
    response = await client.get('/v1/goal-executions/'+row['execution_id'], headers=identity['owner'])
    assert response.status_code == 200
    view = response.json()
    assert view['state'] == data['state'] and view['status'] == 'waiting_approval' and view['sequence'] == 1
    assert view['execution_enabled'] is False
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id))) == 3
        assert await db.scalar(select(func.count(GoalCommand.id))) == 1
        for model in (StudioExecution,Run,TaskAttempt):
            assert await db.scalar(select(func.count(model.id))) == 0
    retry = deepcopy(data); retry['state']['transport_reason'] = 'adapter_unavailable'
    with pytest.raises(ApplicationError, match='retry_conflict'):
        await projection.project_pre_child(retry, 'p63-'+row['execution_id'])


@pytest.mark.parametrize('field,value', [('sequence',True),('sequence',2),('iteration',1),
    ('cost_microusd',1),('cost_microusd',False),('iteration',False),
    ('reserved_cost_microusd',False),('reserved_cost_microusd',5),('model_executed',True),
    ('model_executed',0),('dry_run',1),
    ('dry_run',False),('status','completed'),('status','running'),('child_id','p62-fake'),
    ('proposal_hash','b'*64),('cancel_requested',True),('transport_reason','untrusted text')])
async def test_invalid_state_no_projection_write(client, identity, goal_gates, field, value):
    row, data, control = await fixture(client, identity)
    data['state'][field] = value
    with pytest.raises(ApplicationError):
        await projection.project_pre_child(data, 'p63-'+row['execution_id'])
    async with Session() as db:
        stored = await db.get(GoalExecution, row['execution_id'])
        assert stored.sequence == 0 and stored.status == 'starting'
        assert await db.scalar(select(func.count(GoalEvent.id))) == 2


async def test_wrong_workflow_or_envelope_scope(client, identity, goal_gates):
    row, data, control = await fixture(client, identity)
    with pytest.raises(ApplicationError, match='scope_invalid'):
        await projection.project_pre_child(data, 'p63-'+str(uuid4()))
    data['envelope'] = {**data['envelope'],'actor_id':str(uuid4())}
    with pytest.raises(ApplicationError, match='scope_invalid'):
        await projection.project_pre_child(data, 'p63-'+row['execution_id'])


async def test_cancel_api_request_survives_gate_off_and_retry(client, identity, goal_gates):
    row, data, control = await fixture(client, identity)
    await projection.project_pre_child(data, 'p63-'+row['execution_id'])
    settings().goal_admission_enabled = False
    response = await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',
        headers=identity['owner'], json={'request_key':str(uuid4())})
    assert response.status_code == 200 and response.json()['cancel_requested'] is True
    assert await projection.project_pre_child(data, 'p63-'+row['execution_id']) == {
        'allow_iteration':False,'cancel_requested':True}
    cancelled = {**control.cancel(int(now().timestamp()*1000)), 'sequence':2,
        'child_id':None, 'transport_reason':None}
    await projection.project_pre_child({'envelope':data['envelope'],'state':cancelled}, 'p63-'+row['execution_id'])
    async with Session() as db:
        stored = await db.get(GoalExecution,row['execution_id'])
        assert stored.status == 'cancelled' and stored.cancel_requested
        # No fabricated outbox delivery/ack: unresolved start/cancel remain.
        assert set(await db.scalars(select(GoalCommand.status))) == {'pending','delivered'}


async def test_permission_loss_can_project_safe_manual_review(client, identity, goal_gates):
    row, data, control = await fixture(client, identity)
    await projection.project_pre_child(data, 'p63-'+row['execution_id'])
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'],identity['user_id'])); member.role = 'viewer'
    assert (await projection.project_pre_child(data, 'p63-'+row['execution_id']))['allow_iteration'] is False
    manual = {**control.uncertain(int(now().timestamp()*1000)), 'sequence':2,
        'child_id':None,'transport_reason':'permission_or_gate_lost'}
    await projection.project_pre_child({'envelope':data['envelope'],'state':manual}, 'p63-'+row['execution_id'])
    async with Session() as db:
        stored = await db.get(GoalExecution,row['execution_id'])
        assert stored.status == 'manual_review'
        event = await db.scalar(select(GoalEvent).where(GoalEvent.action=='pre_child_projection').order_by(GoalEvent.created_at.desc()))
        assert event.data['permission_error'] is not None


async def test_activity_requires_temporal_origin(client, identity, goal_gates, monkeypatch):
    row, data, control = await fixture(client, identity)
    info = SimpleNamespace(workflow_type='PaoBoundedDryRunGoalWorkflow',
        workflow_namespace=settings().temporal_namespace,
        task_queue=settings().workflow_temporal_task_queue, workflow_id='p63-'+row['execution_id'])
    monkeypatch.setattr(projection.activity,'info',lambda:info)
    assert (await projection.project_state(data))['allow_iteration'] is False
    for field in ('workflow_type','workflow_namespace','task_queue','workflow_id'):
        prior = getattr(info,field); setattr(info,field,'untrusted')
        with pytest.raises(ApplicationError): await projection.project_state(data)
        setattr(info,field,prior)


async def test_undispatched_admission_cannot_accept_projection(client, identity, goal_gates):
    goal, row, body = await admitted(client, identity)
    stamp = int(now().timestamp()*1000)
    control = GoalControl(row['envelope'],stamp)
    state = {**control.propose(body['proposal'],stamp),'sequence':1,'child_id':None,'transport_reason':None}
    with pytest.raises(ApplicationError, match='start_not_dispatched'):
        await projection.project_pre_child({'envelope':row['envelope'],'state':state},'p63-'+row['execution_id'])


async def test_deadline_cannot_extend_on_new_sequence(client, identity, goal_gates):
    row, data, control = await fixture(client, identity)
    await projection.project_pre_child(data,'p63-'+row['execution_id'])
    changed=deepcopy(data); changed['state']['sequence']=2
    changed['state']['deadline_unix_ms']+=1
    with pytest.raises(ApplicationError, match='state_invalid'):
        await projection.project_pre_child(changed,'p63-'+row['execution_id'])
