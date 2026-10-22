"""Synthetic warehouse/audit on real DB; NOT live Meta business acceptance."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import AdAction,AdActionAudit,AdMetric,MetaSyncJob,MetaConnection,OutcomeObservation,Member,now
from test_meta import connected,meta

async def fixture(identity,monkeypatch,**changes):
    monkeypatch.setattr(settings(),'outcome_observations_enabled',True)
    cid=await connected(identity);stamp=now().replace(minute=0,second=0,microsecond=0)-timedelta(days=8)
    async with Session.begin() as db:
        action=AdAction(workspace_id=identity['workspace'],user_id=identity['user_id'],connection_id=cid,connection_version=1,
            account_id='act_1',resource_type='campaign',resource_id='10',action_type='pause',request_key=str(uuid4()),payload_hash='a'*64,
            before_state={'status':'ACTIVE'},proposed_state={'status':'PAUSED'},after_state={'status':'PAUSED'},reason='Synthetic outcome fixture',
            approval_status='approved',execution_status='succeeded',dry_run=False,approval_expires_at=now()+timedelta(hours=1),executed_at=stamp,**changes)
        db.add(action);await db.flush()
        db.add(AdActionAudit(workspace_id=identity['workspace'],action_id=action.id,actor_id=identity['user_id'],event='action.succeeded',action_version=action.version,data={'after_state':action.after_state,'error_code':None}))
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='historical',account_id='act_1',
            since=(stamp-timedelta(days=8)).date().isoformat(),until=(stamp+timedelta(days=8)).date().isoformat(),status='completed',warehouse=True,granularity='hourly')
        db.add(job);await db.flush()
        for offset in range(-168,168):
            time=stamp+timedelta(hours=offset)
            db.add(AdMetric(connection_id=cid,connection_version=1,account_id='act_1',level='campaign',entity_id='10',day=time.date(),hour=time.hour,
                granularity='hourly',currency='USD',timezone='UTC',attribution='7d_click',spend=10,clicks=20,purchase=1 if offset<0 else 2,revenue=100 if offset<0 else 200,source_job_id=job.id))
        await db.flush();ident=action.id
    return ident,cid,stamp

async def preview(client,identity,ident):
    r=await client.post('/v1/ads/actions/'+ident+'/outcome-preview',headers=identity['owner']);assert r.status_code==200,r.text
    return r.json()

def payload(value):return {'observed_at':value['observed_at'],'confirmation_hash':value['confirmation_hash'],'request_key':str(uuid4())}

async def test_pinned_all_windows_concurrent_dedup_history_and_stale_source(client,identity,meta,monkeypatch):
    ident,_,_=await fixture(identity,monkeypatch);p=await preview(client,identity,ident)
    assert all(v['status']=='observed' and not v['causal_effect_proven'] for v in p['outcomes'].values())
    assert p['pins']['metric_count']==336
    body=payload(p);url='/v1/ads/actions/'+ident+'/outcome-observations'
    values=await asyncio.gather(*(client.post(url,headers=identity['owner'],json=body) for _ in range(3)))
    assert all(v.status_code==201 for v in values),[v.text for v in values]
    saved=values[0].json();assert {v.json()['id'] for v in values}=={saved['id']}
    history=await client.get(url,headers=identity['owner']);assert len(history.json())==1
    r=await client.get('/v1/ads/outcome-observations/'+saved['id'],headers=identity['owner']);assert r.json()['current_source_matches']
    assert r.json()['snapshot']['outcomes']['24h']['delta']['purchase']=='24.000000'
    async with Session.begin() as db:(await db.scalar(select(AdMetric))).revenue=999
    r=await client.get('/v1/ads/outcome-observations/'+saved['id'],headers=identity['owner']);assert not r.json()['current_source_matches']
    assert r.json()['source_hash']==saved['source_hash']
    assert (await client.post(url,headers=identity['owner'],json=body)).json()['id']==saved['id']
    assert (await client.post(url,headers=identity['owner'],json={**body,'confirmation_hash':'0'*64})).status_code==409
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text("UPDATE outcome_observations SET source_hash=repeat('0',64)"))
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text('DELETE FROM outcome_observations'))

@pytest.mark.parametrize('change',['metric','job','action','proof','connection'])
async def test_preview_pin_changes_fail_closed(client,identity,meta,monkeypatch,change):
    ident,cid,_=await fixture(identity,monkeypatch);p=await preview(client,identity,ident)
    async with Session.begin() as db:
        if change=='metric':(await db.scalar(select(AdMetric))).spend=11
        elif change=='job':(await db.scalar(select(MetaSyncJob))).status='failed'
        elif change=='action':(await db.get(AdAction,ident)).version+=1
        elif change=='proof':(await db.scalar(select(AdActionAudit))).data={'after_state':{'status':'different'}}
        else:(await db.get(MetaConnection,cid)).version+=1
    r=await client.post('/v1/ads/actions/'+ident+'/outcome-observations',headers=identity['owner'],json=payload(p));assert r.status_code==409,r.text
    async with Session() as db:assert await db.scalar(select(func.count(OutcomeObservation.id)))==0

@pytest.mark.parametrize('invalid',['future','expired','naive'])
async def test_timestamp_cannot_fast_forward_or_backdate_window(client,identity,meta,monkeypatch,invalid):
    ident,_,_=await fixture(identity,monkeypatch);p=await preview(client,identity,ident);body=payload(p)
    stamp=now()+timedelta(days=8) if invalid=='future' else now()-timedelta(minutes=6)
    body['observed_at']=stamp.replace(tzinfo=None).isoformat() if invalid=='naive' else stamp.isoformat()
    r=await client.post('/v1/ads/actions/'+ident+'/outcome-observations',headers=identity['owner'],json=body);assert r.status_code==(422 if invalid=='naive' else 409)

@pytest.mark.parametrize('case',['dry_run','missing','job_failed','partial_hour','pending','proof_wrong_actor','no_proof'])
async def test_insufficient_and_pending_are_stored_honestly(client,identity,meta,monkeypatch,case):
    ident,_,_=await fixture(identity,monkeypatch)
    async with Session.begin() as db:
        action=await db.get(AdAction,ident)
        if case=='dry_run':action.dry_run=True
        elif case=='missing':await db.delete(await db.scalar(select(AdMetric).order_by(AdMetric.day.desc(),AdMetric.hour.desc())))
        elif case=='job_failed':(await db.scalar(select(MetaSyncJob))).status='failed'
        elif case=='partial_hour':action.executed_at+=timedelta(minutes=1)
        elif case=='pending':action.executed_at=now().replace(minute=0,second=0,microsecond=0)
        elif case=='proof_wrong_actor':(await db.scalar(select(AdActionAudit))).actor_id=(await db.scalar(select(Member.user_id).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id'])))
        else:await db.delete(await db.scalar(select(AdActionAudit)))
    p=await preview(client,identity,ident)
    assert p['outcomes']['7d']['status']==('pending' if case=='pending' else 'insufficient')
    r=await client.post('/v1/ads/actions/'+ident+'/outcome-observations',headers=identity['owner'],json=payload(p));assert r.status_code==201
    assert r.json()['statuses']['7d']==('pending' if case=='pending' else 'insufficient')

async def test_scoped_read_capture_permission_loss_and_gate_rollback(client,identity,meta,monkeypatch):
    ident,_,_=await fixture(identity,monkeypatch);p=await preview(client,identity,ident);url='/v1/ads/actions/'+ident+'/outcome-observations'
    r=await client.post(url,headers=identity['owner'],json=payload(p));assert r.status_code==201
    assert (await client.get(url,headers=identity['outsider'])).status_code==404
    assert (await client.get('/v1/ads/outcome-observations/'+r.json()['id'],headers=identity['other'])).status_code==404
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    assert (await client.post(url,headers=identity['owner'],json=payload(p))).status_code==403
    assert (await client.get(url,headers=identity['owner'])).status_code==200
    settings().outcome_observations_enabled=False
    assert (await client.get(url,headers=identity['owner'])).status_code==409
    assert (await client.get('/v1/ads/outcome-observations/status',params={'workspace_id':identity['workspace']},headers=identity['owner'])).json()['enabled'] is False
