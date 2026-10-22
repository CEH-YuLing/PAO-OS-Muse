from datetime import timedelta
from urllib.parse import parse_qs,urlsplit
from uuid import uuid4
from unittest.mock import AsyncMock
import httpx,pytest
from cryptography.fernet import Fernet
from sqlalchemy import func,select
from pao.config import settings
from pao.db import Session
from pao.models import AdEntity,AdMetric,GoogleAdsConnection,GoogleAdsSyncJob,now
from pao.integrations.google_ads.api import CALLBACK,COOKIE
from pao.integrations.google_ads.client import GoogleAdsClient,GoogleAdsError,SCOPE,encrypt,decrypt
from pao.integrations.google_ads.sync import sync_google_ads
BASE='/v1/integrations/google-ads'
@pytest.fixture
def google_ads(monkeypatch):
    values={'google_ads_enabled':True,'google_ads_client_id':'client.apps.googleusercontent.com','google_ads_client_secret':'synthetic-secret','google_ads_api_version':'v25','google_ads_redirect_uri':'https://test'+CALLBACK,'google_ads_login_customer_id':'','google_ads_developer_token':'','integration_encryption_key':Fernet.generate_key().decode()}
    for key,value in values.items():monkeypatch.setattr(settings(),key,value)
async def connected(identity):
    async with Session.begin() as db:
        from pao.integrations import ads_apps
        app_context=await ads_apps.resolve(db,identity['workspace'],'google')
        row=GoogleAdsConnection(workspace_id=identity['workspace'],user_id=identity['user_id'],refresh_token_ciphertext=encrypt('refresh'),scopes=[SCOPE],connected_at=now(),status='connected',app_binding=app_context.binding);db.add(row);await db.flush();return row.id
@pytest.mark.parametrize('actor,code',[('owner',200),('other',403),('outsider',404)])
async def test_google_oauth_access(client,identity,google_ads,actor,code):
    result=await client.post(BASE+'/oauth/start',params={'workspace_id':identity['workspace']},headers=identity[actor]);assert result.status_code==code
    if code==200:
        query=parse_qs(urlsplit(result.json()['authorization_url']).query);assert query['scope']==[SCOPE] and query['access_type']==['offline'] and query['prompt']==['consent']
async def test_google_oauth_encrypted_replay_safe(client,identity,google_ads,monkeypatch):
    monkeypatch.setattr(GoogleAdsClient,'exchange',AsyncMock(return_value=('refresh-secret',[SCOPE])));monkeypatch.setattr(GoogleAdsClient,'accessible',AsyncMock(return_value=('access',['1234567890'])))
    start=await client.post(BASE+'/oauth/start',params={'workspace_id':identity['workspace']},headers=identity['owner']);state=parse_qs(urlsplit(start.json()['authorization_url']).query)['state'][0];cookie=start.cookies[COOKIE]
    result=await client.get(CALLBACK,params={'state':state,'code':'code'},headers={'Cookie':COOKIE+'='+cookie});assert result.status_code==200 and 'refresh-secret' not in result.text
    assert (await client.get(CALLBACK,params={'state':state,'code':'code'},headers={'Cookie':COOKIE+'='+cookie})).status_code==400
    async with Session() as db:
        row=await db.scalar(select(GoogleAdsConnection));assert decrypt(row.refresh_token_ciphertext)=='refresh-secret'
async def test_google_transport_read_only_and_no_legacy_token(google_ads):
    requests=[]
    def handler(request):
        requests.append(request);assert request.url.host in ('oauth2.googleapis.com','googleads.googleapis.com');assert 'developer-token' not in request.headers
        if request.url.host=='oauth2.googleapis.com':return httpx.Response(200,json={'access_token':'access'})
        if request.method=='GET':return httpx.Response(200,json={'resourceNames':['customers/1234567890']})
        assert request.method=='POST' and request.url.path.endswith('/googleAds:search');return httpx.Response(200,json={'results':[]})
    c=GoogleAdsClient(transport=httpx.MockTransport(handler));token,ids=await c.accessible('refresh');assert token=='access' and ids==['1234567890'];assert [x async for x in c.search(token,ids[0],'SELECT customer.id FROM customer')]==[]
    with pytest.raises(GoogleAdsError):await c.request('POST','https://googleads.googleapis.com/v25/customers/1234567890/googleAds:search',json_body={'query':'MUTATE campaign'})
    with pytest.raises(GoogleAdsError):await c.request('GET','https://hostile.test')
async def test_google_sync_normalizes_shared_warehouse(client,identity,google_ads,monkeypatch):
    await connected(identity)
    monkeypatch.setattr(GoogleAdsClient,'accessible',AsyncMock(return_value=('access',['1234567890'])))
    async def search(self,token,customer,query):
        if 'FROM customer' in query:yield {'customer':{'id':'1234567890','descriptiveName':'Google QA','currencyCode':'USD','timeZone':'Asia/Ho_Chi_Minh','status':'ENABLED','manager':False}}
        elif 'FROM campaign' in query and 'metrics.' not in query:yield {'campaign':{'id':'10','name':'Search QA','status':'ENABLED','advertisingChannelType':'SEARCH'}}
        elif 'FROM ad_group' in query and 'FROM ad_group_ad' not in query and 'metrics.' not in query:yield {'campaign':{'id':'10'},'adGroup':{'id':'20','name':'Group QA','status':'ENABLED'}}
        elif 'FROM ad_group_ad' in query and 'metrics.' not in query:yield {'campaign':{'id':'10'},'adGroup':{'id':'20'},'adGroupAd':{'ad':{'id':'30'},'status':'ENABLED'}}
        elif 'metrics.' in query:
            base={'campaign':{'id':'10'},'segments':{'date':'2026-01-08'},'metrics':{'costMicros':'2500000','impressions':'100','clicks':'10','conversions':'2','conversionsValue':'8'}}
            if 'FROM ad_group' in query and 'FROM ad_group_ad' not in query:base['adGroup']={'id':'20'}
            if 'FROM ad_group_ad' in query:base['adGroup']={'id':'20'};base['adGroupAd']={'ad':{'id':'30'}}
            yield base
    monkeypatch.setattr(GoogleAdsClient,'search',search)
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'accounts'};result=await client.post(BASE+'/sync',json=body,headers=identity['owner']);assert result.status_code==202;await sync_google_ads({},result.json()['id'])
    accounts=await client.get(BASE+'/accounts',params={'workspace_id':identity['workspace']},headers=identity['owner']);assert accounts.json()[0]['id']=='1234567890'
    historical={**body,'request_key':str(uuid4()),'kind':'historical','account_id':'1234567890','since':'2026-01-08','until':'2026-01-08'};result=await client.post(BASE+'/sync',json=historical,headers=identity['owner']);assert result.status_code==202;await sync_google_ads({},result.json()['id'])
    query={'workspace_id':identity['workspace'],'account_id':'1234567890','since':'2026-01-08','until':'2026-01-08','level':'campaign','granularity':'daily'};metrics=(await client.get(BASE+'/metrics',params=query,headers=identity['owner'])).json();assert metrics[0]['spend']=='2.500000' and metrics[0]['conversions']=='2.000000' and metrics[0]['roas']=='3.200000'
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AdEntity))==4 and await db.scalar(select(func.count()).select_from(AdMetric))==3
        row=await db.scalar(select(AdMetric).where(AdMetric.level=='campaign'));assert row.platform=='google' and row.connection_id is None and row.google_connection_id
