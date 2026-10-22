from datetime import date,timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import select,func
from pao.db import Session
from pao.models import MetaSyncJob,MetaSnapshot,AdMetric,AdEntity,AdSyncSchedule,MetaConnection,now
from pao.warehouse import normalize_metric,number,HOUR
from pao.warehouse_api import schedule_warehouse
from pao.integrations.meta.client import MetaClient,MetaError
from pao.integrations.meta.sync import sync_meta
from test_meta import meta,connected


def job(grain='daily'):
    return SimpleNamespace(id=str(uuid4()),connection_id=str(uuid4()),connection_version=1,account_id='act_1',
        since='2026-01-01',until='2026-01-02',granularity=grain)


def insight(level='ad',day='2026-01-01'):
    result={'account_id':'1','account_currency':'VND','campaign_id':'10','date_start':day,'date_stop':day,
        'spend':'0.3','impressions':'100','clicks':'2','reach':'80','inline_link_clicks':'1',
        'actions':[{'action_type':'purchase','value':'2'},{'action_type':'offsite_conversion.fb_pixel_purchase','value':'2'}],
        'action_values':[{'action_type':'purchase','value':'0.9'}]}
    if level in ('adset','ad'):result['adset_id']='20'
    if level=='ad':result['ad_id']='30'
    return result


ACCOUNT={'id':'act_1','account_id':'1','name':'QA account','currency':'VND','timezone_name':'Asia/Ho_Chi_Minh'}


def test_decimal_aliases_and_derived_metrics():
    row=normalize_metric(insight(),job(),ACCOUNT,'ad')
    assert row['spend']==Decimal('0.3') and row['purchase']==2 and row['roas']==3 and row['cpc']==Decimal('.15')
    assert row['frequency']==Decimal('1.25') and row['ctr']==2 and row['leads'] is None


def test_zero_missing_and_hourly():
    payload=insight();payload.update(spend='0',clicks='0',impressions='0',actions=[]);payload[HOUR]='23:00:00 - 23:59:59'
    row=normalize_metric(payload,job('hourly'),ACCOUNT,'ad')
    assert row['spend']==0 and row['cpc'] is None and row['roas'] is None
    assert row['purchase'] is None and row['reach'] is None and row['frequency'] is None and row['hour']==23


@pytest.mark.parametrize('value',['NaN','Infinity','-1','1e30',True])
def test_invalid_numeric(value):
    with pytest.raises(MetaError):number(value)


@pytest.mark.parametrize('change',[{'date_stop':'2026-01-02'},{'account_id':'9'},{'account_currency':'USD'},{'ad_id':'bad'},{'date_start':'2025-01-01'}])
def test_invalid_scope_date_currency(change):
    with pytest.raises(MetaError):normalize_metric({**insight(),**change},job(),ACCOUNT,'ad')


async def test_hourly_transport(meta):
    def handler(req):
        assert req.method=='GET' and req.url.params['level']=='campaign'
        assert req.url.params['breakdowns']==HOUR and req.url.params['time_increment']=='1'
        assert 'reach' not in req.url.params['fields']
        assert req.url.params['action_attribution_windows']=='["7d_click", "1d_view"]'
        return httpx.Response(200,json={'data':[{**insight('campaign'),HOUR:'01:00:00 - 01:59:59'}]})
    client=MetaClient('test',transport=httpx.MockTransport(handler))
    rows=[r async for r in client.rows('insights','act_1','2026-01-01','2026-01-01',level='campaign',granularity='hourly',warehouse=True)]
    assert rows[0][HOUR].startswith('01:')


async def prepare(identity,client):
    cid=await connected(identity)
    async with Session.begin() as db:
        j=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='accounts',status='completed')
        db.add(j);await db.flush();db.add(MetaSnapshot(job_id=j.id,kind='accounts',remote_key='act_1',payload=ACCOUNT))
    return cid


def provider(monkeypatch,days=('2026-01-01','2026-01-02'),fail=False):
    async def rows(self,kind,account=None,since=None,until=None,**kwargs):
        if kind=='accounts':yield ACCOUNT
        elif kind=='campaigns':yield {'id':'10','account_id':'1','name':'Campaign','status':'ACTIVE'}
        elif kind=='adsets':yield {'id':'20','account_id':'1','campaign_id':'10','name':'Adset'}
        elif kind=='ads':yield {'id':'30','account_id':'1','campaign_id':'10','adset_id':'20','creative':{'id':'40','name':'Creative'}}
        elif kind=='insights':
            for day in days:
                if since<=day<=until:
                    p=insight(kwargs['level'],day)
                    if kwargs['granularity']=='hourly':p[HOUR]='01:00:00 - 01:59:59'
                    yield p
            if fail:raise MetaError('meta_rate_limited')
    monkeypatch.setattr(MetaClient,'rows',rows)


async def submit(client,identity,grain='daily',since='2026-01-01',until='2026-01-02'):
    result=await client.post('/v1/integrations/meta/sync',headers=identity['owner'],json={'workspace_id':identity['workspace'],
        'request_key':str(uuid4()),'kind':'historical','account_id':'act_1','since':since,'until':until,'warehouse':True,'granularity':grain})
    assert result.status_code==202,result.text
    await sync_meta({},result.json()['id']);return result.json()['id']


async def test_warehouse_restatement_grains_scope_and_api(client,identity,meta,monkeypatch):
    cid=await prepare(identity,client);provider(monkeypatch)
    jid=await submit(client,identity)
    async with Session() as db:
        assert (await db.get(MetaSyncJob,jid)).status=='completed'
        assert await db.scalar(select(func.count()).select_from(AdMetric))==6
        assert await db.scalar(select(func.count()).select_from(AdEntity))==5
    await submit(client,identity,'hourly')
    provider(monkeypatch,days=('2026-01-02',))
    await submit(client,identity)
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(AdMetric))==9
    query={'workspace_id':identity['workspace'],'account_id':'act_1','since':'2026-01-01','until':'2026-01-02'}
    result=await client.get('/v1/warehouse/metrics',params=query,headers=identity['owner'])
    assert result.status_code==200 and len(result.json()['rows'])==1
    assert result.json()['rows'][0]['spend']=='0.300000'
    assert (await client.get('/v1/warehouse/metrics',params=query,headers=identity['other'])).json()['rows']==[]
    assert (await client.get('/v1/warehouse/metrics',params=query,headers=identity['outsider'])).status_code==404
    provider(monkeypatch,fail=True);failed=await submit(client,identity)
    async with Session() as db:
        assert (await db.get(MetaSyncJob,failed)).status=='failed'
        assert await db.scalar(select(func.count()).select_from(AdMetric))==9
    await client.delete('/v1/integrations/meta/connection',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert (await client.get('/v1/warehouse/metrics',params=query,headers=identity['owner'])).json()['rows']==[]


async def test_schedule_idempotent_and_revoke(client,identity,meta,monkeypatch):
    cid=await prepare(identity,client);provider(monkeypatch);await submit(client,identity)
    body={'workspace_id':identity['workspace'],'account_id':'act_1','enabled':True,'interval_minutes':15,'lookback_days':3}
    assert (await client.put('/v1/warehouse/schedules',json=body,headers=identity['other'])).status_code==403
    result=await client.put('/v1/warehouse/schedules',json=body,headers=identity['owner']);assert result.status_code==200,result.text
    sid=result.json()['id']
    async with Session.begin() as db:(await db.get(AdSyncSchedule,sid)).next_at=now()-timedelta(seconds=1)
    await schedule_warehouse({});await schedule_warehouse({})
    async with Session.begin() as db:
        jobs=list(await db.scalars(select(MetaSyncJob).where(MetaSyncJob.status=='queued')))
        assert len(jobs)==1 and jobs[0].warehouse and jobs[0].granularity=='daily'
        (await db.get(MetaConnection,cid)).version+=1
        (await db.get(AdSyncSchedule,sid)).next_at=now()-timedelta(seconds=1)
    await schedule_warehouse({})
    async with Session() as db:assert not (await db.get(AdSyncSchedule,sid)).enabled
