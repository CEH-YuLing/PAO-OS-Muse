from datetime import date, datetime, time, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from pao.config import settings
from pao.db import Session
from pao.main import app
from pao.models import (AdAction, AdActionAudit, AdAnomaly, AdIntelligenceRun, AdMetric,
    AdRecommendation, AdsAutopilotPolicy, AdsPolicyAudit, MetaSyncJob, now)
from pao.ads_actions import execute_action
from pao.ads_policy import in_quiet_hours
from pao.models import TelegramPeer, TelegramDelivery
from pao.telegram import collect
from test_ads_actions import write_setup, proposal
from test_meta import meta


def policy(identity,**changes):
    data={'workspace_id':identity['workspace'],'account_id':'act_1','mode':'autopilot','halted':False,
        'pause_allowed':True,'resume_allowed':True,'budget_allowed':True,'max_budget_change_pct':20,
        'max_daily_budget_minor_units':20000,'minimum_impressions':3000,'minimum_conversions':3,
        'minimum_confidence':'0.8','freshness_minutes':60,'quiet_hours_enabled':False,
        'quiet_start':'23:00:00','quiet_end':'07:00:00','max_actions_per_day':3,
        'version':None,'confirmation':'ENABLE AUTOPILOT'}
    return {**data,**changes}


@pytest.fixture
async def autopilot_data(identity,write_setup,monkeypatch):
    fake,cid=write_setup
    monkeypatch.setattr(settings(),'ads_autopilot_global_enabled',True)
    monkeypatch.setattr(settings(),'meta_autopilot_enabled',True)
    async with Session.begin() as db:
        job=await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id==cid))
        run=AdIntelligenceRun(connection_id=cid,connection_version=1,workspace_id=identity['workspace'],user_id=identity['user_id'],
            account_id='act_1',request_key=str(uuid4()),granularity='daily',period_start=date(2026,1,1),period_end=date(2026,1,1),
            hour=None,summary={},source_updated_at=now())
        db.add(run);await db.flush()
        db.add(AdMetric(connection_id=cid,connection_version=1,account_id='act_1',level='campaign',entity_id='10',
            day=date(2026,1,1),hour=-1,granularity='daily',currency='VND',timezone='Asia/Ho_Chi_Minh',
            attribution='7d_click+1d_view;report=impression',spend='100',impressions=5000,purchase='5',source_job_id=job.id))
        rec=AdRecommendation(connection_id=cid,connection_version=1,workspace_id=identity['workspace'],run_id=run.id,
            account_id='act_1',resource_id='10',type='pause_review',confidence='.9',impact={'risk':'high'},
            reason_codes=['NO_PURCHASE_AFTER_TARGET_SPEND'],explanation='Synthetic policy-qualified recommendation',
            proposed_action={'type':'pause','resource_id':'10','executable':False,'requires':['phase_12_ads_approval']},
            source={'table':'ad_metrics'},data_freshness_seconds=30,fingerprint=str(uuid4()).replace('-',''),status='active')
        db.add(rec);await db.flush();return fake,cid,rec.id


@pytest.fixture
async def budget_autopilot(identity,autopilot_data):
    fake,cid,_=autopilot_data
    async with Session.begin() as db:
        job=await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id==cid))
        run=await db.scalar(select(AdIntelligenceRun).where(AdIntelligenceRun.connection_id==cid))
        db.add(AdMetric(connection_id=cid,connection_version=1,account_id='act_1',level='adset',entity_id='20',campaign_id='10',
            day=date(2026,1,1),hour=-1,granularity='daily',currency='VND',timezone='Asia/Ho_Chi_Minh',
            attribution='7d_click+1d_view;report=impression',spend='100',impressions=5000,purchase='5',source_job_id=job.id))
        rec=AdRecommendation(connection_id=cid,connection_version=1,workspace_id=identity['workspace'],run_id=run.id,
            account_id='act_1',resource_id='20',type='scale_review',confidence='.9',impact={'risk':'medium'},
            reason_codes=['ROAS_ABOVE_TARGET','STABLE_3_DAYS'],explanation='Synthetic budget recommendation',
            proposed_action={'type':'budget_change','percent':15,'resource_id':'20','executable':False},source={'table':'ad_metrics'},
            data_freshness_seconds=30,fingerprint=str(uuid4()).replace('-',''),status='active')
        db.add(rec);await db.flush();return fake,rec.id


async def put_policy(client,identity,body=None):
    return await client.put('/v1/ads/autopilot/policies',json=body or policy(identity),headers=identity['owner'])


def analyst_proposal(identity,recommendation_id,**changes):
    return proposal(identity,source_agent='performance_analyst',recommendation_id=recommendation_id,**changes)


@pytest.mark.parametrize('hour,expected',[(22,False),(23,True),(3,True),(7,False)])
def test_quiet_hours_cross_midnight(hour,expected):
    assert in_quiet_hours(datetime(2026,1,1,hour,tzinfo=timezone.utc),time(23),time(7)) is expected


async def test_policy_is_db_backed_fail_closed_versioned_and_rbac(client,identity,write_setup,monkeypatch):
    monkeypatch.setattr(settings(),'ads_autopilot_global_enabled',False);monkeypatch.setattr(settings(),'meta_autopilot_enabled',False)
    safe=policy(identity,mode='observer',halted=True,pause_allowed=False,resume_allowed=False,budget_allowed=False,
        max_daily_budget_minor_units=None,confirmation=None)
    created=await put_policy(client,identity,safe);assert created.status_code==200,created.text
    detail=created.json();assert detail['policy']['mode']=='observer' and not detail['effective_autopilot']
    assert not detail['global_enabled'] and not detail['meta_enabled'] and detail['audit'][0]['event']=='policy.created'
    assert (await client.put('/v1/ads/autopilot/policies',json=policy(identity),headers=identity['other'])).status_code==403
    assert (await put_policy(client,identity,policy(identity,version=1,confirmation=None))).status_code==422
    stale=await put_policy(client,identity,policy(identity,version=99));assert stale.status_code==409
    updated=await put_policy(client,identity,policy(identity,version=1));assert updated.status_code==200
    assert updated.json()['policy']['version']==2 and not updated.json()['effective_autopilot']


async def test_qualified_analyst_action_autopilot_queues_and_worker_executes(client,identity,autopilot_data):
    fake,_,rid=autopilot_data
    configured=await put_policy(client,identity);assert configured.json()['effective_autopilot']
    made=await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])
    assert made.status_code==201,made.text
    action=made.json()['action'];assert action['approval_status']=='approved' and action['execution_status']=='queued'
    assert action['decision_channel']=='autopilot' and action['policy_id'] and action['policy_version']==1 and fake.writes==[]
    await execute_action({'redis':app.state.redis},action['id'])
    result=(await client.get(f"/v1/approvals/{action['id']}",headers=identity['owner'])).json()
    assert result['action']['execution_status']=='simulated' and fake.writes==[]
    assert [row['event'] for row in result['audit']]==['action.proposed','autopilot.approved','action.started','action.simulated']
    manual=(await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])).json()['action']
    assert manual['approval_status']=='pending' and manual['decision_channel'] is None


async def test_worker_rechecks_changed_policy_and_returns_to_approval(client,identity,autopilot_data):
    fake,_,rid=autopilot_data;await put_policy(client,identity)
    action=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])).json()['action']
    await put_policy(client,identity,policy(identity,mode='advisor',halted=True,version=1,confirmation=None))
    await execute_action({'redis':app.state.redis},action['id'])
    async with Session() as db:
        row=await db.get(AdAction,action['id']);assert row.approval_status=='pending' and row.execution_status=='pending'
        assert row.error_code=='autopilot_policy_blocked' and fake.writes==[]


async def test_emergency_signal_freezes_and_degrades_to_advisor(client,identity,autopilot_data):
    fake,cid,rid=autopilot_data;created=(await put_policy(client,identity)).json()['policy']
    async with Session.begin() as db:
        run=(await db.get(AdRecommendation,rid)).run_id
        db.add(AdAnomaly(connection_id=cid,connection_version=1,workspace_id=identity['workspace'],run_id=run,
            account_id='act_1',resource_id='10',kind='TRACKING_DISCREPANCY',severity='critical',fingerprint=str(uuid4()).replace('-',''),
            evidence={},acknowledged=False,resolved=False))
        db.add(TelegramPeer(telegram_user_id='99001',chat_id='99001',user_id=identity['user_id'],workspace_id=identity['workspace']))
    action=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])).json()['action']
    assert action['approval_status']=='pending' and fake.writes==[]
    detail=(await client.get(f"/v1/ads/autopilot/policies/{created['id']}",headers=identity['owner'])).json()
    assert detail['policy']['emergency_frozen'] and detail['policy']['halted'] and detail['policy']['mode']=='advisor'
    assert detail['policy']['freeze_reason']=='tracking_failure' and not detail['effective_autopilot']
    assert any(row['event']=='autopilot.emergency_frozen' for row in detail['audit'])
    await collect();await collect()
    async with Session() as db:
        alert=await db.scalar(select(TelegramDelivery).where(
            TelegramDelivery.dedup_key.startswith(f'autopilot-freeze:{created["id"]}:')))
        assert alert and 'Không tiếp tục Ads write tự động' in alert.payload['text']


async def test_manual_freeze_and_deliberate_unfreeze_remain_halted(client,identity,autopilot_data):
    _,_,_=autopilot_data;created=(await put_policy(client,identity)).json()['policy'];pid=created['id']
    frozen=await client.post(f'/v1/ads/autopilot/policies/{pid}/freeze',json={
        'version':1,'reason':'Operator emergency stop','confirmation':'FREEZE'},headers=identity['owner'])
    assert frozen.status_code==200 and frozen.json()['policy']['emergency_frozen']
    assert (await client.post(f'/v1/ads/autopilot/policies/{pid}/unfreeze',json={
        'version':2,'reason':'Reviewed and safe','confirmation':'FREEZE'},headers=identity['owner'])).status_code==422
    unfrozen=await client.post(f'/v1/ads/autopilot/policies/{pid}/unfreeze',json={
        'version':2,'reason':'Reviewed and safe','confirmation':'UNFREEZE'},headers=identity['owner'])
    assert unfrozen.status_code==200 and not unfrozen.json()['policy']['emergency_frozen']
    assert unfrozen.json()['policy']['halted'] and not unfrozen.json()['effective_autopilot']
    async with Session() as db:
        events=list(await db.scalars(select(AdsPolicyAudit.event).where(AdsPolicyAudit.policy_id==pid)))
        assert events==['policy.created','policy.frozen','policy.unfrozen']


async def test_budget_and_sample_guardrails_defer_to_phase12_approval(client,identity,autopilot_data):
    fake,_,rid=autopilot_data;await put_policy(client,identity,policy(identity,minimum_impressions=6000))
    action=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])).json()['action']
    assert action['approval_status']=='pending' and fake.writes==[]
    async with Session() as db:
        audits=list(await db.scalars(select(AdActionAudit).where(AdActionAudit.action_id==action['id'])))
        deferred=next(row for row in audits if row.event=='autopilot.deferred')
        assert 'minimum_impressions_not_met' in deferred.data['reasons']


async def test_budget_autopilot_enforces_percentage_and_absolute_cap(client,identity,budget_autopilot):
    fake,rid=budget_autopilot
    await put_policy(client,identity,policy(identity,max_budget_change_pct=20,max_daily_budget_minor_units=11000))
    body=analyst_proposal(identity,rid,resource_type='adset',resource_id='20',action_type='update_budget',
        budget_minor_units=11500,dry_run=True)
    action=(await client.post('/v1/ads/actions',json=body,headers=identity['owner'])).json()['action']
    assert action['approval_status']=='pending' and fake.writes==[]
    async with Session() as db:
        events=list(await db.scalars(select(AdActionAudit).where(AdActionAudit.action_id==action['id'])))
        assert 'daily_budget_cap' in next(row for row in events if row.event=='autopilot.deferred').data['reasons']


async def test_budget_within_policy_is_queued_without_provider_call(client,identity,budget_autopilot):
    fake,rid=budget_autopilot;await put_policy(client,identity)
    body=analyst_proposal(identity,rid,resource_type='adset',resource_id='20',action_type='update_budget',
        budget_minor_units=11500,dry_run=True)
    action=(await client.post('/v1/ads/actions',json=body,headers=identity['owner'])).json()['action']
    assert action['approval_status']=='approved' and action['execution_status']=='queued' and fake.writes==[]


async def test_resume_is_independently_policy_controlled(client,identity,autopilot_data):
    fake,_,rid=autopilot_data;fake.states['10']['status']='PAUSED';await put_policy(client,identity,policy(identity,resume_allowed=False))
    blocked=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid,action_type='resume'),headers=identity['owner'])).json()['action']
    assert blocked['approval_status']=='pending'
    async with Session() as db:
        audits=list(await db.scalars(select(AdActionAudit).where(AdActionAudit.action_id==blocked['id'])))
        assert 'action_not_allowed' in next(row for row in audits if row.event=='autopilot.deferred').data['reasons']


async def test_global_gate_and_daily_limit_are_fail_closed(client,identity,autopilot_data,monkeypatch):
    fake,_,rid=autopilot_data;await put_policy(client,identity,policy(identity,max_actions_per_day=1))
    monkeypatch.setattr(settings(),'ads_autopilot_global_enabled',False)
    blocked=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])).json()['action']
    assert blocked['approval_status']=='pending'
    monkeypatch.setattr(settings(),'ads_autopilot_global_enabled',True)
    first=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])).json()['action']
    second=(await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])).json()['action']
    assert first['approval_status']=='approved' and second['approval_status']=='pending' and fake.writes==[]
    async with Session() as db:
        events=list(await db.scalars(select(AdActionAudit).where(AdActionAudit.action_id==second['id'])))
        assert 'daily_action_limit' in next(row for row in events if row.event=='autopilot.deferred').data['reasons']
