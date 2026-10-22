from datetime import datetime,date,time,timedelta,timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import select,func
from pao.db import Session
from pao.models import (MetaSyncJob,AdEntity,AdMetric,AdReport,AdReportDelivery,AdReportSchedule,
    TelegramPeer,TelegramDelivery,Member,now)
from pao.warehouse import ATTRIBUTION
from pao.reporting import report_text,next_delivery
from pao.report_api import schedule_reports
from pao.telegram import deliver
from pao.config import settings
from test_meta import meta,connected


@pytest.fixture
def reporting(meta,monkeypatch):
    monkeypatch.setattr(settings(),'telegram_enabled',True)
    monkeypatch.setattr(settings(),'telegram_bot_token','123:synthetic_token_for_testing_only')


async def seed(identity,days,campaigns=('10','20')):
    cid=await connected(identity)
    async with Session.begin() as db:
        job=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key=str(uuid4()),kind='historical',
            account_id='act_1',since=min(days).isoformat(),until=max(days).isoformat(),status='completed',warehouse=True,granularity='daily')
        db.add(job);await db.flush()
        common=dict(connection_id=cid,connection_version=1,account_id='act_1',currency='VND',timezone='Asia/Ho_Chi_Minh',source_job_id=job.id)
        db.add(AdEntity(**common,kind='account',remote_id='act_1',name='QA Account'))
        for ident in campaigns:db.add(AdEntity(**common,kind='campaign',remote_id=ident,name='Campaign '+ident,parent_id='act_1'))
        await db.flush()
        for day in days:
            for index,ident in enumerate(campaigns,1):
                db.add(AdMetric(**common,level='campaign',entity_id=ident,day=day,hour=-1,granularity='daily',attribution=ATTRIBUTION,
                    spend=Decimal(10*index),revenue=Decimal(30*index),purchase=Decimal(index),leads=None,
                    impressions=100*index,clicks=10*index))
        # These rows must never be included in report totals.
        db.add(AdMetric(**common,level='ad',entity_id='999',campaign_id='10',day=max(days),hour=-1,granularity='daily',attribution=ATTRIBUTION,
            spend=999,revenue=999,purchase=999,impressions=999,clicks=999))
        db.add(AdMetric(**common,level='campaign',entity_id='10',day=max(days),hour=1,granularity='hourly',attribution=ATTRIBUTION,
            spend=999,revenue=999,purchase=999,impressions=999,clicks=999))
    return cid


def body(identity,kind='daily',end='2026-01-08',key=None):
    return {'workspace_id':identity['workspace'],'account_id':'act_1','kind':kind,'period_end':end,'request_key':key or str(uuid4())}


async def test_daily_report_totals_comparisons_scope_and_idempotency(client,identity,reporting):
    await seed(identity,[date(2026,1,d) for d in range(1,9)])
    payload=body(identity,key=str(uuid4()))
    response=await client.post('/v1/reports',json=payload,headers=identity['owner']);assert response.status_code==201,response.text
    report=response.json()['report']
    assert report['spend']=='30.000000' and report['revenue']=='90.000000' and report['purchases']=='3.000000'
    assert report['roas']=='3.000000' and report['cpa']=='10.000000'
    assert report['coverage_days']==1 and len(report['campaigns'])==2
    assert report['comparison']['spend']=={'previous_period_pct':'0.000000','previous_7d_average_pct':'0.000000'}
    repeated=await client.post('/v1/reports',json=payload,headers=identity['owner'])
    assert repeated.json()['report']['id']==report['id']
    assert (await client.post('/v1/reports',json={**payload,'kind':'weekly'},headers=identity['owner'])).status_code==409
    assert (await client.post('/v1/reports',json=body(identity),headers=identity['other'])).status_code==403
    assert (await client.get('/v1/reports',params={'workspace_id':identity['workspace']},headers=identity['other'])).json()==[]
    assert (await client.get('/v1/reports/'+report['id'],headers=identity['other'])).status_code==404


async def test_weekly_partial_coverage_and_dashboard_versions(client,identity,reporting):
    await seed(identity,[date(2026,1,8)])
    first=await client.post('/v1/reports',json=body(identity),headers=identity['owner'])
    assert first.status_code==201
    weekly=await client.post('/v1/reports',json=body(identity,'weekly'),headers=identity['owner'])
    assert weekly.status_code==201 and weekly.json()['report']['coverage_days']==1 and weekly.json()['report']['expected_days']==7
    assert weekly.json()['report']['comparison']['spend']['previous_period_pct'] is None
    second=await client.post('/v1/reports',json=body(identity),headers=identity['owner'])
    dashboard=await client.get('/v1/reports/dashboard',params={'workspace_id':identity['workspace'],'account_id':'act_1'},headers=identity['owner'])
    assert dashboard.status_code==200 and len(dashboard.json()['daily_trend'])==1
    assert dashboard.json()['latest_daily']['id']==second.json()['report']['id']
    assert dashboard.json()['latest_weekly']['id']==weekly.json()['report']['id']


async def test_report_validation(client,identity,reporting):
    await seed(identity,[date(2026,1,8)])
    today=now().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()
    assert (await client.post('/v1/reports',json=body(identity,end=today),headers=identity['owner'])).status_code==422
    missing=body(identity,end='2026-02-01')
    result=await client.post('/v1/reports',json=missing,headers=identity['owner'])
    assert result.status_code==409 and result.json()['detail']=='report_data_unavailable'


async def peer(identity):
    async with Session.begin() as db:
        row=TelegramPeer(telegram_user_id='555',chat_id='555',user_id=identity['user_id'],workspace_id=identity['workspace'])
        db.add(row);await db.flush();return row.id


async def test_manual_telegram_delivery_idempotent_and_trace(client,identity,reporting):
    await seed(identity,[date(2026,1,8)]);await peer(identity)
    made=await client.post('/v1/reports',json=body(identity),headers=identity['owner']);rid=made.json()['report']['id']
    first=await client.post(f'/v1/reports/{rid}/telegram',headers=identity['owner']);assert first.status_code==202
    second=await client.post(f'/v1/reports/{rid}/telegram',headers=identity['owner'])
    assert second.json()['id']==first.json()['id'] and second.json()['status']=='queued'
    async with Session() as db:
        rows=list(await db.scalars(select(TelegramDelivery)))
        assert len(rows)==1 and 'UNDERPERFORMERS: chưa đánh giá' in rows[0].payload['text']
        assert 'ACTIONS TAKEN: không có' in rows[0].payload['text']
    send=AsyncMock(return_value={'message_id':88});await deliver(send)
    detail=await client.get(f'/v1/reports/{rid}',headers=identity['owner'])
    assert detail.json()['deliveries'][0]['status']=='sent'


def test_next_delivery_timezone_and_weekday():
    after=datetime(2026,1,5,0,30,tzinfo=timezone.utc) # Monday 07:30 in Ho Chi Minh
    daily=next_delivery('Asia/Ho_Chi_Minh','daily',8,None,after)
    weekly=next_delivery('Asia/Ho_Chi_Minh','weekly',8,0,after)
    assert daily==weekly==datetime(2026,1,5,1,0,tzinfo=timezone.utc)
    assert next_delivery('Asia/Ho_Chi_Minh','weekly',7,0,after)==datetime(2026,1,12,0,0,tzinfo=timezone.utc)


async def test_schedule_generates_and_queues_once_then_revocation_disables(client,identity,reporting):
    local_today=now().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    await seed(identity,[local_today-timedelta(days=1)]);await peer(identity)
    data={'workspace_id':identity['workspace'],'account_id':'act_1','kind':'daily','enabled':True,'delivery_hour':8,'weekday':None,'telegram':True}
    assert (await client.put('/v1/reports/configuration/schedules',json=data,headers=identity['other'])).status_code==403
    result=await client.put('/v1/reports/configuration/schedules',json=data,headers=identity['owner']);assert result.status_code==200,result.text
    sid=result.json()['id']
    async with Session.begin() as db:(await db.get(AdReportSchedule,sid)).next_at=now()-timedelta(seconds=1)
    await schedule_reports({});await schedule_reports({})
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(AdReport))==1
        assert await db.scalar(select(func.count()).select_from(AdReportDelivery))==1
        assert await db.scalar(select(func.count()).select_from(TelegramDelivery))==1
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
        schedule=await db.get(AdReportSchedule,sid);schedule.next_at=now()-timedelta(seconds=1)
    await schedule_reports({})
    async with Session() as db:assert not (await db.get(AdReportSchedule,sid)).enabled


async def test_schedule_requires_weekday_and_peer(client,identity,reporting):
    await seed(identity,[date(2026,1,8)])
    data={'workspace_id':identity['workspace'],'account_id':'act_1','kind':'weekly','enabled':True,'delivery_hour':8,'telegram':True}
    assert (await client.put('/v1/reports/configuration/schedules',json=data,headers=identity['owner'])).status_code==422
    data['weekday']=0
    assert (await client.put('/v1/reports/configuration/schedules',json=data,headers=identity['owner'])).status_code==409


async def test_schedule_disables_when_peer_is_revoked(client,identity,reporting):
    local_today=now().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    await seed(identity,[local_today-timedelta(days=1)]);pid=await peer(identity)
    data={'workspace_id':identity['workspace'],'account_id':'act_1','kind':'daily','enabled':True,'delivery_hour':8,'weekday':None,'telegram':True}
    result=await client.put('/v1/reports/configuration/schedules',json=data,headers=identity['owner']);sid=result.json()['id']
    async with Session.begin() as db:
        (await db.get(TelegramPeer,pid)).enabled=False
        (await db.get(AdReportSchedule,sid)).next_at=now()-timedelta(seconds=1)
    await schedule_reports({})
    async with Session() as db:
        assert not (await db.get(AdReportSchedule,sid)).enabled
        assert await db.scalar(select(func.count()).select_from(AdReport))==0
