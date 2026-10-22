"""Late-receipt DB reconciliation; parent/ACKs remain explicit fixtures."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from temporalio.exceptions import ApplicationError

from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,GoalCommand,TaskAttempt,Member,StudioExecution
from pao.modules.goals import recovery,iterations,first_projection as projection
from test_goal_admission import goal_gates
from test_goal_iterations import iteration_gates,completed,ready
from test_goal_first_projection import frame,controller


async def stopped(client,identity,monkeypatch,kind='manual_review',with_result=True,cancel=False):
    if with_result:row,data,child=await completed(client,identity)
    else:
        row,data=await ready(client,identity)
        await iterations.prepare_first(data,'p63-'+row['execution_id'])
    if cancel:
        assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],
            json={'request_key':str(uuid4())})).status_code==200
    c=controller(data);stamp=int(datetime.now(timezone.utc).timestamp()*1000)
    if cancel:c.cancel(stamp)
    if kind=='deadline_exceeded':
        stamp=data['state']['deadline_unix_ms'];state=c.advance(stamp)
        monkeypatch.setattr(projection,'now',lambda:datetime.fromtimestamp(stamp/1000,timezone.utc))
    else:state=c.uncertain(stamp)
    projected=frame({**data,'state':state});projected['state']['transport_reason']='child_drain_unknown'
    await projection.project_first(projected,'p63-'+row['execution_id'])
    return row,{'envelope':data['envelope']}


@pytest.mark.parametrize('kind,cancel',[('manual_review',False),('deadline_exceeded',False),('manual_review',True)])
async def test_concurrent_recovery_releases_once_never_resumes(client,identity,iteration_gates,monkeypatch,kind,cancel):
    row,data=await stopped(client,identity,monkeypatch,kind,cancel=cancel);ident='p63-'+row['execution_id']
    settings().goal_iterations_enabled=False;settings().goal_admission_enabled=False;settings().workflow_durable_enabled=False
    async with Session() as db:
        before=await db.get(GoalExecution,row['execution_id']);sequence=before.sequence;version=before.version
    results=await asyncio.gather(*(recovery.reconcile_completed_first(data,ident) for _ in range(2)))
    assert results[0]==results[1] and results[0]['status']==kind and results[0]['resumed'] is False
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status==kind and saved.reserved_cost_microusd==0 and saved.sequence==sequence
        assert saved.state['status']==kind and saved.state['reserved_cost_microusd']==0
        assert saved.state['checks']==[] and saved.version==version+1 and saved.cancel_requested==cancel
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='late_completion_reconciled'))==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==2
    assert (await client.get('/v1/goal-executions/'+row['execution_id'],headers=identity['owner'])).json()['state']['reserved_cost_microusd']==0


async def test_unknown_child_never_releases(client,identity,iteration_gates,monkeypatch):
    row,data=await stopped(client,identity,monkeypatch,with_result=False)
    with pytest.raises((ApplicationError,HTTPException)):
        await recovery.reconcile_completed_first(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action.in_(['late_completion_reconciled','iteration_receipt'])))==0


@pytest.mark.parametrize('kind',['permission','approval','state','reservation','attempt','child'])
async def test_recovery_fails_closed_after_corruption(client,identity,iteration_gates,monkeypatch,kind):
    row,data=await stopped(client,identity,monkeypatch)
    async with Session.begin() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        if kind=='permission':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif kind=='approval':(await db.scalar(select(GoalCommand).where(GoalCommand.operation=='decision'))).status='pending'
        elif kind=='state':saved.state={**saved.state,'receipt_hash':'b'*64}
        elif kind=='reservation':saved.reserved_cost_microusd=4
        elif kind=='attempt':(await db.scalar(select(TaskAttempt))).result={'output':{'text':'forged'}}
        else:(await db.scalar(select(StudioExecution))).status='cancelled'
    with pytest.raises((ApplicationError,HTTPException)):
        await recovery.reconcile_completed_first(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==(4 if kind=='reservation' else 5)
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='late_completion_reconciled'))==0


@pytest.mark.parametrize('kind',['extra','scope','workflow','iteration'])
async def test_closed_recovery_identity(client,identity,iteration_gates,monkeypatch,kind):
    row,data=await stopped(client,identity,monkeypatch);ident='p63-'+row['execution_id']
    bad=deepcopy(data)
    if kind=='extra':bad['receipt']={'text':'forged'}
    elif kind=='scope':bad['envelope']['workspace_id']=str(uuid4())
    elif kind=='workflow':ident='p63-'+str(uuid4())
    else:bad['envelope']['policy']['max_iterations']=20
    with pytest.raises((ApplicationError,HTTPException)):await recovery.reconcile_completed_first(bad,ident)


async def test_not_stopped_and_retry_projection_conflict(client,identity,iteration_gates,monkeypatch):
    row,data,child=await completed(client,identity);ident='p63-'+row['execution_id']
    with pytest.raises(ApplicationError,match='not_stopped'):
        await recovery.reconcile_completed_first({'envelope':data['envelope']},ident)
    c=controller(data);state=c.uncertain(int(datetime.now(timezone.utc).timestamp()*1000))
    await projection.project_first(frame({**data,'state':state}),ident)
    await recovery.reconcile_completed_first({'envelope':data['envelope']},ident)
    async with Session.begin() as db:
        saved=await db.get(GoalExecution,row['execution_id']);saved.state={**saved.state,'reason':'changed'}
    with pytest.raises(ApplicationError,match='retry_conflict'):
        await recovery.reconcile_completed_first({'envelope':data['envelope']},ident)


async def test_recovery_wrapper_wrong_origin(client,identity,iteration_gates,monkeypatch):
    row,data=await stopped(client,identity,monkeypatch)
    info=SimpleNamespace(workflow_type='untrusted',workflow_namespace=settings().temporal_namespace,
        task_queue=settings().workflow_temporal_task_queue,workflow_id='p63-'+row['execution_id'])
    monkeypatch.setattr(iterations.activity,'info',lambda:info)
    with pytest.raises(ApplicationError,match='origin_invalid'):
        await recovery.reconcile_completed_first_activity(data)
