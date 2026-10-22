"""Leased Goal transport, DB regressions + real pre-child Temporal cancellation."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func
from temporalio.worker import Worker,Replayer
from pao.config import settings
from pao.db import Session
from pao.models import GoalCommand,GoalExecution,GoalEvent,StudioExecution,TaskAttempt,Member,now
from pao.modules.goals.dispatcher import GoalDispatcher,GoalGateway
from pao.modules.goals.projection import project_state
from test_goal_evidence import admitted
from test_goal_admission import goal_gates
from test_goal_temporal_kernel import temporal,GoalW


async def test_dispatch_start_concurrent_leased_and_default_denied(client,identity,goal_gates,monkeypatch):
    _,row,_=await admitted(client,identity)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    gateway=AsyncMock()
    assert await GoalDispatcher(gateway).dispatch()==0
    dispatcher=GoalDispatcher(gateway,allow_start=True)
    values=await asyncio.gather(*(dispatcher.dispatch() for _ in range(2)))
    assert sum(values)==1 and gateway.deliver.await_count==1
    async with Session() as db:
        item=await db.scalar(select(GoalCommand))
        assert item.status=='delivered' and item.attempts==1 and item.delivered_at and item.lease_token is None
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==0


async def test_retry_reclaims_expired_lease_and_cancel_survives_rollback(client,identity,goal_gates,monkeypatch):
    _,row,_=await admitted(client,identity)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    gateway=AsyncMock();gateway.deliver.side_effect=OSError('synthetic disconnect')
    dispatcher=GoalDispatcher(gateway,allow_start=True)
    assert await dispatcher.dispatch()==0
    async with Session.begin() as db:
        item=await db.scalar(select(GoalCommand));assert item.status=='pending' and item.attempts==1
        item.status='processing';item.lease_token=str(uuid4());item.lease_until=now()-timedelta(seconds=1)
        item.available_at=now()-timedelta(seconds=1)
    gateway.deliver.side_effect=None
    assert await dispatcher.dispatch()==1
    assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],
        json={'request_key':str(uuid4())})).status_code==200
    settings().goal_admission_enabled=False;settings().temporal_enabled=False
    assert await GoalDispatcher(gateway).dispatch()==1
    async with Session() as db:
        item=await db.scalar(select(GoalCommand).where(GoalCommand.operation=='cancel'))
        assert item.status=='delivered' and item.attempts==1


async def test_start_reauthorizes_without_transport(client,identity,goal_gates,monkeypatch):
    await admitted(client,identity)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    gateway=AsyncMock()
    assert await GoalDispatcher(gateway,allow_start=True).dispatch()==0
    gateway.deliver.assert_not_awaited()
    async with Session() as db:assert (await db.scalar(select(GoalCommand))).status=='dead'


async def test_real_parent_pre_child_cancel_outbox_replay(client,identity,goal_gates,temporal,monkeypatch):
    _,row,_=await admitted(client,identity)
    env,directory=temporal
    queue='p63-parent-dispatch-'+uuid4().hex
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',queue)
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    dispatcher=GoalDispatcher(GoalGateway(env.client),allow_start=True)
    assert await dispatcher.dispatch()==1
    handle=env.client.get_workflow_handle('p63-'+row['execution_id'])
    # Signal before starting worker: this is actual delivery, not a fixture ACK.
    key=str(uuid4())
    response=await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],
        json={'request_key':key})
    assert response.status_code==200
    settings().goal_admission_enabled=False;settings().temporal_enabled=False
    assert await dispatcher.dispatch()==1
    async with Worker(env.client,task_queue=queue,workflows=[GoalW],activities=[project_state],
            graceful_shutdown_timeout=timedelta(seconds=2)):
        result=await asyncio.wait_for(handle.result(),30)
    assert result['status']=='cancelled' and result['iteration']==0 and result['reserved_cost_microusd']==0
    async with Session() as db:
        commands=list(await db.scalars(select(GoalCommand)))
        assert len(commands)==2 and all(c.status=='delivered' and c.attempts==1 and c.delivered_at for c in commands)
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='cancelled' and saved.state==result and saved.cancel_requested
        for model in (StudioExecution,TaskAttempt):assert await db.scalar(select(func.count(model.id)))==0
    assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],
        json={'request_key':key})).status_code==200
    assert await dispatcher.dispatch()==0
    history=await handle.fetch_history()
    await Replayer(workflows=[GoalW]).replay_workflow(history)
    (directory/'parent-dispatch-cancel.json').write_text(history.to_json(),encoding='utf-8')


async def test_ack_lost_after_actual_start_retries_same_workflow(client,identity,goal_gates,temporal,monkeypatch):
    _,row,_=await admitted(client,identity)
    env,_=temporal
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue','p63-ack-lost-'+uuid4().hex)
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    real=GoalGateway(env.client)
    class LoseAck:
        first=True
        async def deliver(self,row,item):
            await real.deliver(row,item)
            if self.first:
                self.first=False
                raise OSError('synthetic lost ACK after successful network call')
    dispatcher=GoalDispatcher(LoseAck(),allow_start=True)
    assert await dispatcher.dispatch()==0
    async with Session.begin() as db:
        item=await db.scalar(select(GoalCommand));assert item.status=='pending' and item.attempts==1
        item.available_at=now()-timedelta(seconds=1)
    assert await dispatcher.dispatch()==1
    history=await env.client.get_workflow_handle('p63-'+row['execution_id']).fetch_history()
    assert sum(e.HasField('workflow_execution_started_event_attributes') for e in history.events)==1
    async with Session() as db:
        item=await db.scalar(select(GoalCommand));assert item.status=='delivered' and item.attempts==2


@pytest.mark.parametrize('operation',['start','cancel'])
async def test_real_workflow_collision_never_acknowledged(client,identity,goal_gates,temporal,monkeypatch,operation):
    _,row,_=await admitted(client,identity)
    env,_=temporal;queue='p63-collision-'+uuid4().hex
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',queue)
    monkeypatch.setattr(settings(),'temporal_namespace',env.client.namespace)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    bad={'envelope':row['envelope'],'initial_proposal':{**row['initial_proposal'],'cost_ceiling_microusd':6}}
    await env.client.start_workflow(GoalW.run,bad,id='p63-'+row['execution_id'],task_queue=queue)
    dispatcher=GoalDispatcher(GoalGateway(env.client),allow_start=True)
    assert await dispatcher.dispatch()==0
    if operation=='cancel':
        assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],
            json={'request_key':str(uuid4())})).status_code==200
        async with Session.begin() as db:
            item=await db.scalar(select(GoalCommand).where(GoalCommand.operation=='start'))
            item.available_at=now()-timedelta(seconds=1)
        assert await dispatcher.dispatch()==0
    async with Session() as db:
        item=await db.scalar(select(GoalCommand).where(GoalCommand.operation==operation))
        assert item.status=='pending' and item.delivered_at is None and item.error_code=='HTTPException'


async def test_old_dispatcher_cannot_ack_after_lease_owner_changed(client,identity,goal_gates,monkeypatch):
    await admitted(client,identity)
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    async def changed(row,item):
        async with Session.begin() as db:
            saved=await db.get(GoalCommand,item.id)
            saved.lease_token=str(uuid4())
    gateway=AsyncMock();gateway.deliver.side_effect=changed
    assert await GoalDispatcher(gateway,allow_start=True).dispatch()==0
    async with Session() as db:
        item=await db.scalar(select(GoalCommand))
        assert item.status=='processing' and item.delivered_at is None and item.lease_token
