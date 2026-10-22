import asyncio
from datetime import timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import StudioExecution,StudioCommand,StudioEvent,Member,now
from pao.modules.studio import durable
from test_workflow_planning import definitions,preview

BASE='/v1/studio'
@pytest.fixture
def gates(monkeypatch):
    for key in ('studio_enabled','workflow_planning_enabled','workflow_durable_enabled','workflow_dispatch_enabled','temporal_enabled'):
        monkeypatch.setattr(settings(),key,True)
    monkeypatch.setattr(durable.gateway,'deliver',AsyncMock())

async def plan(client,identity):
    workflow,_,_=await definitions(client,identity);base,body,response=await preview(client,identity,workflow)
    body['confirmation_hash']=response.json()['sha256']
    response=await client.post(base+'/plans',json=body,headers=identity['owner']);assert response.status_code==201,response.text
    return response.json()

async def start(client,identity,value,**changes):
    body={'request_key':str(uuid4()),'confirmation_hash':value['snapshot']['sha256']};body.update(changes)
    response=await client.post(BASE+'/plans/'+value['plan_id']+'/execution',json=body,headers=identity['owner'])
    return body,response

def state(value,sequence,status='waiting_approval',**updates):
    return {'plan_id':value['plan_id'],'snapshot_hash':value['snapshot']['sha256'],'sequence':sequence,
        'status':status,'current_step':'first','completed_steps':[],'cancel_requested':False,'reason':None,'dry_run':True,**updates}

async def test_admission_concurrent_idempotency_scope_and_frozen_tasks(client,identity,gates):
    value=await plan(client,identity);body={'request_key':str(uuid4()),'confirmation_hash':value['snapshot']['sha256']}
    url=BASE+'/plans/'+value['plan_id']+'/execution'
    result=await asyncio.gather(*(client.post(url,json=body,headers=identity['owner']) for _ in range(2)))
    assert all(r.status_code==202 for r in result),[r.text for r in result]
    assert result[0].json()['execution_id']==result[1].json()['execution_id']
    assert durable.gateway.deliver.await_count==0
    for actor,code in [('other',403),('outsider',404)]:
        assert (await client.post(url,json=body,headers=identity[actor])).status_code==code
    assert (await client.post(url,json={**body,'delay_seconds':1},headers=identity['owner'])).status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count(StudioExecution.id)))==1
        assert await db.scalar(select(func.count(StudioCommand.id)))==1
        row=await db.scalar(select(StudioExecution));assert row.command['steps'][0]['execution_id']==value['task_ids'][0]
    assert (await client.patch('/v1/tasks/'+value['task_ids'][0],json={'version':1,'status':'ready'},headers=identity['owner'])).status_code==409

async def test_projection_monotonic_dedup_terminal_and_decision_race(client,identity,gates):
    value=await plan(client,identity);_,response=await start(client,identity,value);assert response.status_code==202
    data=state(value,1);receipt=await durable.project_state(data)
    assert receipt==await durable.project_state(data)
    read=await client.get(BASE+'/executions/'+value['plan_id'],headers=identity['owner']);version=read.json()['version']
    decisions=await asyncio.gather(*(client.post(BASE+'/executions/'+value['plan_id']+'/decision',headers=identity['owner'],
        json={'request_key':str(uuid4()),'version':version,'step_id':'first','decision':d}) for d in ('approve','reject')))
    assert sorted(r.status_code for r in decisions)==[200,409]
    await durable.project_state(state(value,2,'cancelled',reason='rejected'))
    assert (await durable.project_state(state(value,3,'running')))['allow_next_step'] is False
    async with Session() as db:
        row=await db.get(StudioExecution,value['plan_id']);assert row.status=='cancelled' and row.sequence==2
        events=list(await db.scalars(select(StudioEvent).where(StudioEvent.action=='p62_projection')));assert len(events)==2

async def test_cancel_when_disabled_before_dispatch_is_atomic(client,identity,gates):
    value=await plan(client,identity);_,r=await start(client,identity,value);assert r.status_code==202
    settings().workflow_durable_enabled=False;settings().workflow_dispatch_enabled=False
    body={'request_key':str(uuid4())};url=BASE+'/executions/'+value['plan_id']+'/cancel'
    response=await client.post(url,json=body,headers=identity['owner']);assert response.status_code==200
    assert response.json()['status']=='cancelled'
    assert (await client.post(url,json=body,headers=identity['owner'])).status_code==200
    assert await durable.dispatch_commands()==0;durable.gateway.deliver.assert_not_awaited()
    async with Session() as db:
        commands=list(await db.scalars(select(StudioCommand).order_by(StudioCommand.ordinal)))
        assert [c.status for c in commands]==['dead','delivered']

async def test_retry_lease_reclaim_and_cancel_drain_off(client,identity,gates):
    value=await plan(client,identity);_,r=await start(client,identity,value);assert r.status_code==202
    durable.gateway.deliver.side_effect=RuntimeError('offline')
    assert await durable.dispatch_commands()==0
    async with Session.begin() as db:
        row=await db.scalar(select(StudioCommand));assert row.status=='pending' and row.attempts==1
        row.status='processing';row.lease_until=now()-timedelta(seconds=1);row.available_at=now()-timedelta(seconds=1);row.lease_token=str(uuid4())
    durable.gateway.deliver.side_effect=None
    assert await durable.dispatch_commands()==1
    assert await durable.dispatch_commands()==0
    settings().workflow_durable_enabled=False;settings().workflow_dispatch_enabled=False;settings().temporal_enabled=False
    response=await client.post(BASE+'/executions/'+value['plan_id']+'/cancel',headers=identity['owner'],json={'request_key':str(uuid4())})
    assert response.status_code==200 and response.json()['cancel_requested']
    assert await durable.dispatch_commands()==1
    assert durable.gateway.deliver.call_args.args[1].operation=='cancel'

async def test_permission_loss_fail_closed_and_identity_immutable(client,identity,gates):
    value=await plan(client,identity);_,r=await start(client,identity,value);assert r.status_code==202
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    assert await durable.dispatch_commands()==0;durable.gateway.deliver.assert_not_awaited()
    async with Session() as db:
        row=await db.get(StudioExecution,value['plan_id']);assert row.status=='manual_review'
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text("UPDATE studio_executions SET snapshot_hash=repeat('b',64)"))
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text("UPDATE studio_commands SET payload='{}'::json"))

async def test_projection_permission_loss_and_gap(client,identity,gates):
    value=await plan(client,identity);_,r=await start(client,identity,value);assert r.status_code==202
    from temporalio.exceptions import ApplicationError
    with pytest.raises(ApplicationError):await durable.project_state(state(value,2))
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    receipt=await durable.project_state(state(value,1,'running'));assert receipt['allow_next_step'] is False
    from fastapi import HTTPException
    with pytest.raises(HTTPException):await durable.authorize_step(value['plan_id'],'first',value['task_ids'][0])

async def test_disabled_and_bad_admission_no_execution(client,identity,gates):
    value=await plan(client,identity)
    _,r=await start(client,identity,value,confirmation_hash='b'*64);assert r.status_code==409
    _,r=await start(client,identity,value,request_key='invalid');assert r.status_code==422
    settings().workflow_durable_enabled=False
    _,r=await start(client,identity,value);assert r.status_code==503
    async with Session() as db:assert await db.scalar(select(func.count(StudioExecution.id)))==0
