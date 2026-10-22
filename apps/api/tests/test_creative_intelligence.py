from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select

from pao.db import Session
from pao.models import (AdEntity, AdMetric, CreativeAnalysisRun, CreativeLearning,
    CreativeMetadata, MetaSyncJob)
from pao.warehouse import ATTRIBUTION
from test_meta import connected, meta

async def seed(identity):
    cid=await connected(identity);end=date(2026,2,10);start=end-timedelta(days=5)
    async with Session.begin() as db:
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='historical',
            account_id='act_1',since=start.isoformat(),until=end.isoformat(),status='completed',warehouse=True,granularity='daily')
        db.add(job);await db.flush();common=dict(connection_id=cid,connection_version=1,account_id='act_1',currency='VND',timezone='Asia/Ho_Chi_Minh',source_job_id=job.id)
        old=datetime(2026,1,1,tzinfo=timezone.utc)
        db.add_all([AdEntity(**common,kind='account',remote_id='act_1',name='Creative QA'),
            AdEntity(**common,kind='creative',remote_id='40',name='Fatigued',created_at=old),AdEntity(**common,kind='creative',remote_id='41',name='Winner',created_at=old),
            AdEntity(**common,kind='ad',remote_id='30',name='Ad 30',creative_id='40'),AdEntity(**common,kind='ad',remote_id='31',name='Ad 31',creative_id='41')])
        for offset in range(6):
            day=start+timedelta(days=offset);current=offset>=3
            db.add(AdMetric(**common,level='ad',entity_id='30',day=day,hour=-1,granularity='daily',attribution=ATTRIBUTION,
                spend=Decimal('20' if current else '10'),impressions=2000 if current else 1000,reach=1000,
                clicks=40 if current else 100,purchase=Decimal('1' if current else '2'),revenue=Decimal('20' if current else '40')))
            db.add(AdMetric(**common,level='ad',entity_id='31',day=day,hour=-1,granularity='daily',attribution=ATTRIBUTION,
                spend=Decimal('10'),impressions=1000,reach=900,clicks=120,purchase=Decimal('3'),revenue=Decimal('60')))
    return end

def payload(identity,end,key=None):
    return {'workspace_id':identity['workspace'],'account_id':'act_1','as_of':end.isoformat(),'request_key':key or str(uuid4()),
        'current_days':3,'baseline_days':3,'minimum_impressions':1000,'minimum_age_days':7,'saturation_impressions':3000,
        'frequency_rise_pct':'20','ctr_decline_pct':'20','cpa_increase_pct':'20','cpm_stable_pct':'15'}

async def test_fatigue_metadata_learning_and_idempotency(client,identity,meta):
    end=await seed(identity);key=str(uuid4());body=payload(identity,end,key)
    result=await client.post('/v1/creatives/analyze',json=body,headers=identity['owner'])
    assert result.status_code==201,result.text;data=result.json();assert data['read_only'] is True and len(data['creatives'])==2
    tired=next(x for x in data['creatives'] if x['asset']['creative_id']=='40')
    assert tired['feature']['fatigue_status']=='fatigued';assert tired['feature']['signals']['independent_signal_count']>=3
    assert tired['feature']['strategy_brief']['requirements']=={'hooks':5,'angles':3,'ctas':2}
    assert len(tired['feature']['strategy_brief']['hooks'])==5 and tired['feature']['strategy_brief']['requires_human_review'] is True
    repeated=await client.post('/v1/creatives/analyze',json=body,headers=identity['owner'])
    assert repeated.status_code==201 and repeated.json()['run']['id']==data['run']['id']
    assert (await client.post('/v1/creatives/analyze',json={**body,'as_of':'2026-02-09'},headers=identity['owner'])).status_code==409
    for row,hook in zip(data['creatives'],['Question hook','Proof hook']):
        saved=await client.put(f"/v1/creatives/assets/{row['asset']['id']}/metadata",params={'workspace_id':identity['workspace']},
            json={'version':0,'hook':hook,'angle':'Problem aware','format':'video','duration_seconds':15,'market':'VN'},headers=identity['owner'])
        assert saved.status_code==200 and saved.json()['version']==1
        assert (await client.put(f"/v1/creatives/assets/{row['asset']['id']}/metadata",params={'workspace_id':identity['workspace']},
            json={'version':0,'hook':hook},headers=identity['owner'])).status_code==409
    learned=await client.post('/v1/creatives/analyze',json=payload(identity,end),headers=identity['owner'])
    assert learned.status_code==201;assert {x['dimension'] for x in learned.json()['learnings']}>= {'hook'}
    assert (await client.put(f"/v1/creatives/assets/{tired['asset']['id']}/metadata",params={'workspace_id':identity['workspace']},
        json={'version':1,'hook':'Blocked'},headers=identity['other'])).status_code==403
    outsider=await client.get('/v1/creatives/dashboard',params={'workspace_id':identity['workspace'],'account_id':'act_1'},headers=identity['outsider'])
    assert outsider.status_code==404
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(CreativeAnalysisRun))==2
        assert await db.scalar(select(func.count()).select_from(CreativeMetadata))==2
        assert await db.scalar(select(func.count()).select_from(CreativeLearning))>=1

async def test_frequency_is_not_aggregated_across_ads(client,identity,meta):
    end=await seed(identity)
    async with Session.begin() as db:
        cid=await db.scalar(select(MetaSyncJob.connection_id).limit(1));job=await db.scalar(select(MetaSyncJob).limit(1))
        common=dict(connection_id=cid,connection_version=1,account_id='act_1',currency='VND',timezone='Asia/Ho_Chi_Minh',source_job_id=job.id)
        db.add(AdEntity(**common,kind='ad',remote_id='32',name='Reuse',creative_id='40'))
        for offset in range(6):
            db.add(AdMetric(**common,level='ad',entity_id='32',day=end-timedelta(days=5-offset),hour=-1,granularity='daily',attribution=ATTRIBUTION,
                spend=Decimal('1'),impressions=100,reach=80,clicks=5,purchase=Decimal('0'),revenue=Decimal('0')))
    result=await client.post('/v1/creatives/analyze',json=payload(identity,end),headers=identity['owner'])
    tired=next(x for x in result.json()['creatives'] if x['asset']['creative_id']=='40')
    assert tired['current']['ad_count']==2 and tired['current']['frequency'] is None
    assert tired['feature']['signals']['frequency_up'] is False
