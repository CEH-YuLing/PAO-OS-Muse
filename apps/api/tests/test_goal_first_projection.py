"""DB ledger projection, not live goal execution. Parent/ACKs are fixtures."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select,func
from temporalio.exceptions import ApplicationError
from fastapi import HTTPException

from pao.config import settings
from pao.db import Session
from pao.models import Goal,GoalExecution,GoalEvent,GoalCommand,Member,TaskAttempt
from pao.modules.goals import iterations,first_projection as projection,projection as pre_child
from pao.modules.goals.control import GoalControl
from test_goal_iterations import ready,completed,iteration_gates
from test_goal_admission import goal_gates


def frame(data,sequence=2,child=True):
    return {'envelope':data['envelope'],'state':{**data['state'],'sequence':sequence,
        'child_id':'p62-'+data['state']['proposal']['plan_id'] if child else None,'transport_reason':None}}


def controller(data):
    s=data['state'];start=max(0,s['deadline_unix_ms']-data['envelope']['policy']['max_elapsed_seconds']*1000)
    c=GoalControl(data['envelope'],start);c.propose(s['proposal'],start)
    c.decide(s['proposal_hash'],'approve',start)
    return c


async def test_atomic_running_completion_idempotent_releases_once_not_m1(client,identity,iteration_gates):
    row,data,child=await completed(client,identity)
    ident='p63-'+row['execution_id'];running=frame(data,child=False)
    results=await asyncio.gather(*(projection.project_first(running,ident) for _ in range(2)))
    assert results==[{'allow_iteration':False,'cancel_requested':False}]*2
    receipt=await iterations.read_first_receipt(data,ident)
    c=controller(data);done=c.finish(receipt,int(datetime.now(timezone.utc).timestamp()*1000))
    final=frame({**data,'state':done},3)
    # Gate rollback must not block safe, reauthorized receipt reconciliation.
    settings().goal_iterations_enabled=False;settings().goal_admission_enabled=False
    results=await asyncio.gather(*(projection.project_first(final,ident) for _ in range(2)))
    assert results==[{'allow_iteration':False,'cancel_requested':False}]*2
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='completed' and saved.reserved_cost_microusd==0 and saved.sequence==3
        assert saved.state==final['state'] and saved.state['checks'][0]['passed'] is True
        assert (await db.get(Goal,row['goal_id'])).status=='draft'
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='first_iteration_projection'))==2
        assert await db.scalar(select(func.count(TaskAttempt.id)))==2
        version=saved.version
    assert (await client.get('/v1/goal-executions/'+row['execution_id'],headers=identity['owner'])).json()['state']==final['state']
    await projection.project_first(final,ident)
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).version==version
    altered=deepcopy(final);altered['state']['checks'][0]['passed']=False
    with pytest.raises(ApplicationError,match='retry_conflict'):await projection.project_first(altered,ident)


@pytest.mark.parametrize('field,value',[('iteration',True),('iteration',2),('sequence',True),
    ('sequence',3),('reserved_cost_microusd',0),('cost_microusd',1),('cost_microusd',False),
    ('deadline_unix_ms',253402300799000),('child_id','p62-forged'),('cancel_requested',True),
    ('checks',[{'field':'text','rule':'equals','passed':True}]),('model_executed',True)])
async def test_fabricated_projection_keeps_reserve(client,identity,iteration_gates,field,value):
    row,data=await ready(client,identity)
    await iterations.prepare_first(data,'p63-'+row['execution_id'])
    bad=frame(data);bad['state'][field]=value
    with pytest.raises(ApplicationError):await projection.project_first(bad,'p63-'+row['execution_id'])
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.sequence==1 and saved.reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='first_iteration_projection'))==0


async def test_receipt_required_before_success(client,identity,iteration_gates):
    row,data,child=await completed(client,identity)
    fake={'execution_id':row['execution_id'],'iteration':1,'proposal_hash':data['state']['proposal_hash'],
        'output':{'text':'Fixture planning'},'cost_microusd':0,'dry_run':True,'origin':'fixture_echo'}
    c=controller(data);done=c.finish(fake,int(datetime.now(timezone.utc).timestamp()*1000))
    with pytest.raises(ApplicationError,match='receipt_missing'):
        await projection.project_first(frame({**data,'state':done}),'p63-'+row['execution_id'])
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


@pytest.mark.parametrize('kind',['permission','approval','ledger','receipt_hash','attempt'])
async def test_rechecks_authority_evidence_and_mutable_ledger(client,identity,iteration_gates,kind):
    row,data,child=await completed(client,identity)
    ident='p63-'+row['execution_id'];receipt=await iterations.read_first_receipt(data,ident)
    c=controller(data);done=c.finish(receipt,int(datetime.now(timezone.utc).timestamp()*1000))
    bad=frame({**data,'state':done})
    async with Session.begin() as db:
        if kind=='permission':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif kind=='approval':
            cmd=await db.scalar(select(GoalCommand).where(GoalCommand.operation=='decision'));cmd.status='pending'
        elif kind=='ledger':
            saved=await db.get(GoalExecution,row['execution_id']);saved.state={**saved.state,'proposal_hash':'b'*64}
        elif kind=='attempt':
            (await db.scalar(select(TaskAttempt))).result={'output':{'text':'forged after receipt'}}
        else:bad['state']['receipt_hash']='b'*64
    with pytest.raises((ApplicationError,HTTPException)):await projection.project_first(bad,ident)
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


async def test_unknown_authority_loss_hold_and_no_cancel_ack_without_receipt(client,identity,iteration_gates):
    row,data=await ready(client,identity);ident='p63-'+row['execution_id']
    await iterations.prepare_first(data,ident)
    async with Session.begin() as db:
        (await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    c=controller(data);unknown=c.uncertain(int(datetime.now(timezone.utc).timestamp()*1000))
    pending=frame({**data,'state':unknown});pending['state']['transport_reason']='permission_or_gate_lost'
    result=await projection.project_first(pending,ident)
    assert result['allow_iteration'] is False
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='manual_review' and saved.reserved_cost_microusd==5
    # Terminal uncertainty cannot be changed into completion by a later projection.
    with pytest.raises(ApplicationError):await projection.project_first(frame(data,3),ident)


async def test_wrapper_metadata_and_first_projection_route(client,identity,iteration_gates,monkeypatch):
    row,data=await ready(client,identity);ident='p63-'+row['execution_id']
    await iterations.prepare_first(data,ident)
    info=SimpleNamespace(workflow_type='PaoBoundedDryRunGoalWorkflow',
        workflow_namespace=settings().temporal_namespace,task_queue=settings().workflow_temporal_task_queue,workflow_id=ident)
    monkeypatch.setattr(pre_child.activity,'info',lambda:info)
    assert (await pre_child.project_state(frame(data)))['allow_iteration'] is False
    info.workflow_type='untrusted'
    with pytest.raises(ApplicationError,match='origin_invalid'):await pre_child.project_state(frame(data))


async def test_deadline_keeps_reservation(client,identity,iteration_gates,monkeypatch):
    row,data=await ready(client,identity);ident='p63-'+row['execution_id']
    await iterations.prepare_first(data,ident)
    c=controller(data);deadline=data['state']['deadline_unix_ms']
    expired=c.advance(deadline)
    monkeypatch.setattr(projection,'now',lambda:datetime.fromtimestamp(deadline/1000,timezone.utc))
    assert (await projection.project_first(frame({**data,'state':expired}),ident))['allow_iteration'] is False
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='deadline_exceeded' and saved.reserved_cost_microusd==5


async def test_cancel_ack_requires_verified_child_receipt(client,identity,iteration_gates):
    row,data,child=await completed(client,identity);ident='p63-'+row['execution_id']
    assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',
        headers=identity['owner'],json={'request_key':str(uuid4())})).status_code==200
    receipt=await iterations.read_first_receipt(data,ident)
    c=controller(data);stamp=int(datetime.now(timezone.utc).timestamp()*1000)
    c.cancel(stamp);done=c.finish(receipt,stamp)
    assert done['status']=='cancelled' and done['reason']=='cancel_acknowledged'
    assert (await projection.project_first(frame({**data,'state':done}),ident))['cancel_requested'] is True
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='cancelled' and saved.reserved_cost_microusd==0
        assert (await db.get(Goal,row['goal_id'])).status=='draft'


async def test_missing_claim_and_disabled_running_are_rejected(client,identity,iteration_gates):
    row,data=await ready(client,identity);ident='p63-'+row['execution_id']
    with pytest.raises(ApplicationError,match='claim_missing'):await projection.project_first(frame(data),ident)
    await iterations.prepare_first(data,ident)
    settings().goal_iterations_enabled=False
    with pytest.raises(ApplicationError):await projection.project_first(frame(data),ident)
    async with Session() as db:assert (await db.get(GoalExecution,row['execution_id'])).reserved_cost_microusd==5


@pytest.mark.parametrize('limit,expected',[(2,'waiting_replan'),(1,'budget_exhausted')])
async def test_unmet_criteria_and_iteration_budget_from_receipt(client,identity,iteration_gates,monkeypatch,limit,expected):
    import test_goal_evidence as evidence_fixture
    original=evidence_fixture.draft
    async def custom(client,identity):
        goal,plan,url,body=await original(client,identity)
        draft={k:v for k,v in body.items() if k!='confirmation_hash'}
        draft['success_criteria']=[{'field':'text','rule':'equals','value':'Does not match echo'}]
        draft['policy']={**draft['policy'],'max_iterations':limit}
        preview=await client.post('/v1/goals/'+goal['id']+'/dry-run-admission-preview',headers=identity['owner'],json=draft)
        assert preview.status_code==200
        return goal,plan,url,{**draft,'confirmation_hash':preview.json()['confirmation_hash']}
    monkeypatch.setattr(evidence_fixture,'draft',custom)
    row,data,child=await completed(client,identity);ident='p63-'+row['execution_id']
    receipt=await iterations.read_first_receipt(data,ident)
    c=controller(data);done=c.finish(receipt,int(datetime.now(timezone.utc).timestamp()*1000))
    assert done['status']==expected
    await projection.project_first(frame({**data,'state':done}),ident)
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status==expected and saved.reserved_cost_microusd==0
        assert saved.state['checks'][0]['passed'] is False
        assert (await db.get(Goal,row['goal_id'])).status=='draft'


async def test_cancel_without_completion_is_unknown_and_holds_reserve(client,identity,iteration_gates):
    row,data=await ready(client,identity);ident='p63-'+row['execution_id']
    await iterations.prepare_first(data,ident)
    assert (await client.post('/v1/goal-executions/'+row['execution_id']+'/cancel',
        headers=identity['owner'],json={'request_key':str(uuid4())})).status_code==200
    c=controller(data);stamp=int(datetime.now(timezone.utc).timestamp()*1000)
    c.cancel(stamp);unknown=c.uncertain(stamp)
    pending=frame({**data,'state':unknown});pending['state']['transport_reason']='child_drain_unknown'
    assert (await projection.project_first(pending,ident))['cancel_requested'] is True
    async with Session() as db:
        saved=await db.get(GoalExecution,row['execution_id'])
        assert saved.status=='manual_review' and saved.reserved_cost_microusd==5
        assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='iteration_receipt'))==0
