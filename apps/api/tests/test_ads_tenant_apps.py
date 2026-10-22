from datetime import timedelta
from urllib.parse import parse_qs,urlsplit
from uuid import uuid4
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select,text

from pao.config import settings
from pao.db import Session
from pao.models import Workspace,Member,MetaConnection,GoogleAdsConnection,MetaSyncJob,GoogleAdsSyncJob,now
from pao.integrations import ads_apps
from pao.integrations.meta.client import MetaClient,encrypt,MetaError
from pao.integrations.google_ads.client import GoogleAdsClient,SCOPE,GoogleAdsError


@pytest.fixture
def apps(monkeypatch):
    for k,v in {'meta_enabled':True,'google_ads_enabled':True,'meta_app_id':'123','meta_app_secret':'host-meta-secret',
        'meta_graph_api_version':'v26.0','meta_redirect_uri':'https://test/v1/integrations/meta/callback',
        'google_ads_client_id':'host.apps.googleusercontent.com','google_ads_client_secret':'host-google-secret',
        'google_ads_api_version':'v25','google_ads_redirect_uri':'https://test/v1/integrations/google-ads/callback',
        'google_ads_developer_token':'host-developer','google_ads_login_customer_id':'1111111111',
        'integration_encryption_key':Fernet.generate_key().decode()}.items():monkeypatch.setattr(settings(),k,v)


def base(p):return '/v1/integrations/'+('meta' if p=='meta' else 'google-ads')
def body(p,revision=0,client='456'):
    return {'mode':'byo','expected_revision':revision,'consent':True,
        'client_id':client if p=='meta' else client+'.apps.googleusercontent.com',
        'client_secret':'tenant-secret-'+client,'api_version':'v26.0' if p=='meta' else 'v25',
        **({'developer_token':'tenant-developer','login_customer_id':'2222222222'} if p=='google' else {})}


async def second(identity):
    async with Session.begin() as db:
        row=Workspace(name='Second SME');db.add(row);await db.flush()
        db.add(Member(workspace_id=row.id,user_id=identity['user_id'],role='owner'))
        return row.id


@pytest.mark.parametrize('p',['meta','google'])
async def test_config_authority_isolation_secret_and_cas(client,identity,apps,p):
    b=base(p);q={'workspace_id':identity['workspace']};other=await second(identity)
    assert (await client.get(b+'/tenant-app',params=q)).status_code==401
    for actor,status in [('other',403),('outsider',404)]:
        r=await client.put(b+'/tenant-app',params=q,headers=identity[actor],json=body(p));assert r.status_code==status
    r=await client.put(b+'/tenant-app',params=q,headers=identity['owner'],json=body(p));assert r.status_code==200,r.text
    assert r.headers['cache-control']=='no-store' and r.json()['revision']==1 and r.json()['mode']=='byo'
    assert 'tenant-secret' not in r.text and 'tenant-developer' not in r.text
    assert (await client.put(b+'/tenant-app',params=q,headers=identity['owner'],json=body(p))).status_code==409
    r=await client.get(b+'/tenant-app',params={'workspace_id':other},headers=identity['owner'])
    assert r.json()['mode']=='managed' and r.json()['revision']==0 and r.json()['client_id'].startswith('123' if p=='meta' else 'host')
    async with Session() as db:
        saved=await db.scalar(text('SELECT credential_ciphertext FROM ads_app_configs'))
        assert 'tenant-secret' not in saved
        a=await ads_apps.resolve(db,identity['workspace'],p);bctx=await ads_apps.resolve(db,other,p)
        assert a.binding!=bctx.binding and a.config is not settings() and 'tenant-secret' not in repr(a)
        assert a.config.meta_app_id=='456' if p=='meta' else a.config.google_ads_client_id=='456.apps.googleusercontent.com'


@pytest.mark.parametrize('p',['meta','google'])
async def test_oauth_uses_selected_app_and_rotation_consumes_old_state(client,identity,apps,p,monkeypatch):
    b=base(p);q={'workspace_id':identity['workspace']};headers=identity['owner']
    await client.put(b+'/tenant-app',params=q,headers=headers,json=body(p))
    response=await client.post(b+'/oauth/start',params=q,headers=headers)
    assert response.status_code==200,response.text
    query=parse_qs(urlsplit(response.json()['authorization_url']).query)
    assert query['client_id']==['456' if p=='meta' else '456.apps.googleusercontent.com']
    cookie='pao_meta_state' if p=='meta' else 'pao_google_ads_state'
    token=response.cookies[cookie];state=query['state'][0]
    called=AsyncMock(side_effect=AssertionError('stale callback may not reach provider'))
    monkeypatch.setattr(MetaClient if p=='meta' else GoogleAdsClient,'exchange',called)
    await client.put(b+'/tenant-app',params=q,headers=headers,json=body(p,1,client='789'))
    r=await client.get(b+'/callback',params={'state':state,'code':'old-secret-code'},headers={'Cookie':cookie+'='+token})
    assert r.status_code==400 and 'old-secret-code' not in r.text and not called.called


@pytest.mark.parametrize('p',['meta','google'])
async def test_callback_binding_replay_encrypted_and_managed_host_change(client,identity,apps,p,monkeypatch):
    b=base(p);q={'workspace_id':identity['workspace']};headers=identity['owner']
    await client.put(b+'/tenant-app',params=q,headers=headers,json=body(p))
    seen=[]
    async def exchange(self,code):
        seen.append(self.config.meta_app_secret if p=='meta' else self.config.google_ads_client_secret)
        return ('user-token',3600) if p=='meta' else ('user-refresh',[SCOPE])
    monkeypatch.setattr(MetaClient if p=='meta' else GoogleAdsClient,'exchange',exchange)
    monkeypatch.setattr(MetaClient,'identity',AsyncMock(return_value=('42',['ads_read'])))
    monkeypatch.setattr(GoogleAdsClient,'accessible',AsyncMock(return_value=('access',['1234567890'])))
    response=await client.post(b+'/oauth/start',params=q,headers=headers)
    query=parse_qs(urlsplit(response.json()['authorization_url']).query);cookie='pao_meta_state' if p=='meta' else 'pao_google_ads_state'
    callback={'params':{'state':query['state'][0],'code':'synthetic-code'},'headers':{'Cookie':cookie+'='+response.cookies[cookie]}}
    r=await client.get(b+'/callback',**callback);assert r.status_code==200 and 'thành công' in r.text and seen==['tenant-secret-456']
    assert (await client.get(b+'/callback',**callback)).status_code==400
    async with Session() as db:
        conn=await db.scalar(select(MetaConnection if p=='meta' else GoogleAdsConnection))
        assert conn.app_binding and await ads_apps.valid(db,conn,p)
        assert (conn.token_ciphertext if p=='meta' else conn.refresh_token_ciphertext) not in ('user-token','user-refresh')
    # BYO never silently starts using a different managed host key.
    monkeypatch.setattr(settings(),'meta_app_secret' if p=='meta' else 'google_ads_client_secret','changed-host-key')
    async with Session() as db:
        conn=await db.scalar(select(MetaConnection if p=='meta' else GoogleAdsConnection));assert await ads_apps.valid(db,conn,p)
    await client.put(b+'/tenant-app',params=q,headers=headers,json={'mode':'managed','expected_revision':1,'consent':True})
    async with Session() as db:
        conn=await db.scalar(select(MetaConnection if p=='meta' else GoogleAdsConnection))
        assert conn.status=='disconnected' and not (conn.token_ciphertext if p=='meta' else conn.refresh_token_ciphertext)
        assert not await ads_apps.valid(db,conn,p)


@pytest.mark.parametrize('p',['meta','google'])
async def test_rotation_invalidates_jobs_only_in_own_sme(client,identity,apps,p):
    other=await second(identity);model=MetaConnection if p=='meta' else GoogleAdsConnection;jobmodel=MetaSyncJob if p=='meta' else GoogleAdsSyncJob
    async with Session.begin() as db:
        connections=[]
        for wid in (identity['workspace'],other):
            values={'token_ciphertext':encrypt('token'),'expires_at':now()+timedelta(hours=1)} if p=='meta' else {'refresh_token_ciphertext':encrypt('refresh')}
            row=model(workspace_id=wid,user_id=identity['user_id'],status='connected',scopes=['ads_read'] if p=='meta' else [SCOPE],**values)
            db.add(row);await db.flush();connections.append(row.id)
            db.add(jobmodel(connection_id=row.id,connection_version=row.version,api_version='v26.0' if p=='meta' else 'v25',request_key=str(uuid4()),kind='accounts'))
    await client.put(base(p)+'/tenant-app',params={'workspace_id':identity['workspace']},headers=identity['owner'],json=body(p))
    async with Session() as db:
        a,b=[await db.get(model,i) for i in connections]
        assert a.status=='disconnected' and a.version==2 and b.status=='connected' and b.version==1
        jobs=list(await db.scalars(select(jobmodel).order_by(jobmodel.created_at)))
        assert [j.status for j in jobs]==['cancelled','queued']
    public=await client.get(base(p)+'/connection',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert public.json()['status']=='disconnected' and public.json()['scopes']==[]


@pytest.mark.parametrize('p',['meta','google'])
async def test_secret_validation_never_echoes_and_platform_gate_stays_off(client,identity,apps,p,monkeypatch):
    b=base(p);q={'workspace_id':identity['workspace']};headers=identity['owner']
    r=await client.put(b+'/tenant-app',params=q,headers=headers,json={**body(p),'client_secret':'secret\ninvalid'})
    assert r.status_code==422 and 'secret\ninvalid' not in r.text and 'invalid_input' in r.text
    r=await client.put(b+'/tenant-app',params=q,headers=headers,json={**body(p),'redirect_uri':'https://hostile.test'})
    assert r.status_code==422
    monkeypatch.setattr(settings(),'meta_enabled' if p=='meta' else 'google_ads_enabled',False)
    r=await client.put(b+'/tenant-app',params=q,headers=headers,json=body(p));assert r.status_code==200
    assert not r.json()['configured'] and not r.json()['platform_enabled']
    assert (await client.post(b+'/oauth/start',params=q,headers=headers)).status_code==503


@pytest.mark.parametrize('p',['meta','google'])
async def test_explicit_client_configuration_never_changes_global_credentials(apps,p):
    c=settings().model_copy(deep=True)
    c.meta_app_secret='byo-meta-key';c.google_ads_client_secret='byo-google-key';c.google_ads_developer_token='byo-developer'
    requests=[]
    def http(request):
        requests.append(request)
        if p=='meta':return httpx.Response(200,json={'access_token':'fresh','expires_in':3600})
        return httpx.Response(200,json={'access_token':'fresh'})
    if p=='meta':await MetaClient(config=c,transport=httpx.MockTransport(http)).exchange('code')
    else:await GoogleAdsClient(config=c,transport=httpx.MockTransport(http)).access('refresh')
    assert ('byo-meta-key' if p=='meta' else 'byo-google-key') in requests[0].content.decode()
    assert settings().meta_app_secret=='host-meta-secret' and settings().google_ads_client_secret=='host-google-secret'


@pytest.mark.parametrize('p',['meta','google'])
async def test_real_worker_http_and_same_remote_account_are_tenant_scoped(client,identity,apps,p,monkeypatch):
    import hashlib,hmac
    from pao.models import MetaSnapshot,AdEntity
    from pao.integrations.meta.sync import sync_meta
    from pao.integrations.google_ads.sync import sync_google_ads
    workspaces=[identity['workspace'],await second(identity)]
    jobs=[];connections=[];seen=[]
    for i,wid in enumerate(workspaces):
        r=await client.put(base(p)+'/tenant-app',params={'workspace_id':wid},headers=identity['owner'],json=body(p,client=str(456+i)));assert r.status_code==200
        async with Session.begin() as db:
            app=await ads_apps.resolve(db,wid,p)
            model=MetaConnection if p=='meta' else GoogleAdsConnection
            values={'token_ciphertext':encrypt('token-'+str(i)),'expires_at':now()+timedelta(hours=1)} if p=='meta' else {'refresh_token_ciphertext':encrypt('refresh-'+str(i))}
            row=model(workspace_id=wid,user_id=identity['user_id'],status='connected',scopes=['ads_read'] if p=='meta' else [SCOPE],app_binding=app.binding,**values)
            db.add(row);await db.flush();connections.append(row.id)
        r=await client.post(base(p)+'/sync',headers=identity['owner'],json={'workspace_id':wid,'request_key':str(uuid4()),'kind':'accounts'})
        assert r.status_code==202,r.text;jobs.append(r.json()['id'])
    def http(request):
        seen.append(request)
        assert request.url.host in ('graph.facebook.com','oauth2.googleapis.com','googleads.googleapis.com')
        if p=='meta':
            token=request.headers['authorization'].removeprefix('Bearer ');i=int(token.rsplit('-',1)[1])
            assert request.url.params['appsecret_proof']==hmac.new(('tenant-secret-'+str(456+i)).encode(),token.encode(),hashlib.sha256).hexdigest()
            return httpx.Response(200,json={'data':[{'id':'act_1','name':'SME '+str(i),'account_id':'1','currency':'VND','timezone_name':'Asia/Ho_Chi_Minh'}]})
        if request.url.host=='oauth2.googleapis.com':
            q=parse_qs(request.content.decode());i=int(q['refresh_token'][0].rsplit('-',1)[1]);assert q['client_secret']==['tenant-secret-'+str(456+i)]
            return httpx.Response(200,json={'access_token':'access-'+str(i)})
        i=int(request.headers['authorization'].rsplit('-',1)[1]);assert request.headers['developer-token']=='tenant-developer' and request.headers['login-customer-id']=='2222222222'
        if request.url.path.endswith(':listAccessibleCustomers'):return httpx.Response(200,json={'resourceNames':['customers/1234567890']})
        return httpx.Response(200,json={'results':[{'customer':{'id':'1234567890','descriptiveName':'SME '+str(i),'currencyCode':'VND','timeZone':'Asia/Ho_Chi_Minh','status':'ENABLED'}}]})
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',lambda **kw:httpx.MockTransport(http))
    # httpx._client binds its default transport at import time. Patch that
    # binding too; replacing only the package export does not intercept it.
    from httpx import _client as transport_module
    monkeypatch.setattr(transport_module,'AsyncHTTPTransport',lambda **kw:httpx.MockTransport(http))
    for jid in jobs:await (sync_meta if p=='meta' else sync_google_ads)({},jid)
    async with Session() as db:
        jobmodel=MetaSyncJob if p=='meta' else GoogleAdsSyncJob
        for i,jid in enumerate(jobs):
            job=await db.get(jobmodel,jid);assert job.status=='completed',job.error_code
            if p=='meta':assert (await db.scalar(select(MetaSnapshot).where(MetaSnapshot.job_id==jid))).payload['name']=='SME '+str(i)
            else:assert (await db.scalar(select(AdEntity).where(AdEntity.google_connection_id==connections[i]))).name=='SME '+str(i)
    assert len(seen)==(2 if p=='meta' else 6)


@pytest.mark.parametrize('p',['meta','google'])
async def test_old_client_guard_denies_before_http_after_rotation(client,identity,apps,p):
    q={'workspace_id':identity['workspace']};headers=identity['owner']
    await client.put(base(p)+'/tenant-app',params=q,headers=headers,json=body(p))
    model=MetaConnection if p=='meta' else GoogleAdsConnection
    async with Session.begin() as db:
        app=await ads_apps.resolve(db,identity['workspace'],p)
        values={'token_ciphertext':encrypt('token'),'expires_at':now()+timedelta(hours=1)} if p=='meta' else {'refresh_token_ciphertext':encrypt('refresh')}
        conn=model(workspace_id=identity['workspace'],user_id=identity['user_id'],status='connected',scopes=['ads_read'] if p=='meta' else [SCOPE],app_binding=app.binding,**values)
        db.add(conn);await db.flush()
    calls=[];transport=httpx.MockTransport(lambda r:calls.append(r) or httpx.Response(200,json={}))
    guard=ads_apps.invocation(conn,p,binding=app.binding)
    old=MetaClient('token',config=app.config,guard=guard,transport=transport) if p=='meta' else GoogleAdsClient(config=app.config,guard=guard,transport=transport)
    await client.put(base(p)+'/tenant-app',params=q,headers=headers,json=body(p,1,client='789'))
    with pytest.raises(MetaError if p=='meta' else GoogleAdsError,match='ads_app_binding_changed'):
        if p=='meta':await old._request('me')
        else:await old.access('refresh')
    assert not calls


@pytest.mark.parametrize('p',['meta','google'])
async def test_managed_key_rotation_invalidates_persisted_pin_without_byo_fallback(client,identity,apps,p,monkeypatch):
    model=MetaConnection if p=='meta' else GoogleAdsConnection
    async with Session.begin() as db:
        app=await ads_apps.resolve(db,identity['workspace'],p)
        values={'token_ciphertext':encrypt('token'),'expires_at':now()+timedelta(hours=1)} if p=='meta' else {'refresh_token_ciphertext':encrypt('refresh')}
        conn=model(workspace_id=identity['workspace'],user_id=identity['user_id'],status='connected',scopes=['ads_read'] if p=='meta' else [SCOPE],app_binding=app.binding,**values)
        db.add(conn);await db.flush();cid=conn.id
    monkeypatch.setattr(settings(),'meta_app_secret' if p=='meta' else 'google_ads_client_secret','rotated-host-secret')
    async with Session() as db:
        conn=await db.get(model,cid)
        assert not await ads_apps.valid(db,conn,p) and not await ads_apps.matches(db,conn,p)
    r=await client.get(base(p)+'/connection',params={'workspace_id':identity['workspace']},headers=identity['owner']);assert r.json()['status']=='expired'


@pytest.mark.parametrize('p',['meta','google'])
async def test_legacy_unbound_token_is_not_adopted_silently(client,identity,apps,p):
    model=MetaConnection if p=='meta' else GoogleAdsConnection
    async with Session.begin() as db:
        values={'token_ciphertext':encrypt('old-token'),'expires_at':now()+timedelta(hours=1)} if p=='meta' else {'refresh_token_ciphertext':encrypt('old-refresh')}
        conn=model(workspace_id=identity['workspace'],user_id=identity['user_id'],status='connected',scopes=['ads_read'] if p=='meta' else [SCOPE],**values)
        db.add(conn);await db.flush();cid=conn.id
    async with Session() as db:
        conn=await db.get(model,cid)
        assert not await ads_apps.valid(db,conn,p) and not await ads_apps.matches(db,conn,p)
    result=await client.post(base(p)+'/sync',headers=identity['owner'],json={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'accounts'})
    assert result.status_code==409 and result.json()['detail']=='ads_app_binding_changed'


async def test_single_sme_owner_cannot_read_or_mutate_host_configuration(client,identity,apps,monkeypatch):
    from pao.integrations.meta import app_config
    assert settings().meta_installation_config_enabled is False
    def forbidden(*args,**kwargs):raise AssertionError('SME may not access installer .env path')
    monkeypatch.setattr(app_config,'status',forbidden);monkeypatch.setattr(app_config,'save',forbidden)
    q={'workspace_id':identity['workspace']};path='/v1/integrations/meta/app-config'
    for method in ('get','put'):
        kwargs={} if method=='get' else {'json':{'app_id':'123','app_secret':'synthetic-secret-not-real','api_version':'v26.0','redirect_uri':'http://127.0.0.1:3200/v1/integrations/meta/callback','revision':'0'*64}}
        response=await getattr(client,method)(path,params=q,headers=identity['owner'],**kwargs)
        assert response.status_code==410 and response.json()['detail']=='meta_installation_config_disabled'
