"""First-iteration DB adapters. Dispatch/parent state are explicit fixtures.

Real P6.2 reserve/claim/finish produces immutable echo receipts; no goal worker,
Temporal dispatch, provider, model or business success acceptance is claimed.
"""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from temporalio.exceptions import ApplicationError

from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,GoalCommand,StudioExecution,StudioCommand,TaskAttempt,Run,Member,now
from pao.modules.goals import iterations,projection
from pao.modules.studio import durable,step_jobs as jobs
from test_goal_admission import goal_gates
from test_goal_projection import fixture as fixture_admission
from test_durable_admission import state


@pytest.fixture
def iteration_gates(monkeypatch,goal_gates):
    for key in ('goal_iterations_enabled','workflow_durable_enabled','temporal_enabled'):
        monkeypatch.setattr(settings(),key,True)


async def ready(client,identity,approve=True,delivered=True):
    row,data,control=await fixture_admission(client,identity)
    await projection.project_pre_child(data,'p63-'+row['execution_id'])
    view=(await client.get('/v1/goal-executions/'+row['execution_id'],headers=identity['owner'])).json()
    if approve:
        response=await client.post('/v1/goal-executions/'+row['execution_id']+'/decision',headers=identity['owner'],json={
            'request_key':str(uuid4()),'version':view['version'],
            'proposal_hash':data['state']['proposal_hash'],'decision':'approve'})
        assert response.status_code==200,response.text
        if delivered:
            async with Session.begin() as db:
                cmd=await db.scalar(select(GoalCommand).where(GoalCommand.execution_id==row['execution_id'],GoalCommand.operation=='decision'))
                cmd.status='delivered';cmd.attempts=1;cmd.delivered_at=now()
    running=control.decide(data['state']['proposal_hash'],'approve',int(now().timestamp()*1000))
    return row,{'envelope':data['envelope'],'state':running}


async def completed(client,identity):
    row,data=await ready(client,identity)
    command=await iterations.prepare_first(data,'p63-'+row['execution_id'])
    value={'plan_id':command['plan_id'],'snapshot':{'sha256':command['snapshot_hash']}}
    seq=0;done=[]
    for step in command['steps']:
        seq+=1
        await durable.project_state(state(value,seq,'waiting_approval',current_step=step['step_id'],completed_steps=done[:]))
        view=(await client.get('/v1/studio/executions/'+command['plan_id'],headers=identity['owner'])).json()
        response=await client.post('/v1/studio/executions/'+command['plan_id']+'/decision',headers=identity['owner'],json={
            'request_key':str(uuid4()),'version':view['version'],'step_id':step['step_id'],'decision':'approve'})
        assert response.status_code==200,response.text
        async with Session.begin() as db:
            item=await db.scalar(select(StudioCommand).where(StudioCommand.execution_id==command['plan_id'],
                StudioCommand.operation=='decision',StudioCommand.payload['step_id'].as_string()==step['step_id']))
            item.status='delivered';item.attempts=1;item.delivered_at=now()
        seq+=1
        await durable.project_state(state(value,seq,'running',current_step=step['step_id'],completed_steps=done[:]))
        args=(command['plan_id'],step['step_id'],step['execution_id'])
        await jobs.reserve(*args);claim=await jobs.claim(*args)
        assert claim['claimed'] is True
        assert (await jobs.finish(*args,claim['token'],claim['input']))['status']=='completed'
        done.append(step['step_id']);seq+=1
        await durable.project_state(state(value,seq,'step_completed',current_step=step['step_id'],completed_steps=done[:]))
    await durable.project_state(state(value,seq+1,'completed',current_step=None,completed_steps=done))
    return row,{**data,'child_result':{'status':'completed','output':{'text':'FORGED CHILD OUTPUT'}}},command


async def test_claim_concurrent_inert_child_and_reservation(client,identity,iteration_gates):
    row,data=await ready(client,identity)
    values=await asyncio.gather(*(iterations.prepare_first(data,'p63-'+row['execution_id']) for _ in range(2)))
    assert values[0]==values[1] and all(s['approval_required'] is True for s in values[0]['steps'])
    async with Session() as db:
        goal=await db.get(Goal,row['goal_id']);assert goal.status=='draft'
        execution=await db.get(GoalExecution,row['execution_id'])
        assert execution.status=='waiting_approval' and execution.reserved_cost_microusd==5
        assert await db.scalar(select(func.count(StudioExecution.id)))==1
        assert await db.scalar(select(func.count(GoalEvent.id)))==6
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert await db.scalar(select(func.count(Run.id)))==0
        start=await db.scalar(select(StudioCommand).where(StudioCommand.operation=='start'))
        assert start.status=='dead' and start.error_code=='goal_parent_owned_start' and start.delivered_at is None
    assert (await client.post('/v1/studio/plans/'+values[0]['plan_id']+'/execution',headers=identity['owner'],json={
        'request_key':str(uuid4()),'confirmation_hash':values[0]['snapshot_hash']})).status_code==409


@pytest.mark.parametrize('kind',['missing','undelivered','flag','cancel','permission'])
async def test_no_claim_without_current_authority_and_approval(client,identity,iteration_gates,kind):
    row,data=await ready(client,identity,approve=kind!='missing',delivered=kind!='undelivered')
    if kind=='flag':settings().goal_iterations_enabled=False
    if kind=='cancel':
        assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',headers=identity['owner'],json={
            'request_key':str(uuid4())})).status_code==200
    if kind=='permission':
        async with Session.begin() as db:
            member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    with pytest.raises((ApplicationError,HTTPException)):
        await iterations.prepare_first(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert await db.scalar(select(func.count(StudioExecution.id)))==0
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==0


@pytest.mark.parametrize('field,value',[('iteration',2),('iteration',True),('cost_microusd',False),
    ('reserved_cost_microusd',0),('model_executed',True),('deadline_unix_ms',253402300799000)])
async def test_changed_running_state_cannot_claim(client,identity,iteration_gates,field,value):
    row,data=await ready(client,identity)
    data['state'][field]=value
    with pytest.raises(ApplicationError):await iterations.prepare_first(data,'p63-'+row['execution_id'])


async def test_receipt_from_all_immutable_outcomes_not_child_output(client,identity,iteration_gates):
    row,data,command=await completed(client,identity)
    settings().goal_iterations_enabled=False;settings().goal_admission_enabled=False;settings().workflow_durable_enabled=False
    receipts=await asyncio.gather(*(iterations.read_first_receipt(data,'p63-'+row['execution_id']) for _ in range(2)))
    assert receipts[0]==receipts[1]
    receipt=receipts[0]
    assert receipt['output']=={'text':'Fixture planning'} and receipt['cost_microusd']==0 and receipt['origin']=='fixture_echo'
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='iteration_receipt'))==1
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        assert await db.scalar(select(func.count(TaskAttempt.id)))==2
    conflicting=deepcopy(data);conflicting['state']['proposal_hash']='b'*64
    with pytest.raises(ApplicationError):await iterations.read_first_receipt(conflicting,'p63-'+row['execution_id'])


async def test_missing_final_receipt_unknown_does_not_release_reserve(client,identity,iteration_gates):
    row,data=await ready(client,identity)
    await iterations.prepare_first(data,'p63-'+row['execution_id'])
    with pytest.raises(ApplicationError):
        await iterations.read_first_receipt({**data,'child_result':{'status':'completed','output':{'text':'made up'}}},'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='iteration_receipt'))==0


@pytest.mark.parametrize('kind',['attempt','child','approval','permission'])
async def test_receipt_rejects_mutable_projection_or_authority_change(client,identity,iteration_gates,kind):
    row,data,command=await completed(client,identity)
    async with Session.begin() as db:
        if kind=='attempt':
            attempt=await db.scalar(select(TaskAttempt));attempt.result={'output':{'text':'forged'}}
        elif kind=='child':
            child=await db.get(StudioExecution,command['plan_id']);child.status='manual_review'
        elif kind=='approval':
            item=await db.scalar(select(StudioCommand).where(StudioCommand.operation=='decision'));item.status='pending'
        else:
            member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    with pytest.raises((ApplicationError,HTTPException)):
        await iterations.read_first_receipt(data,'p63-'+row['execution_id'])
    async with Session() as db:
        assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='iteration_receipt'))==0


async def test_wrappers_reject_wrong_temporal_origin(client,identity,iteration_gates,monkeypatch):
    from types import SimpleNamespace
    row,data=await ready(client,identity)
    info=SimpleNamespace(workflow_type='untrusted',workflow_namespace=settings().temporal_namespace,
        task_queue=settings().workflow_temporal_task_queue,workflow_id='p63-'+row['execution_id'])
    monkeypatch.setattr(iterations.activity,'info',lambda:info)
    with pytest.raises(ApplicationError,match='origin_invalid'):
        await iterations.prepare_iteration(data)
    with pytest.raises(ApplicationError,match='origin_invalid'):
        await iterations.read_receipt({**data,'child_result':{'status':'completed'}})
