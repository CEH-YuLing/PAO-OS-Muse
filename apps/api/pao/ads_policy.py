"""Fail-closed policy checks for Phase 13 limited Ads Autopilot."""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select

from .config import settings
from .models import (AdAction, AdAnomaly, AdEntity, AdMetric, AdRecommendation,
                     AdsAutopilotPolicy, AdsPolicyAudit, MetaConnection, MetaSyncJob, now)


def snapshot(policy):
    values={key:getattr(policy,key) for key in ('mode','halted','pause_allowed','resume_allowed','budget_allowed',
        'max_budget_change_pct','max_daily_budget_minor_units','minimum_impressions','minimum_conversions',
        'minimum_confidence','freshness_minutes','quiet_hours_enabled','max_actions_per_day','emergency_frozen')}
    return {key:str(value) if isinstance(value,Decimal) else value for key,value in values.items()}


def policy_audit(db,policy,actor,event,**data):
    db.add(AdsPolicyAudit(workspace_id=policy.workspace_id,policy_id=policy.id,actor_id=actor,
        event=event,policy_version=policy.version,data=data))


def in_quiet_hours(value,start,end):
    current=value.time().replace(tzinfo=None)
    if start==end:return True
    return start<=current<end if start<end else current>=start or current<end


async def assess(db,action,recommendation=None,freeze=True):
    policy=await db.scalar(select(AdsAutopilotPolicy).where(AdsAutopilotPolicy.connection_id==action.connection_id,
        AdsAutopilotPolicy.account_id==action.account_id).with_for_update())
    if not policy:return None,['policy_missing']
    reasons=[];emergency=[];config=settings()
    if not config.ads_autopilot_global_enabled:reasons.append('global_kill_switch')
    if not config.meta_autopilot_enabled:reasons.append('meta_kill_switch')
    if policy.connection_version!=action.connection_version:reasons.append('policy_connection_stale')
    if policy.mode!='autopilot':reasons.append('mode_not_autopilot')
    if policy.halted:reasons.append('workspace_kill_switch')
    if policy.emergency_frozen:reasons.append('emergency_frozen')
    allowed={'pause':policy.pause_allowed,'resume':policy.resume_allowed,'update_budget':policy.budget_allowed}
    if not allowed.get(action.action_type,False):reasons.append('action_not_allowed')
    if action.source_agent!='performance_analyst' or not action.recommendation_id:reasons.append('analyst_recommendation_required')
    recommendation=recommendation or (await db.get(AdRecommendation,action.recommendation_id) if action.recommendation_id else None)
    if not recommendation or recommendation.status!='active' or recommendation.connection_id!=action.connection_id or \
        recommendation.connection_version!=action.connection_version or recommendation.resource_id!=action.resource_id:
        reasons.append('recommendation_invalid')
    else:
        if Decimal(recommendation.confidence)<Decimal(policy.minimum_confidence):reasons.append('confidence_below_policy')
        if recommendation.data_freshness_seconds>policy.freshness_minutes*60:emergency.append('data_stale')
        blockers=set(recommendation.proposed_action.get('blocked_by',[]))-{'phase_12_ads_approval'}
        if blockers:reasons.append('recommendation_blocked')
    conn=await db.get(MetaConnection,action.connection_id)
    if not conn or conn.status!='connected' or conn.version!=action.connection_version or not conn.token_ciphertext or conn.expires_at<=now():
        emergency.append('credential_issue')
    recent_failures=await db.scalar(select(func.count()).select_from(MetaSyncJob).where(MetaSyncJob.connection_id==action.connection_id,
        MetaSyncJob.updated_at>=now()-timedelta(minutes=15),MetaSyncJob.status=='failed'))
    if recent_failures>=3:emergency.append('meta_api_errors_spike')
    anomaly=await db.scalar(select(AdAnomaly.kind).where(AdAnomaly.connection_id==action.connection_id,
        AdAnomaly.account_id==action.account_id,AdAnomaly.resource_id==action.resource_id,AdAnomaly.resolved.is_(False),
        AdAnomaly.severity=='critical',AdAnomaly.kind.in_(('TRACKING_DISCREPANCY','SPEND_ANOMALY'))).limit(1))
    if anomaly:emergency.append('tracking_failure' if anomaly=='TRACKING_DISCREPANCY' else 'unexpected_spend_anomaly')
    metric=await db.scalar(select(AdMetric).where(AdMetric.connection_id==action.connection_id,
        AdMetric.connection_version==action.connection_version,AdMetric.account_id==action.account_id,
        AdMetric.level==action.resource_type,AdMetric.entity_id==action.resource_id,AdMetric.granularity=='daily')
        .order_by(AdMetric.day.desc(),AdMetric.updated_at.desc()).limit(1))
    if not metric:reasons.append('metrics_missing')
    else:
        if (metric.impressions or 0)<policy.minimum_impressions:reasons.append('minimum_impressions_not_met')
        if Decimal(metric.purchase or 0)<policy.minimum_conversions:reasons.append('minimum_conversions_not_met')
    entity=await db.scalar(select(AdEntity).where(AdEntity.connection_id==action.connection_id,
        AdEntity.connection_version==action.connection_version,AdEntity.account_id==action.account_id,
        AdEntity.kind=='account').limit(1))
    try:zone=ZoneInfo(entity.timezone if entity else 'UTC')
    except ZoneInfoNotFoundError:zone=timezone.utc;reasons.append('account_timezone_invalid')
    local_now=now().astimezone(zone)
    if policy.quiet_hours_enabled and in_quiet_hours(local_now,policy.quiet_start,policy.quiet_end):reasons.append('quiet_hours')
    day_start=datetime.combine(local_now.date(),time.min,tzinfo=zone).astimezone(timezone.utc)
    daily=await db.scalar(select(func.count()).select_from(AdAction).where(AdAction.policy_id==policy.id,
        AdAction.id!=action.id,AdAction.decision_channel=='autopilot',AdAction.approved_at>=day_start))
    if daily>=policy.max_actions_per_day:reasons.append('daily_action_limit')
    if action.action_type=='update_budget':
        old=int(action.before_state.get('daily_budget') or 0);new=int(action.proposed_state.get('daily_budget') or 0)
        change=Decimal(abs(new-old))*100/Decimal(old) if old else Decimal(1000)
        if change>policy.max_budget_change_pct:reasons.append('budget_change_policy_limit')
        if policy.max_daily_budget_minor_units is None or new>policy.max_daily_budget_minor_units:
            reasons.append('daily_budget_cap')
    if emergency:
        reasons.extend(emergency)
        if freeze and not policy.emergency_frozen:
            before=snapshot(policy);policy.emergency_frozen=True;policy.halted=True;policy.mode='advisor'
            policy.freeze_reason=emergency[0];policy.updated_by=action.user_id;policy.version+=1;policy.updated_at=now()
            policy_audit(db,policy,action.user_id,'autopilot.emergency_frozen',before=before,reasons=emergency)
    return policy,sorted(set(reasons))
