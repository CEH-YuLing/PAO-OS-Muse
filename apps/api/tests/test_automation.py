import asyncio
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from sqlalchemy import func,select
from pao.automation import dispatch_automation,gateway,project_workflow
from pao.config import settings
from pao.db import Session
from pao.models import AutomationOutbox,AutomationWorkflow,AutomationWorkflowAudit

BASE='/v1/automation'

@pytest.fixture
def temporal(monkeypatch):
    monkeypatch.setattr(settings(),'temporal_enabled',True)
    monkeypatch.setattr(gateway,'start',AsyncMock(return_value='temporal-run-1'))
    monkeypatch.setattr(gateway,'signal',AsyncMock())

async def test_status_is_fail_closed(client,monkeypatch):
    monkeypatch.setattr(settings(),'temporal_enabled',False)
    assert (await client.get(BASE+'/status')).json()['enabled'] is False

async def test_operator_starts_owner_approves_versioned_workflow(client,identity,temporal):
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'approval_wait','payload':{'task':'review report'},'approval_required':True}
    made=await client.post(BASE+'/workflows',json=body,headers=identity['other']);assert made.status_code==202
    row=made.json();assert row['status']=='starting' and row['approval_status']=='pending'
    assert await dispatch_automation({})==1
    current=await client.get(f"{BASE}/workflows/{row['id']}",headers=identity['owner'])
    assert current.json()['status']=='waiting_approval'
    assert (await client.post(f"{BASE}/workflows/{row['id']}/decision",json={'version':1,'decision':'approve'},headers=identity['other'])).status_code==403
    approved=await client.post(f"{BASE}/workflows/{row['id']}/decision",json={'version':1,'decision':'approve'},headers=identity['owner']);assert approved.status_code==200
    assert approved.json()['approval_status']=='approved' and approved.json()['version']==2
    assert (await client.post(f"{BASE}/workflows/{row['id']}/decision",json={'version':1,'decision':'approve'},headers=identity['owner'])).status_code==409
    gateway.signal.assert_not_awaited();assert await dispatch_automation({})==1;gateway.signal.assert_awaited_once()
    async with Session() as db: assert await db.scalar(select(func.count()).select_from(AutomationWorkflowAudit))==2

async def test_idempotency_scope_cancel_and_projection(client,identity,temporal):
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'follow_up','payload':{'subject':'daily check'},'approval_required':False,
          'wait_until':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    first=await client.post(BASE+'/workflows',json=body,headers=identity['owner']);second=await client.post(BASE+'/workflows',json=body,headers=identity['owner'])
    assert first.status_code==202 and second.json()['id']==first.json()['id'];assert gateway.start.await_count==0
    assert await dispatch_automation({})==1;assert gateway.start.await_count==1
    assert (await client.get(BASE+'/workflows',params={'workspace_id':identity['workspace']},headers=identity['outsider'])).status_code==404
    row=first.json();cancelled=await client.post(f"{BASE}/workflows/{row['id']}/cancel",headers=identity['owner']);assert cancelled.json()['status']=='cancelled'
    await project_workflow({'id':row['id'],'status':'completed','result':{'should':'not overwrite'}})
    async with Session() as db:
        saved=await db.get(AutomationWorkflow,row['id']);assert saved.status=='cancelled' and saved.result=={}

async def test_temporal_unavailable_keeps_committed_command_for_retry(client,identity,temporal):
    gateway.start.side_effect=RuntimeError('offline')
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'approval_wait','payload':{}}
    response=await client.post(BASE+'/workflows',json=body,headers=identity['owner'])
    assert response.status_code==202 and response.json()['status']=='starting'
    assert await dispatch_automation({})==0
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AutomationWorkflow))==1
        outbox=await db.scalar(select(AutomationOutbox));assert outbox.status=='pending' and outbox.attempts==1


async def test_request_key_fingerprint_covers_all_execution_options(client,identity,temporal):
    key=str(uuid4())
    body={'workspace_id':identity['workspace'],'request_key':key,'kind':'approval_wait','payload':{'x':1},
          'approval_required':True,'approval_timeout_hours':24}
    assert (await client.post(BASE+'/workflows',json=body,headers=identity['owner'])).status_code==202
    changed={**body,'approval_timeout_hours':48}
    assert (await client.post(BASE+'/workflows',json=changed,headers=identity['owner'])).status_code==409
    changed={**body,'approval_required':False}
    assert (await client.post(BASE+'/workflows',json=changed,headers=identity['owner'])).status_code==409


async def test_concurrent_decisions_accept_exactly_one(client,identity,temporal):
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'approval_wait','payload':{}}
    made=await client.post(BASE+'/workflows',json=body,headers=identity['owner'])
    assert await dispatch_automation({})==1
    workflow_id=made.json()['id']
    responses=await asyncio.gather(
        client.post(f'{BASE}/workflows/{workflow_id}/decision',json={'version':1,'decision':'approve'},headers=identity['owner']),
        client.post(f'{BASE}/workflows/{workflow_id}/decision',json={'version':1,'decision':'reject'},headers=identity['owner']),
    )
    assert sorted(response.status_code for response in responses)==[200,409]
    async with Session() as db:
        signals=await db.scalar(select(func.count()).select_from(AutomationOutbox).where(AutomationOutbox.operation=='signal'))
        assert signals==1


async def test_concurrent_identical_starts_share_one_workflow(client,identity,temporal):
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'follow_up',
          'payload':{'subject':'one durable command'},'approval_required':False}
    responses=await asyncio.gather(
        client.post(BASE+'/workflows',json=body,headers=identity['owner']),
        client.post(BASE+'/workflows',json=body,headers=identity['owner']),
    )
    assert [response.status_code for response in responses]==[202,202]
    assert len({response.json()['id'] for response in responses})==1
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AutomationWorkflow))==1
        assert await db.scalar(select(func.count()).select_from(AutomationOutbox))==1


async def test_dispatch_recovers_expired_worker_lease(client,identity,temporal):
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'follow_up',
          'payload':{},'approval_required':False}
    made=await client.post(BASE+'/workflows',json=body,headers=identity['owner'])
    async with Session.begin() as db:
        item=await db.scalar(select(AutomationOutbox).with_for_update())
        item.status='processing';item.attempts=1
        item.locked_at=datetime.now(timezone.utc)-timedelta(minutes=3)
    assert await dispatch_automation({})==1
    async with Session() as db:
        item=await db.scalar(select(AutomationOutbox))
        row=await db.get(AutomationWorkflow,made.json()['id'])
        assert item.status=='delivered' and item.attempts==2
        assert row.status=='running' and row.temporal_run_id=='temporal-run-1'
