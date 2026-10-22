from datetime import timedelta
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4
from unittest.mock import AsyncMock
import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select, func
from pao.config import settings
from pao.db import Session
from pao.models import MetaConnection, MetaSyncJob, MetaSnapshot, MetaOAuthState, Member, now
from pao.integrations.meta.client import MetaClient, MetaError, encrypt, decrypt
from pao.integrations.meta.sync import sync_meta, dispatch_meta
from pao.integrations.meta.api import CALLBACK, COOKIE

BASE='/v1/integrations/meta'


@pytest.fixture
def meta(monkeypatch):
    for name,value in {'meta_enabled':True,'meta_app_id':'123','meta_app_secret':'synthetic-secret',
        'meta_graph_api_version':'v25.0','meta_redirect_uri':'http://test'+CALLBACK,
        'integration_encryption_key':Fernet.generate_key().decode()}.items():monkeypatch.setattr(settings(),name,value)
    # Production permits HTTP only on loopback. Test origin represents HTTPS deployment.
    monkeypatch.setattr(settings(),'meta_redirect_uri','https://test'+CALLBACK)


async def connected(identity):
    async with Session.begin() as db:
        from pao.integrations import ads_apps
        app_context=await ads_apps.resolve(db,identity['workspace'],'meta')
        row=MetaConnection(workspace_id=identity['workspace'],user_id=identity['user_id'],token_ciphertext=encrypt('synthetic-token'),
            remote_user_id='42',scopes=['ads_read'],expires_at=now()+timedelta(hours=1),status='connected',app_binding=app_context.binding)
        db.add(row);await db.flush();return row.id


@pytest.mark.parametrize('actor,expected',[('owner',200),('other',403),('outsider',404)])
async def test_oauth_access(client,identity,meta,actor,expected):
    result=await client.post(BASE+'/oauth/start',params={'workspace_id':identity['workspace']},headers=identity[actor])
    assert result.status_code==expected
    if expected==200:assert 'scope=ads_read' in result.json()['authorization_url'] and 'ads_management' not in result.text


async def test_oauth_cookie_replay_encryption(client,identity,meta,monkeypatch):
    monkeypatch.setattr(MetaClient,'exchange',AsyncMock(return_value=('synthetic-token',3600)))
    monkeypatch.setattr(MetaClient,'identity',AsyncMock(return_value=('42',['ads_read'])))
    response=await client.post(BASE+'/oauth/start',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    state=parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]
    cookie=response.cookies[COOKIE]
    params={'state':state,'code':'synthetic-code'}
    assert (await client.get(CALLBACK,params=params)).status_code==400  # secure cookie not sent over test HTTP
    result=await client.get(CALLBACK,params=params,headers={'Cookie':COOKIE+'='+cookie})
    assert result.status_code==200 and 'thành công' in result.text
    assert 'synthetic-token' not in result.text
    assert (await client.get(CALLBACK,params=params,headers={'Cookie':COOKIE+'='+cookie})).status_code==400
    async with Session() as db:
        row=await db.scalar(select(MetaConnection))
        assert row.token_ciphertext!='synthetic-token' and decrypt(row.token_ciphertext)=='synthetic-token'
    public=await client.get(BASE+'/connection',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert 'token' not in public.text and public.json()['status']=='connected'


async def test_oauth_expired_and_disconnect_fence(client,identity,meta,monkeypatch):
    query={'workspace_id':identity['workspace']}
    response=await client.post(BASE+'/oauth/start',params=query,headers=identity['owner'])
    state=parse_qs(urlsplit(response.json()['authorization_url']).query)['state'][0]
    async with Session.begin() as db:
        row=await db.scalar(select(MetaOAuthState));row.expires_at=now()-timedelta(seconds=1)
    assert (await client.get(CALLBACK,params={'state':state,'code':'x'},headers={'Cookie':COOKIE+'='+response.cookies[COOKIE]})).status_code==400
    await client.delete(BASE+'/connection',params=query,headers=identity['owner'])
    async with Session() as db:assert (await db.scalar(select(MetaOAuthState))).used


async def test_readonly_transport_and_cursor(meta):
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.url.host=='graph.facebook.com' and request.method=='GET'
        assert request.headers['authorization']=='Bearer synthetic-token'
        assert 'access_token' not in str(request.url)
        if len(requests)==1:return httpx.Response(200,json={'data':[{'id':'act_1','name':'A','secret':'removed'}],
            'paging':{'next':'https://hostile.test/?access_token=secret','cursors':{'after':'cursor'}}})
        assert request.url.params['after']=='cursor'
        return httpx.Response(200,json={'data':[]})
    client=MetaClient('synthetic-token',transport=httpx.MockTransport(handler))
    rows=[row async for row in client.rows('accounts')]
    assert rows==[{'id':'act_1','name':'A'}] and len(requests)==2
    with pytest.raises(MetaError):await client._request('act_1/campaigns',oauth={'name':'write'})
    with pytest.raises(MetaError):await client._request('https://hostile.test')
    with pytest.raises(MetaError):await client._request('act_1/unknown')


@pytest.mark.parametrize('status,payload,error,calls',[(429,{'error':{'code':4}},'meta_rate_limited',3),
    (400,{'error':{'code':190,'message':'secret'}},'meta_reauthorization_required',1),
    (403,{'error':{'code':200}},'meta_permission_denied',1)])
async def test_provider_failures(meta,status,payload,error,calls):
    count=0
    def handler(request):
        nonlocal count;count+=1;return httpx.Response(status,json=payload)
    client=MetaClient('synthetic-token',transport=httpx.MockTransport(handler),sleep=AsyncMock())
    with pytest.raises(MetaError,match=error):await client._request('me')
    assert count==calls


async def test_sync_scope_idempotency_atomic_snapshots(client,identity,meta,monkeypatch):
    cid=await connected(identity)
    async def rows(self,kind,*args):
        if kind=='accounts':yield {'id':'act_1','name':'Test account'}
        elif kind=='insights':yield {'ad_id':'3','date_start':args[1],'date_stop':args[2],'spend':'1.23'}
        else:yield {'id':'3','name':kind}
    monkeypatch.setattr(MetaClient,'rows',rows)
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'accounts'}
    result=await client.post(BASE+'/sync',json=body,headers=identity['owner']);assert result.status_code==202
    jid=result.json()['id']
    assert (await client.post(BASE+'/sync',json=body,headers=identity['owner'])).json()['id']==jid
    assert (await client.post(BASE+'/sync',json={**body,'request_key':str(uuid4())},headers=identity['owner'])).status_code==409
    assert (await client.post(BASE+'/sync',json=body,headers=identity['other'])).status_code==403
    query={'workspace_id':identity['workspace'],'kind':'accounts'}
    assert (await client.get(BASE+'/snapshots',params=query,headers=identity['owner'])).json()['rows']==[]
    await sync_meta({},jid);await sync_meta({},jid)
    assert len((await client.get(BASE+'/snapshots',params=query,headers=identity['owner'])).json()['rows'])==1
    assert (await client.get(BASE+'/snapshots',params=query,headers=identity['other'])).json()['rows']==[]
    historical={**body,'request_key':str(uuid4()),'kind':'historical','account_id':'act_1','since':'2026-01-01','until':'2026-01-10'}
    result=await client.post(BASE+'/sync',json=historical,headers=identity['owner']);assert result.status_code==202
    await sync_meta({},result.json()['id'])
    async with Session() as db:
        job=await db.get(MetaSyncJob,result.json()['id']);assert job.status=='completed' and job.row_count==5
    await client.delete(BASE+'/connection',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert (await client.get(BASE+'/snapshots',params=query,headers=identity['owner'])).json()['rows']==[]
    async with Session() as db:assert (await db.get(MetaConnection,cid)).token_ciphertext is None


@pytest.mark.parametrize('failure',['partial','disconnect','role'])
async def test_inflight_failure_never_publishes(client,identity,meta,monkeypatch,failure):
    cid=await connected(identity)
    async def rows(self,*args):
        yield {'id':'act_1'}
        if failure=='partial':raise MetaError('meta_rate_limited')
        async with Session.begin() as db:
            if failure=='disconnect':
                conn=await db.get(MetaConnection,cid);conn.version+=1;conn.status='disconnected';conn.token_ciphertext=None
            else:
                member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    monkeypatch.setattr(MetaClient,'rows',rows)
    result=await client.post(BASE+'/sync',json={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'accounts'},headers=identity['owner'])
    await sync_meta({},result.json()['id'])
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(MetaSnapshot))==0
        assert (await db.get(MetaSyncJob,result.json()['id'])).status==('failed' if failure=='partial' else 'cancelled')


async def test_date_and_account_validation(client,identity,meta):
    await connected(identity)
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'historical','account_id':'act_99','since':'2026-01-01','until':'2026-02-15'}
    assert (await client.post(BASE+'/sync',json=body,headers=identity['owner'])).status_code==422
    body['until']='2026-01-02'
    assert (await client.post(BASE+'/sync',json=body,headers=identity['owner'])).status_code==409


async def test_stale_recovery_no_blind_resend(client,identity,meta):
    cid=await connected(identity)
    async with Session.begin() as db:
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='accounts',status='running',attempts=1,updated_at=now()-timedelta(minutes=10))
        db.add(job);await db.flush();jid=job.id
    redis=AsyncMock();await dispatch_meta({'redis':redis});redis.enqueue_job.assert_not_awaited()
    await dispatch_meta({'redis':redis});redis.enqueue_job.assert_not_awaited()
    async with Session() as db:
        job=await db.get(MetaSyncJob,jid)
        assert job.status=='failed' and job.error_code=='meta_worker_lost_unknown' and job.attempts==1
