import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import ResultInboxReceipt,ResultDelivery,StudioExecution,Member
from pao.modules.studio import durable
from test_durable_admission import gates,plan,start,state


async def terminal(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'result_inbox_enabled',True)
    value=await plan(client,identity);_,r=await start(client,identity,value)
    assert r.status_code==202
    await durable.project_state(state(value,1,'cancelled',reason='rejected'))
    return value


async def test_inbox_receipts_are_per_user_idempotent(client,identity,gates,monkeypatch):
    value=await terminal(client,identity,monkeypatch)
    url='/v1/results?workspace_id='+identity['workspace']
    rows=(await client.get(url,headers=identity['owner'])).json()
    assert len(rows)==1 and rows[0]['read'] is False and rows[0]['business_success_proven'] is False
    receipt='/v1/results/'+value['plan_id']+'/receipt'
    body={'source_hash':rows[0]['source_hash'],'action':'ack'}
    responses=await asyncio.gather(*(client.post(receipt,headers=identity['owner'],json=body) for _ in range(2)))
    assert all(r.status_code==200 and r.json()['acknowledged'] for r in responses)
    assert (await client.get(url,headers=identity['owner'])).json()[0]['acknowledged'] is True
    assert (await client.get(url,headers=identity['other'])).json()[0]['read'] is False
    assert (await client.get(url,headers=identity['outsider'])).status_code==404
    async with Session() as db:assert await db.scalar(select(func.count(ResultInboxReceipt.id)))==1


async def test_bad_hash_and_fake_source_rejected(client,identity,gates,monkeypatch):
    value=await terminal(client,identity,monkeypatch)
    url='/v1/results/'+value['plan_id']+'/receipt'
    assert (await client.post(url,headers=identity['owner'],json={'source_hash':'0'*64,'action':'ack'})).status_code==409
    async with Session.begin() as db:
        row=await db.get(StudioExecution,value['plan_id']);row.state={**row.state,'reason':'tampered'}
    assert (await client.get('/v1/results?workspace_id='+identity['workspace'],headers=identity['owner'])).status_code==409


async def test_delivery_dedup_membership_and_no_external_send(client,identity,gates,monkeypatch):
    value=await terminal(client,identity,monkeypatch)
    item=(await client.get('/v1/results?workspace_id='+identity['workspace'],headers=identity['owner'])).json()[0]
    url='/v1/results/'+value['plan_id']+'/deliveries'
    body={'source_hash':item['source_hash'],'recipient_id':identity['user_id'],'destination':'in_app'}
    responses=await asyncio.gather(*(client.post(url,headers=identity['owner'],json=body) for _ in range(2)))
    assert all(r.status_code==200 and r.json()['external_send'] is False for r in responses)
    assert responses[0].json()['id']==responses[1].json()['id']
    assert (await client.post(url,headers=identity['owner'],json={**body,'recipient_id':str(uuid4())})).status_code==404
    assert (await client.post(url,headers=identity['owner'],json={**body,'destination':'telegram'})).status_code==422
    async with Session.begin() as db:
        (await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    assert (await client.post(url,headers=identity['owner'],json=body)).status_code==403
    async with Session() as db:
        assert await db.scalar(select(func.count(ResultDelivery.id)))==1
        assert await db.scalar(select(func.count(ResultInboxReceipt.id)))==0


async def test_disabled_has_no_mutation(client,identity):
    assert (await client.get('/v1/results/status?workspace_id='+identity['workspace'],headers=identity['owner'])).json()['enabled'] is False
    assert (await client.get('/v1/results?workspace_id='+identity['workspace'],headers=identity['owner'])).status_code==409
