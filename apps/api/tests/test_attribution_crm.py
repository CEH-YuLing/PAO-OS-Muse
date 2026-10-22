from datetime import date,datetime,timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func,select

from pao.db import Session
from pao.models import (AdEntity,AdMetric,AnalyticsEvent,AttributionMetric,AttributionRun,
    AttributionSource,BusinessOrder,CrmLead,CrmStageEvent,MetaSyncJob,TrackingAlert)
from pao.warehouse import ATTRIBUTION
from test_meta import connected,meta

DAY=date(2026,1,8);STAMP='2026-01-08T10:00:00+07:00'

async def seed_ads(identity):
    cid=await connected(identity)
    async with Session.begin() as db:
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='historical',account_id='act_1',since=str(DAY),until=str(DAY),status='completed',warehouse=True,granularity='daily')
        db.add(job);await db.flush();common=dict(connection_id=cid,connection_version=1,account_id='act_1',currency='USD',timezone='Asia/Ho_Chi_Minh',source_job_id=job.id)
        db.add_all([AdEntity(**common,kind='account',remote_id='act_1',name='Attribution QA'),AdEntity(**common,kind='campaign',remote_id='10',name='Cheap leads'),AdEntity(**common,kind='campaign',remote_id='20',name='Valuable leads'),
            AdMetric(**common,level='campaign',entity_id='10',day=DAY,hour=-1,granularity='daily',attribution=ATTRIBUTION,spend=Decimal('400'),purchase=Decimal('100'),revenue=Decimal('1000'),impressions=10000,clicks=500),
            AdMetric(**common,level='campaign',entity_id='20',day=DAY,hour=-1,granularity='daily',attribution=ATTRIBUTION,spend=Decimal('490'),purchase=Decimal('20'),revenue=Decimal('2000'),impressions=9000,clicks=450)])

async def source(client,identity,kind):
    result=await client.post('/v1/attribution/sources',json={'workspace_id':identity['workspace'],'account_id':'act_1','kind':kind,'name':f'QA {kind}'},headers=identity['owner'])
    assert result.status_code==201,result.text;return result.json()['id']

async def ingest(client,identity):
    ga4=await source(client,identity,'ga4');crm=await source(client,identity,'crm');orders=await source(client,identity,'orders')
    events=[]
    for campaign,sessions,forms,purchases in [('10',100,10,5),('20',100,20,20)]:
        events += [{'external_id':f'{campaign}-s-{i}','occurred_at':STAMP,'event_name':'session','campaign_id':campaign} for i in range(sessions)]
        events += [{'external_id':f'{campaign}-f-{i}','occurred_at':STAMP,'event_name':'form_submit','campaign_id':campaign} for i in range(forms)]
        events += [{'external_id':f'{campaign}-p-{i}','occurred_at':STAMP,'event_name':'purchase','campaign_id':campaign,'value':'100','currency':'USD'} for i in range(purchases)]
    result=await client.post(f'/v1/attribution/sources/{ga4}/analytics',params={'workspace_id':identity['workspace']},json={'rows':events},headers=identity['owner'])
    assert result.status_code==200 and result.json()['inserted']==255
    repeat=await client.post(f'/v1/attribution/sources/{ga4}/analytics',params={'workspace_id':identity['workspace']},json={'rows':events},headers=identity['owner'])
    assert repeat.json()['unchanged']==255
    leads=[]
    for campaign,count in [('10',100),('20',70)]:leads += [{'external_id':f'L{campaign}-{i}','acquired_at':STAMP,'campaign_id':campaign} for i in range(count)]
    assert (await client.post(f'/v1/attribution/sources/{crm}/leads',params={'workspace_id':identity['workspace']},json={'rows':leads},headers=identity['owner'])).json()['inserted']==170
    stages=[]
    for campaign,count in [('10',5),('20',20)]:stages += [{'external_id':f'S{campaign}-{i}','lead_external_id':f'L{campaign}-{i}','stage':'sale','occurred_at':'2026-01-08T12:00:00+07:00'} for i in range(count)]
    assert (await client.post(f'/v1/attribution/sources/{crm}/stages',params={'workspace_id':identity['workspace']},json={'rows':stages},headers=identity['owner'])).json()['inserted']==25
    rows=[]
    for campaign,count in [('10',5),('20',20)]:rows += [{'external_id':f'O{campaign}-{i}','version':0,'occurred_at':STAMP,'status':'paid','revenue':'100','currency':'USD','lead_external_id':f'L{campaign}-{i}','attribution_method':'lead_link'} for i in range(count)]
    assert (await client.post(f'/v1/attribution/sources/{orders}/orders',params={'workspace_id':identity['workspace']},json={'rows':rows},headers=identity['owner'])).json()['inserted']==25
    return ga4,crm,orders

def analysis(identity,key=None):return {'workspace_id':identity['workspace'],'account_id':'act_1','period_start':str(DAY),'period_end':str(DAY),'request_key':key or str(uuid4()),'discrepancy_threshold_pct':'25'}

async def test_business_value_tracking_and_idempotency(client,identity,meta):
    await seed_ads(identity);await ingest(client,identity);key=str(uuid4());body=analysis(identity,key)
    result=await client.post('/v1/attribution/analyze',json=body,headers=identity['owner']);assert result.status_code==201,result.text
    data=result.json();assert data['read_only'] is True and data['run']['summary']['optimization_blocked'] is True
    cheap=next(x for x in data['metrics'] if x['campaign_id']=='10');valuable=next(x for x in data['metrics'] if x['campaign_id']=='20')
    assert cheap['cpl']=='4.000000' and valuable['cpl']=='7.000000'
    assert cheap['cac']=='80.000000' and valuable['cac']=='24.500000';assert valuable['actual_revenue']=='2000.000000'
    assert cheap['tracking_status']=='unhealthy' and cheap['purchase_discrepancy_pct']=='1900.000000'
    assert valuable['tracking_status']=='healthy' and valuable['landing_cvr']=='20.000000'
    assert len(data['alerts'])==1 and data['alerts'][0]['campaign_id']=='10'
    report=await client.post('/v1/reports',json={'workspace_id':identity['workspace'],'account_id':'act_1','kind':'daily','period_end':str(DAY),'request_key':str(uuid4())},headers=identity['owner'])
    assert report.status_code==201 and report.json()['report']['comparison']['business']['actual_orders']==25
    assert report.json()['report']['comparison']['business']['cac']=='35.600000'
    repeated=await client.post('/v1/attribution/analyze',json=body,headers=identity['owner']);assert repeated.json()['run']['id']==data['run']['id']
    assert (await client.post('/v1/attribution/analyze',json={**body,'period_start':'2026-01-07'},headers=identity['owner'])).status_code==409
    ack=await client.post(f"/v1/attribution/alerts/{data['alerts'][0]['id']}/acknowledge",params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert ack.status_code==200 and ack.json()['acknowledged'] is True
    assert (await client.get('/v1/attribution/dashboard',params={'workspace_id':identity['workspace'],'account_id':'act_1'},headers=identity['outsider'])).status_code==404
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AttributionSource))==3
        assert await db.scalar(select(func.count()).select_from(AnalyticsEvent))==255
        assert await db.scalar(select(func.count()).select_from(CrmLead))==170
        assert await db.scalar(select(func.count()).select_from(CrmStageEvent))==195
        assert await db.scalar(select(func.count()).select_from(BusinessOrder))==25
        assert await db.scalar(select(func.count()).select_from(AttributionMetric))==2

async def test_ingestion_conflicts_currency_and_rbac(client,identity,meta):
    await seed_ads(identity);ga4=await source(client,identity,'ga4');orders=await source(client,identity,'orders')
    event={'external_id':'event-1','occurred_at':STAMP,'event_name':'purchase','campaign_id':'10','value':'5','currency':'USD'}
    assert (await client.post(f'/v1/attribution/sources/{ga4}/analytics',params={'workspace_id':identity['workspace']},json={'rows':[event]},headers=identity['owner'])).status_code==200
    conflict={**event,'value':'6'}
    assert (await client.post(f'/v1/attribution/sources/{ga4}/analytics',params={'workspace_id':identity['workspace']},json={'rows':[conflict]},headers=identity['owner'])).status_code==409
    wrong={'external_id':'o1','version':0,'occurred_at':STAMP,'status':'paid','revenue':'10','currency':'VND','attribution_method':'unattributed'}
    assert (await client.post(f'/v1/attribution/sources/{orders}/orders',params={'workspace_id':identity['workspace']},json={'rows':[wrong]},headers=identity['owner'])).status_code==422
    assert (await client.post(f'/v1/attribution/sources/{ga4}/analytics',params={'workspace_id':identity['workspace']},json={'rows':[event]},headers=identity['other'])).status_code==403
    pii={**event,'external_id':'event-2','visitor_ref_hash':'not-a-hash'}
    assert (await client.post(f'/v1/attribution/sources/{ga4}/analytics',params={'workspace_id':identity['workspace']},json={'rows':[pii]},headers=identity['owner'])).status_code==422

async def test_tracking_health_blocks_performance_recommendation(client,identity,meta):
    await seed_ads(identity);await ingest(client,identity)
    assert (await client.post('/v1/attribution/analyze',json=analysis(identity),headers=identity['owner'])).status_code==201
    target={'workspace_id':identity['workspace'],'account_id':'act_1','target_cpa':'1','target_roas':'1','minimum_spend':'1','minimum_impressions':1,'minimum_clicks':1,'minimum_conversions':1,'minimum_run_days':1,'freshness_minutes':10080}
    assert (await client.put('/v1/ads/targets',json=target,headers=identity['owner'])).status_code==200
    body={'workspace_id':identity['workspace'],'account_id':'act_1','as_of':str(DAY),'granularity':'daily','hour':None,'request_key':str(uuid4())}
    result=await client.post('/v1/ads/intelligence/analyze',json=body,headers=identity['owner']);assert result.status_code==201,result.text
    rec=next(x for x in result.json()['recommendations'] if x['resource_id']=='10')
    assert 'TRACKING_UNHEALTHY' in rec['reason_codes'] and 'tracking_health' in rec['proposed_action']['blocked_by']
    assert Decimal(rec['confidence'])<=Decimal('.3')

async def test_order_can_link_to_lead_acquired_before_reporting_cohort(client,identity,meta):
    await seed_ads(identity);crm=await source(client,identity,'crm');orders=await source(client,identity,'orders')
    old={'external_id':'historic-lead','acquired_at':'2025-12-01T10:00:00+07:00','campaign_id':'20'}
    assert (await client.post(f'/v1/attribution/sources/{crm}/leads',params={'workspace_id':identity['workspace']},json={'rows':[old]},headers=identity['owner'])).status_code==200
    order={'external_id':'current-order','version':0,'occurred_at':STAMP,'status':'paid','revenue':'250','currency':'USD','lead_external_id':'historic-lead','attribution_method':'lead_link'}
    assert (await client.post(f'/v1/attribution/sources/{orders}/orders',params={'workspace_id':identity['workspace']},json={'rows':[order]},headers=identity['owner'])).status_code==200
    result=await client.post('/v1/attribution/analyze',json=analysis(identity),headers=identity['owner']);assert result.status_code==201,result.text
    valuable=next(x for x in result.json()['metrics'] if x['campaign_id']=='20')
    assert valuable['leads']==0 and valuable['actual_orders']==1 and valuable['actual_revenue']=='250.000000'
