"""Dedicated pao_test / Redis15 only; never call live Ads."""
import asyncio
import signal
from types import SimpleNamespace
import httpx
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, text, delete
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import (MetaConnection,GoogleAdsConnection,MetaSyncJob,GoogleAdsSyncJob,
    TenantConnectionGrant,TenantConnectionReference,Member,User,AdMetric,AdEntity,MetaSnapshot,now)
from pao.modules.connections import ads_authority
from test_connection_inventory import corpus,path,SECRET
from test_connection_grants import stage
from test_meta import meta
from test_google_ads import google_ads
from test_ads_actions import write_setup

KINDS=('meta_ads','google_ads')
JOBS={'meta_ads':MetaSyncJob,'google_ads':GoogleAdsSyncJob}
SOURCES=ads_authority.MODELS
BASE={'meta_ads':'/v1/integrations/meta','google_ads':'/v1/integrations/google-ads'}


async def ready(c,kind):
    from pao.integrations.meta.client import encrypt
    async with Session.begin() as db:
        conn=await db.get(SOURCES[kind],c['connections']['a'][kind])
        from pao.integrations import ads_apps
        conn.app_binding=(await ads_apps.resolve(db,conn.workspace_id,'meta' if kind=='meta_ads' else 'google')).binding
        if kind=='meta_ads':
            conn.token_ciphertext=encrypt('fixture-read-token');conn.expires_at=now()+timedelta(hours=1)
            conn.scopes=['ads_read']
        else:
            conn.refresh_token_ciphertext=encrypt('fixture-refresh-token')
            conn.scopes=['https://www.googleapis.com/auth/adwords']


async def consent(client,c,kind,saved=None):
    await ready(c,kind)
    if not saved:
        res,_=await stage(client,c,kind);assert res.status_code==201,res.text;saved=res.json()
    body={'reference_revision':1,'grant_revision':1,'request_key':str(uuid4()),
          'capability':'ads_read','allow_ads_read_ack':True}
    url=path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-ads"
    result=await client.post(url,headers=c['owner'],json=body)
    assert result.status_code==201,result.text
    return saved,url,body


async def enqueue(client,c,kind,saved,change=None):
    day=(date.today()-timedelta(days=1)).isoformat()
    body={'workspace_id':c['workspace'],'request_key':str(uuid4()),'kind':'historical',
          'account_id':saved['grant']['account_id'],'brand_id':saved['grant']['brand_id'],
          'grant_id':saved['grant']['id'],'since':day,'until':day}
    if kind=='meta_ads':body['warehouse']=True
    body.update(change or {})
    return await client.post(BASE[kind]+'/sync',headers=c['other'],json=body),body


async def run(kind,job_id):
    from pao.integrations.meta.sync import sync_meta
    from pao.integrations.google_ads.sync import sync_google_ads
    await (sync_meta if kind=='meta_ads' else sync_google_ads)({},job_id)


async def record(kind,job_id):
    async with Session() as db:return await db.get(JOBS[kind],job_id)


def fixture_fetch(monkeypatch,kind,side_effect=None):
    import pao.integrations.meta.sync as m
    import pao.integrations.google_ads.sync as g
    async def payload(*args):
        job=args[-1]
        return [dict(connection_id=job.connection_id if kind=='meta_ads' else None,
            google_connection_id=job.connection_id if kind=='google_ads' else None,
            connection_version=job.connection_version,platform='meta' if kind=='meta_ads' else 'google',account_id=job.account_id,
            kind='account',remote_id=job.account_id,currency='USD',timezone='UTC',
            source_job_id=job.id if kind=='meta_ads' else None,
            google_source_job_id=job.id if kind=='google_ads' else None)],[]
    fetch=AsyncMock(side_effect=side_effect or payload)
    monkeypatch.setattr(m if kind=='meta_ads' else g,'fetch_warehouse' if kind=='meta_ads' else 'fetch_historical',fetch)
    return fetch


@pytest.mark.parametrize('kind',KINDS)
async def test_consent_exact_pin_sync_replay_discovery(client,corpus,meta,google_ads,monkeypatch,kind):
    c=corpus;saved,url,body=await consent(client,c,kind)
    repeat=await client.post(url,headers=c['owner'],json=body)
    assert repeat.status_code==201 and repeat.json()['replayed'] is True
    queued,request=await enqueue(client,c,kind,saved);assert queued.status_code==202,queued.text
    again=await client.post(BASE[kind]+'/sync',headers=c['other'],json=request)
    assert again.status_code==202 and again.json()['id']==queued.json()['id']
    pin=(await record(kind,queued.json()['id'])).authority_pin
    assert pin['workspace_id']==c['workspace'] and pin['actor_id']==c['operator_id']
    assert pin['account_id']==saved['grant']['account_id'] and pin['capability']=='ads_read'
    fetch=fixture_fetch(monkeypatch,kind);await run(kind,queued.json()['id'])
    assert fetch.await_count==1 and (await record(kind,queued.json()['id'])).status=='completed'
    catalog=await client.get(path(c['workspace'])+'/ads-grants',headers=c['other'],params={'brand_id':c['brands']['a']})
    assert catalog.status_code==200 and catalog.headers['cache-control']=='no-store'
    assert catalog.json()['items'][0]['grant_id']==saved['grant']['id']
    assert SECRET not in catalog.text and 'ciphertext' not in catalog.text
    assert (await client.get(path(c['workspace'])+'/ads-grants',headers=c['other'])).json()['items']==[]
    assert (await client.get(path(c['second'])+'/ads-grants',headers=c['other'])).status_code==403
    query={'kind':kind,'connection_id':c['connections']['a'][kind]}
    accounts=await client.get(path(c['workspace'])+'/ads-accounts',headers=c['owner'],params=query)
    assert accounts.status_code==200 and accounts.json()['items']==[{'account_id':saved['grant']['account_id']}]
    assert (await client.get(path(c['workspace'])+'/ads-accounts',headers=c['other'],params=query)).status_code==403
    assert (await client.get(path(c['second'])+'/ads-accounts',headers=c['owner'],params=query)).status_code==404


async def test_registered_read_mapping_cancels_old_approved_action(client,identity,write_setup,monkeypatch):
    from test_ads_actions import proposal,approve,run_action
    from pao.models import AdAction
    fake,cid=write_setup
    made=await client.post('/v1/ads/actions',headers=identity['owner'],json=proposal(identity))
    assert made.status_code==201
    action=made.json()['action'];assert (await approve(client,identity,action)).status_code==200
    body={'kind':'meta_ads','connection_id':cid,'expected_version':1,'brand_id':None,
          'account_id':'act_1','grantee_id':identity['user_id'],'permission':'read_only'}
    preview=await client.post(path(identity['workspace'])+'/mapping-preview',headers=identity['owner'],json=body)
    saved=await client.post(path(identity['workspace'])+'/references',headers=identity['owner'],json={**body,
        'preview_hash':preview.json()['preview_hash'],'request_key':str(uuid4()),'ttl_minutes':60,
        'manager_id':None,'apply_data_only_ack':True})
    assert saved.status_code==201
    def forbidden(*args):raise AssertionError('Read mapping must not authorize action decrypt')
    monkeypatch.setattr('pao.ads_actions.decrypt',forbidden)
    await run_action(action['id'])
    async with Session() as db:assert (await db.get(AdAction,action['id'])).execution_status=='cancelled'
    assert fake.writes==[]


async def test_meta_typed_account_provenance_without_raw_snapshot(client,corpus,meta,google_ads):
    c=corpus;cid=c['connections']['a']['meta_ads']
    async with Session.begin() as db:
        job=await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id==cid,MetaSyncJob.kind=='accounts'))
        db.add(AdEntity(connection_id=cid,connection_version=3,platform='meta',account_id='act_123',
            remote_id='act_123',kind='account',currency='USD',timezone='UTC',source_job_id=job.id))
        await db.execute(delete(MetaSnapshot).where(MetaSnapshot.job_id==job.id))
    saved,_,_=await consent(client,c,'meta_ads')
    result,_=await enqueue(client,c,'meta_ads',saved)
    assert result.status_code==202,result.text


@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('change',['revoke','rotate','role','manager','expiry','scopes','disconnect'])
async def test_queued_denies_before_decrypt(client,corpus,meta,google_ads,monkeypatch,kind,change):
    c=corpus;saved,_,_=await consent(client,c,kind)
    queued,_=await enqueue(client,c,kind,saved);assert queued.status_code==202,queued.text
    async with Session.begin() as db:
        conn=await db.get(SOURCES[kind],c['connections']['a'][kind])
        grant=await db.get(TenantConnectionGrant,saved['grant']['id'])
        if change=='revoke':grant.status='revoked';grant.revision+=1
        if change=='rotate':conn.version+=1
        if change=='role':(await db.get(Member,(c['workspace'],c['operator_id']))).role='viewer'
        if change=='manager':(await db.get(User,c['user_id'])).active=False
        if change=='scopes':conn.scopes=[]
        if change=='disconnect':conn.status='disconnected'
    if change=='expiry':monkeypatch.setattr('pao.modules.connections.grants.now',lambda:now()+timedelta(hours=2))
    import pao.integrations.meta.sync as m
    import pao.integrations.google_ads.sync as g
    def forbidden(*args):raise AssertionError('Denied job must not decrypt')
    monkeypatch.setattr(m if kind=='meta_ads' else g,'decrypt',forbidden)
    fetch=fixture_fetch(monkeypatch,kind);await run(kind,queued.json()['id'])
    assert fetch.await_count==0 and (await record(kind,queued.json()['id'])).status=='cancelled'


@pytest.mark.parametrize('kind',KINDS)
async def test_staged_and_legacy_owner_never_execute_registered(client,corpus,meta,google_ads,monkeypatch,kind):
    c=corpus;await ready(c,kind);res,_=await stage(client,c,kind);saved=res.json()
    assert (await enqueue(client,c,kind,saved))[0].status_code==403
    result=await client.post(BASE[kind]+'/sync',headers=c['owner'],json={
        'workspace_id':c['workspace'],'request_key':str(uuid4()),'kind':'accounts'})
    assert result.status_code==403
    async with Session.begin() as db:
        conn=await db.get(SOURCES[kind],c['connections']['a'][kind])
        job=JOBS[kind](connection_id=conn.id,connection_version=conn.version,api_version='fixture',
                       request_key='old-queued',kind='accounts');db.add(job);await db.flush();jid=job.id
    fetch=fixture_fetch(monkeypatch,kind);await run(kind,jid)
    assert fetch.await_count==0 and (await record(kind,jid)).status=='cancelled'
    # Configuration status still available to the native manager, not execution.
    assert (await client.get(BASE[kind]+'/connection',headers=c['owner'],params={'workspace_id':c['workspace']})).status_code==200


@pytest.mark.parametrize('kind',KINDS)
async def test_late_revoke_discards_result(client,corpus,meta,google_ads,monkeypatch,kind):
    c=corpus;saved,_,_=await consent(client,c,kind)
    queued,_=await enqueue(client,c,kind,saved);assert queued.status_code==202
    started,release=asyncio.Event(),asyncio.Event()
    async def wait(*args):started.set();await release.wait();return [],[]
    fixture_fetch(monkeypatch,kind,wait)
    worker=asyncio.create_task(run(kind,queued.json()['id']))
    try:
        await asyncio.wait_for(started.wait(),8)
        revoked=await client.post(path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/revoke",
            headers=c['owner'],json={'reference_revision':1,'grant_revision':1})
        assert revoked.status_code==200
        release.set();await asyncio.wait_for(worker,8)
        assert (await record(kind,queued.json()['id'])).status=='cancelled'
    finally:
        release.set();await asyncio.gather(worker,return_exceptions=True)


@pytest.mark.parametrize('kind',KINDS)
async def test_scope_tamper_and_immutable_database_pin(client,corpus,meta,google_ads,kind):
    c=corpus;saved,_,_=await consent(client,c,kind)
    for change in ({'brand_id':None},{'account_id':'act_999' if kind=='meta_ads' else '9999999999'},
                   {'workspace_id':c['second']}):
        assert (await enqueue(client,c,kind,saved,change))[0].status_code==403
    q,_=await enqueue(client,c,kind,saved);assert q.status_code==202
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            await db.execute(text(f'UPDATE {JOBS[kind].__tablename__} SET authority_pin=NULL WHERE id=:id'),{'id':q.json()['id']})


@pytest.mark.parametrize('kind',KINDS)
async def test_report_completed_source_account_provenance(client,corpus,meta,google_ads,monkeypatch,kind):
    c=corpus;saved,_,_=await consent(client,c,kind)
    queued,_=await enqueue(client,c,kind,saved);assert queued.status_code==202
    fixture_fetch(monkeypatch,kind);await run(kind,queued.json()['id'])
    connid=c['connections']['a'][kind];version=3 if kind=='meta_ads' else 4
    async with Session.begin() as db:
        for entity,source,account in (('1',connid,saved['grant']['account_id']),
            ('2',c['connections']['b'][kind],saved['grant']['account_id']),
            ('3',connid,'act_999' if kind=='meta_ads' else '9999999999')):
            db.add(AdMetric(connection_id=source if kind=='meta_ads' else None,
                google_connection_id=source if kind=='google_ads' else None,connection_version=version,
                platform='meta' if kind=='meta_ads' else 'google',account_id=account,level='campaign',
                entity_id=entity,day=date.today()-timedelta(days=1),granularity='daily',currency='USD',
                timezone='UTC',attribution='fixture',source_job_id=queued.json()['id'] if kind=='meta_ads' else None,
                google_source_job_id=queued.json()['id'] if kind=='google_ads' else None,spend=None))
    url=path(c['workspace'])+f"/grants/{saved['grant']['id']}/ads-report"
    query={'brand_id':c['brands']['a'],'since':(date.today()-timedelta(days=1)).isoformat(),'until':date.today().isoformat()}
    result=await client.get(url,headers=c['other'],params=query)
    assert result.status_code==200,result.text
    assert [r['entity_id'] for r in result.json()['rows']]==['1']
    assert result.json()['rows'][0]['spend'] is None and result.headers['cache-control']=='no-store'
    assert (await client.get(url,headers=c['owner'],params=query)).status_code==403
    assert (await client.get(url,headers=c['other'],params={**query,'brand_id':c['brands']['b']})).status_code==403


@pytest.mark.parametrize('kind',KINDS)
async def test_two_sme_real_arq_one_revoked(client,corpus,meta,google_ads,monkeypatch,kind):
    from arq import create_pool
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix,default_queue_name
    from pao.integrations.meta.sync import sync_meta,dispatch_meta
    from pao.integrations.google_ads.sync import sync_google_ads,dispatch_google_ads
    c=corpus
    async with Session.begin() as db:db.add(Member(workspace_id=c['second'],user_id=c['operator_id'],role='operator'))
    b={**c,'workspace':c['second'],'brands':{'a':c['brands']['b']},'connections':{'a':c['connections']['b']}}
    saved=[];ids=[]
    for ctx in (c,b):
        s,_,_=await consent(client,ctx,kind);saved.append(s)
        q,_=await enqueue(client,ctx,kind,s);assert q.status_code==202,q.text;ids.append(q.json()['id'])
    await client.post(path(c['workspace'])+f"/references/{saved[0]['reference']['id']}/grants/{saved[0]['grant']['id']}/revoke",
        headers=c['owner'],json={'reference_revision':1,'grant_revision':1})
    fetch=fixture_fetch(monkeypatch,kind)
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:s21b2d:'+uuid4().hex;redis=await create_pool(config,default_queue_name=queue)
    fn=sync_meta if kind=='meta_ads' else sync_google_ads
    dispatcher=dispatch_meta if kind=='meta_ads' else dispatch_google_ads
    jobs=[('meta:' if kind=='meta_ads' else 'google-ads:')+i for i in ids];runner=None
    class Workers:
        functions=[fn];redis_settings=config;queue_name=queue;handle_signals=False;burst=True
        max_jobs=max_burst_jobs=2;keep_result=0;poll_delay=.05;job_timeout=20
    try:
        class DefaultQueue:
            async def enqueue_job(self,*args,**kw):return await redis.enqueue_job(*args,_queue_name=default_queue_name,**kw)
        await dispatcher({'redis':DefaultQueue()})
        for jid in jobs:
            assert await redis.exists(job_key_prefix+jid)
            score=await redis.zscore(default_queue_name,jid);assert score is not None
            await redis.zrem(default_queue_name,jid);await redis.zadd(queue,{jid:score})
        runner=create_worker(Workers);await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==2 and runner.jobs_failed==0 and fetch.await_count==1
        assert (await record(kind,ids[0])).status=='cancelled'
        assert (await record(kind,ids[1])).status=='completed'
    finally:
        if runner:
            if not hasattr(signal,'SIGUSR1'):runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
            await runner.close()
        await redis.delete(queue,*(prefix+jid for jid in jobs for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()


async def test_meta_granted_transport_never_lists_all_accounts(meta):
    from pao.integrations.meta.client import MetaClient,MetaError
    from pao.warehouse import fetch_warehouse
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        assert req.method=='GET' and req.url.path.startswith('/v25.0/act_123')
        assert req.url.path!='/v25.0/me/adaccounts'
        if req.url.path=='/v25.0/act_123':return httpx.Response(200,json={
            'id':'act_123','account_id':'123','currency':'USD','timezone_name':'UTC',
            'access_token':'not-a-credential-marker','business':{'id':'1','token':'not-a-credential-marker'}})
        return httpx.Response(200,json={'data':[]})
    client=MetaClient('fixture',transport=httpx.MockTransport(handler))
    day=(date.today()-timedelta(days=1)).isoformat()
    job=SimpleNamespace(id=str(uuid4()),connection_id=str(uuid4()),connection_version=1,account_id='act_123',
        since=day,until=day,granularity='daily',authority_pin={'capability':'ads_read'})
    entities,metrics=await fetch_warehouse(client,job)
    assert len(entities)==1 and metrics==[] and calls[0]=='/v25.0/act_123'
    assert 'not-a-credential-marker' not in str(await client.account('act_123'))
    with pytest.raises(MetaError):await client.account('act_123/ads')


async def test_google_granted_transport_never_lists_accounts_and_missing_spend(google_ads):
    from pao.integrations.google_ads.client import GoogleAdsClient
    from pao.integrations.google_ads.warehouse import fetch_historical
    calls=[]
    def handler(req):
        calls.append(req.url.path)
        if req.url.host=='oauth2.googleapis.com':return httpx.Response(200,json={'access_token':'fixture-access'})
        assert req.method=='POST' and req.url.path=='/v25/customers/1234567890/googleAds:search'
        query=__import__('json').loads(req.content)['query']
        if 'FROM customer' in query:return httpx.Response(200,json={'results':[{'customer':{
            'id':'1234567890','currencyCode':'USD','timeZone':'UTC','manager':False}}]})
        if 'FROM campaign' in query and 'metrics.' in query:return httpx.Response(200,json={'results':[{
            'campaign':{'id':'10'},'segments':{'date':'2026-01-01'},'metrics':{}}]})
        return httpx.Response(200,json={'results':[]})
    job=SimpleNamespace(id=str(uuid4()),connection_id=str(uuid4()),connection_version=1,account_id='1234567890',
        since='2026-01-01',until='2026-01-01',granularity='daily',authority_pin={'capability':'ads_read'})
    _,metrics=await fetch_historical(GoogleAdsClient(transport=httpx.MockTransport(handler)),'fixture-refresh',job)
    assert len(metrics)==1 and metrics[0]['spend'] is None and metrics[0]['roas'] is None
    assert not any('listAccessibleCustomers' in path for path in calls)
