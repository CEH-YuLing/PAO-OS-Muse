import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

import pao.ads_actions as action_service
from pao.ads_actions import dispatch_actions,execute_action
from pao.config import settings
from pao.db import Session
from pao.integrations.meta.client import MetaClient,MetaError
from pao.main import app
from pao.models import AdAction,AdEntity,Member,MetaConnection,MetaSyncJob,now
from test_meta import connected,meta


class FakeMeta:
    def __init__(self):
        self.states={'10':{'id':'10','account_id':'1','name':'Campaign 10','status':'ACTIVE','effective_status':'ACTIVE','daily_budget':'10000'},
            '20':{'id':'20','account_id':'1','name':'Adset 20','status':'ACTIVE','effective_status':'ACTIVE','daily_budget':'10000'}}
        self.writes=[];self.failure=None
    async def resource(self,resource_type,resource_id,account_id):return dict(self.states[resource_id])
    async def write_resource(self,resource_id,payload):
        self.writes.append((resource_id,payload))
        if self.failure:raise MetaError(self.failure)
        for key,value in payload.items():self.states[resource_id][key]=str(value) if key=='daily_budget' else value
        return {'success':True}


@pytest.fixture
async def write_setup(identity,meta,monkeypatch):
    monkeypatch.setattr(settings(),'meta_write_enabled',True);monkeypatch.setattr(settings(),'meta_write_max_budget_change_pct',20)
    monkeypatch.setattr(settings(),'ads_approval_ttl_hours',24)
    cid=await connected(identity)
    async with Session.begin() as db:
        conn=await db.get(MetaConnection,cid);conn.scopes=['ads_read','ads_management']
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='historical',
            account_id='act_1',since='2026-01-01',until='2026-01-01',status='completed',warehouse=True,granularity='daily')
        db.add(job);await db.flush()
        common=dict(connection_id=cid,connection_version=1,account_id='act_1',currency='VND',timezone='Asia/Ho_Chi_Minh',source_job_id=job.id)
        db.add_all([AdEntity(**common,kind='account',remote_id='act_1',name='Write QA'),
            AdEntity(**common,kind='campaign',remote_id='10',name='Campaign 10',parent_id='act_1'),
            AdEntity(**common,kind='adset',remote_id='20',name='Adset 20',parent_id='10')])
    fake=FakeMeta();monkeypatch.setattr(action_service,'MetaClient',lambda token:fake)
    return fake,cid


def proposal(identity,**changes):
    data={'workspace_id':identity['workspace'],'account_id':'act_1','resource_type':'campaign','resource_id':'10',
        'action_type':'pause','budget_minor_units':None,'reason':'Performance review requested by owner','confidence':'0.9',
        'source_agent':'user','recommendation_id':None,'dry_run':True,'request_key':str(uuid4())}
    return {**data,**changes}


async def approve(client,identity,action,headers=None):
    return await client.post(f"/v1/approvals/{action['id']}/approve",json={'version':action['version']},headers=headers or identity['owner'])


async def run_action(action_id):await execute_action({'redis':app.state.redis},action_id)


async def get_approval(client,identity,action_id):return await client.get(f'/v1/approvals/{action_id}',headers=identity['owner'])


async def test_write_status_scope_and_oauth(client,identity,write_setup):
    status=await client.get('/v1/ads/write-status',headers=identity['owner'])
    assert status.json()=={'enabled':True,'mode':'copilot','dry_run_default':True,'formal_approval_phase':12,'max_budget_change_pct':20}
    assert (await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['other'])).status_code==403
    assert (await client.get('/v1/approvals',params={'workspace_id':identity['workspace']},headers=identity['outsider'])).status_code==404
    oauth=await client.post('/v1/integrations/meta/oauth/start',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert 'scope=ads_read%2Cads_management' in oauth.json()['authorization_url']


async def test_ui_approval_queue_execution_idempotency_and_audit(client,identity,write_setup):
    fake,_=write_setup;body=proposal(identity);made=await client.post('/v1/ads/actions',json=body,headers=identity['owner'])
    assert made.status_code==201,made.text
    action=made.json()['action']
    assert action['before_state']['status']=='ACTIVE' and action['proposed_state']=={'status':'PAUSED'}
    assert action['execution_status']=='pending' and action['approval_status']=='pending' and action['dry_run']
    repeated=await client.post('/v1/ads/actions',json=body,headers=identity['owner'])
    assert repeated.json()['action']['id']==action['id']
    assert (await client.post('/v1/ads/actions',json={**body,'reason':'A materially different reason'},headers=identity['owner'])).status_code==409
    assert (await approve(client,identity,{**action,'version':99})).status_code==409
    queued=await approve(client,identity,action);assert queued.status_code==200
    assert queued.json()['action']['approval_status']=='approved' and queued.json()['action']['execution_status']=='queued' and fake.writes==[]
    await run_action(action['id']);result=(await get_approval(client,identity,action['id'])).json()
    assert result['action']['execution_status']=='simulated' and result['action']['after_state']['simulated']
    assert result['action']['approved_by']==identity['user_id'] and result['action']['decision_channel']=='ui' and fake.writes==[]
    assert [row['event'] for row in result['audit']]==['action.proposed','approval.approve','action.started','action.simulated']
    again=await approve(client,identity,action);assert again.json()['action']['execution_status']=='simulated' and fake.writes==[]


async def test_admin_can_approve_another_users_action_and_operator_cannot(client,identity,write_setup):
    action=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    denied=await approve(client,identity,action,identity['other']);assert denied.status_code==404
    async with Session.begin() as db:
        other_id=await db.scalar(select(Member.user_id).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        member=await db.get(Member,(identity['workspace'],other_id));member.role='admin'
    approved=await approve(client,identity,action,identity['other'])
    assert approved.status_code==200 and approved.json()['action']['approval_status']=='approved'


async def test_reject_and_expiry_never_execute(client,identity,write_setup):
    fake,cid=write_setup
    first=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    async with Session.begin() as db:
        conn=await db.get(MetaConnection,cid);conn.status='revoked'
    rejected=await client.post(f"/v1/approvals/{first['id']}/reject",json={'version':1,'reason':'Need more data'},headers=identity['owner'])
    assert rejected.json()['action']['approval_status']=='rejected' and rejected.json()['action']['execution_status']=='cancelled'
    await run_action(first['id']);assert fake.writes==[]
    async with Session.begin() as db:
        conn=await db.get(MetaConnection,cid);conn.status='connected'
    second=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    async with Session.begin() as db:
        row=await db.get(AdAction,second['id']);row.approval_expires_at=now()-timedelta(seconds=1)
    expired=await approve(client,identity,second)
    assert expired.json()['action']['approval_status']=='expired' and expired.json()['action']['execution_status']=='cancelled' and fake.writes==[]


async def test_live_budget_compensation_limit_and_no_direct_execute(client,identity,write_setup):
    fake,_=write_setup
    too_much=proposal(identity,resource_type='adset',resource_id='20',action_type='update_budget',budget_minor_units=13000,dry_run=False)
    assert (await client.post('/v1/ads/actions',json=too_much,headers=identity['owner'])).status_code==422
    body=proposal(identity,resource_type='adset',resource_id='20',action_type='update_budget',budget_minor_units=11500,dry_run=False)
    made=(await client.post('/v1/ads/actions',json=body,headers=identity['owner'])).json()['action']
    bypass=await client.post(f"/v1/ads/actions/{made['id']}/execute",json={'version':1,'confirmation':'CONFIRM'},headers=identity['owner'])
    assert bypass.status_code==409 and fake.writes==[]
    await approve(client,identity,made);await run_action(made['id'])
    action=(await get_approval(client,identity,made['id'])).json()['action']
    assert action['execution_status']=='succeeded' and action['after_state']['daily_budget']=='11500'
    assert action['compensating_action']=={'action_type':'update_budget','state':{'daily_budget':10000}}
    assert fake.writes==[('20',{'daily_budget':11500})]


async def test_state_drift_and_uncertain_write_never_retry(client,identity,write_setup):
    fake,_=write_setup
    first=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    await approve(client,identity,first);fake.states['10']['status']='PAUSED';await run_action(first['id'])
    stale=(await get_approval(client,identity,first['id'])).json()['action']
    assert stale['execution_status']=='stale' and stale['error_code']=='meta_state_changed' and fake.writes==[]
    fake.states['10']['status']='ACTIVE';fake.failure='meta_write_unknown'
    second=(await client.post('/v1/ads/actions',json=proposal(identity,dry_run=False),headers=identity['owner'])).json()['action']
    await approve(client,identity,second);await run_action(second['id']);await run_action(second['id'])
    unknown=(await get_approval(client,identity,second['id'])).json()['action']
    assert unknown['execution_status']=='unknown' and len(fake.writes)==1


async def test_dry_run_available_while_live_write_disabled(client,identity,write_setup,monkeypatch):
    fake,cid=write_setup;monkeypatch.setattr(settings(),'meta_write_enabled',False)
    async with Session.begin() as db:
        conn=await db.get(MetaConnection,cid);conn.scopes=['ads_read']
    made=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    await approve(client,identity,made);await run_action(made['id'])
    assert (await get_approval(client,identity,made['id'])).json()['action']['execution_status']=='simulated' and fake.writes==[]
    live=await client.post('/v1/ads/actions',json=proposal(identity,dry_run=False),headers=identity['owner'])
    assert live.status_code==503


async def test_dispatch_recovers_and_enqueues(client,identity,write_setup):
    first=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    second=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    await approve(client,identity,second)
    async with Session.begin() as db:
        row=await db.get(AdAction,first['id']);row.execution_status='executing';row.updated_at=now()-timedelta(minutes=3)
    class Queue:
        def __init__(self):self.calls=[]
        async def enqueue_job(self,*args,**kwargs):self.calls.append((args,kwargs))
    redis=Queue();await dispatch_actions({'redis':redis})
    async with Session() as db:
        row=await db.get(AdAction,first['id']);assert row.execution_status=='unknown' and row.error_code=='execution_worker_lost'
    assert redis.calls[0][0]==('execute_action',second['id'])


async def test_resource_lock_leaves_overlapping_action_queued(client,identity,write_setup):
    fake,_=write_setup
    first=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    second=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    await approve(client,identity,first);await approve(client,identity,second)
    original=fake.resource;started=asyncio.Event();release=asyncio.Event()
    async def slow(*args):started.set();await release.wait();return await original(*args)
    fake.resource=slow
    task=asyncio.create_task(run_action(first['id']));await asyncio.wait_for(started.wait(),3);await run_action(second['id'])
    async with Session() as db:assert (await db.get(AdAction,second['id'])).execution_status=='queued'
    release.set();await task


async def test_meta_write_transport_is_allowlisted_and_never_retried(meta,monkeypatch):
    monkeypatch.setattr(settings(),'meta_write_enabled',True);calls=[]
    def handler(request):calls.append(request);raise httpx.ReadTimeout('uncertain',request=request)
    client=MetaClient('synthetic-token',transport=httpx.MockTransport(handler))
    with pytest.raises(MetaError,match='meta_write_unknown'):await client.write_resource('10',{'status':'PAUSED'})
    assert len(calls)==1 and calls[0].method=='POST' and calls[0].url.host=='graph.facebook.com'
    with pytest.raises(MetaError,match='meta_write_payload_invalid'):await client.write_resource('10',{'name':'forbidden'})
    with pytest.raises(MetaError,match='meta_endpoint_forbidden'):await client._request('evil')
