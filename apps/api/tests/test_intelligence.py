from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from pao.db import Session
from pao.models import (AdAnomaly, AdEntity, AdIntelligenceRun, AdMetric,
                        AdRecommendation, AdRule, MetaSyncJob)
from pao.warehouse import ATTRIBUTION
from pao.intelligence import schedule_intelligence
from test_meta import connected, meta


async def seed(identity, points):
    cid=await connected(identity)
    async with Session.begin() as db:
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),
            kind='historical',account_id='act_1',since=min(x[0] for x in points).isoformat(),until=max(x[0] for x in points).isoformat(),
            status='completed',warehouse=True,granularity='daily')
        db.add(job);await db.flush()
        common=dict(connection_id=cid,connection_version=1,account_id='act_1',currency='VND',timezone='Asia/Ho_Chi_Minh',source_job_id=job.id)
        db.add_all([AdEntity(**common,kind='account',remote_id='act_1',name='Intelligence QA'),
            AdEntity(**common,kind='campaign',remote_id='10',name='Campaign 10',parent_id='act_1')])
        for day,spend,purchases,revenue in points:
            db.add(AdMetric(**common,level='campaign',entity_id='10',day=day,hour=-1,granularity='daily',attribution=ATTRIBUTION,
                spend=Decimal(spend),revenue=Decimal(revenue),purchase=Decimal(purchases),impressions=2000,clicks=100))
    return cid


def target(identity,**changes):
    payload={'workspace_id':identity['workspace'],'account_id':'act_1','target_cpa':'10','target_roas':'2',
        'minimum_spend':'10','minimum_impressions':1000,'minimum_clicks':20,'minimum_conversions':2,
        'minimum_run_days':3,'freshness_minutes':180}
    return {**payload,**changes}


def analysis(identity,day,key=None):
    return {'workspace_id':identity['workspace'],'account_id':'act_1','as_of':day.isoformat(),'granularity':'daily',
        'hour':None,'request_key':key or str(uuid4())}


async def test_targets_rules_rbac_and_scope(client,identity,meta):
    await seed(identity,[(date(2026,1,6),'10','2','40')])
    assert (await client.put('/v1/ads/targets',json=target(identity),headers=identity['other'])).status_code==403
    made=await client.put('/v1/ads/targets',json=target(identity),headers=identity['owner'])
    assert made.status_code==200 and Decimal(made.json()['target_cpa'])==Decimal('10')
    rows=(await client.get('/v1/ads/rules',params={'workspace_id':identity['workspace'],'account_id':'act_1'},headers=identity['owner'])).json()
    assert {row['code'] for row in rows}=={'NO_PURCHASE_AFTER_TARGET_SPEND','CPA_ABOVE_TARGET','ROAS_ABOVE_TARGET_STABLE'}
    disabled=await client.put(f"/v1/ads/rules/{rows[0]['id']}",params={'workspace_id':identity['workspace']},json={'enabled':False},headers=identity['owner'])
    assert disabled.status_code==200 and not disabled.json()['enabled']
    assert (await client.get('/v1/ads/targets',params={'workspace_id':identity['workspace']},headers=identity['other'])).json()==[]
    invalid=target(identity,target_cpa=None,target_roas=None)
    assert (await client.put('/v1/ads/targets',json=invalid,headers=identity['owner'])).status_code==422


async def test_anomaly_recommendation_lineage_dedup_and_lifecycle(client,identity,meta):
    current=date(2026,2,3)
    points=[(current-timedelta(days=7*n),'10','2','40') for n in range(1,5)]
    points.append((current,'30','0','0'))
    await seed(identity,points)
    await client.put('/v1/ads/targets',json=target(identity),headers=identity['owner'])
    key=str(uuid4());payload=analysis(identity,current,key)
    result=await client.post('/v1/ads/intelligence/analyze',json=payload,headers=identity['owner'])
    assert result.status_code==201,result.text
    data=result.json();assert data['run']['analyst_version']=='performance-analyst-v1'
    assert data['run']['summary']['campaigns_analyzed']==1
    kinds={row['kind'] for row in data['anomalies']}
    assert {'SPEND_ANOMALY','ROAS_COLLAPSE','CONVERSION_DISAPPEARANCE'}<=kinds
    pause=next(row for row in data['recommendations'] if row['type']=='pause_review')
    assert pause['confidence']=='0.9000' and pause['reason_codes']==['NO_PURCHASE_AFTER_TARGET_SPEND']
    assert pause['proposed_action']['executable'] is False
    assert pause['source']['table']=='ad_metrics' and pause['source']['attribution']==ATTRIBUTION
    repeated=await client.post('/v1/ads/intelligence/analyze',json=payload,headers=identity['owner'])
    assert repeated.status_code==201 and repeated.json()['run']['id']==data['run']['id']
    assert (await client.post('/v1/ads/intelligence/analyze',json={**payload,'as_of':'2026-02-02'},headers=identity['owner'])).status_code==409
    alerts=(await client.get('/v1/ads/anomalies',params={'workspace_id':identity['workspace'],'account_id':'act_1'},headers=identity['owner'])).json()
    ack=await client.post(f"/v1/ads/anomalies/{alerts[0]['id']}/acknowledge",params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert ack.status_code==200 and ack.json()['acknowledged']
    dismissed=await client.post(f"/v1/ads/recommendations/{pause['id']}/dismiss",params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert dismissed.status_code==200 and dismissed.json()['status']=='dismissed'
    rerun=await client.post('/v1/ads/intelligence/analyze',json=analysis(identity,current),headers=identity['owner'])
    assert rerun.status_code==201 and rerun.json()['recommendations']==[]
    assert (await client.get('/v1/ads/recommendations',params={'workspace_id':identity['workspace'],'account_id':'act_1'},headers=identity['other'])).json()==[]
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AdIntelligenceRun))==2
        assert await db.scalar(select(func.count()).select_from(AdRule))==3


async def test_low_sample_guardrail_and_finished_period(client,identity,meta):
    day=date(2026,1,8);await seed(identity,[(day,'5','0','0')])
    await client.put('/v1/ads/targets',json=target(identity,minimum_spend='100',minimum_impressions=10000,minimum_clicks=1000),headers=identity['owner'])
    result=await client.post('/v1/ads/intelligence/analyze',json=analysis(identity,day),headers=identity['owner'])
    assert result.status_code==201
    recommendation=result.json()['recommendations'][0]
    assert recommendation['type']=='collect_more_data' and recommendation['reason_codes']==['LOW_SAMPLE_SIZE']
    from pao.models import now
    today=now().date()
    assert (await client.post('/v1/ads/intelligence/analyze',json=analysis(identity,today),headers=identity['owner'])).status_code==422


async def test_analysis_requires_target_and_data(client,identity,meta):
    day=date(2026,1,8);await seed(identity,[(day,'10','1','20')])
    missing=await client.post('/v1/ads/intelligence/analyze',json=analysis(identity,day),headers=identity['owner'])
    assert missing.status_code==409 and missing.json()['detail']=='intelligence_target_required'
    await client.put('/v1/ads/targets',json=target(identity),headers=identity['owner'])
    empty=await client.post('/v1/ads/intelligence/analyze',json=analysis(identity,date(2026,1,7)),headers=identity['owner'])
    assert empty.status_code==409 and empty.json()['detail']=='intelligence_data_unavailable'


async def test_worker_analyzes_new_complete_slot_once(client,identity,meta):
    day=date(2026,1,8);await seed(identity,[(day,'30','0','0')])
    await client.put('/v1/ads/targets',json=target(identity),headers=identity['owner'])
    await schedule_intelligence({});await schedule_intelligence({})
    async with Session() as db:
        runs=list(await db.scalars(select(AdIntelligenceRun)))
        assert len(runs)==1 and runs[0].request_key.startswith('intelligence-auto:')
