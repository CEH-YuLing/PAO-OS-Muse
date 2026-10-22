"""Deterministic Phase 10 performance analysis over normalized warehouse metrics."""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select

from .db import Session
from .models import (AdAnomaly, AdEntity, AdIntelligenceRun, AdMetric,
                     AdRecommendation, AdRule, AdTarget, AttributionMetric,
                     AttributionRun, Member, MetaConnection, now)
from .warehouse import ATTRIBUTION
from .modules.events.producer import analyzed as record_analysis_completed
from .auth import Principal

ANALYST_VERSION='performance-analyst-v1'
RULES={
    'NO_PURCHASE_AFTER_TARGET_SPEND':(
        'Chi tiêu vượt 2× target CPA nhưng chưa có purchase',
        {'all':['spend_gte_2x_target_cpa','purchase_eq_0','impressions_gte_minimum']},
        {'type':'pause_review','suggested':'pause','executable':False}),
    'CPA_ABOVE_TARGET':(
        'CPA cao hơn target ít nhất 20%',
        {'all':['cpa_gte_1.2x_target','purchase_gte_minimum']},
        {'type':'funnel_review','suggested':'diagnose_funnel','executable':False}),
    'ROAS_ABOVE_TARGET_STABLE':(
        'ROAS cao hơn target 30% và ổn định ba ngày',
        {'all':['roas_gte_1.3x_target','purchase_gte_minimum','stable_3_days']},
        {'type':'scale_review','suggested_budget_change_pct':15,'executable':False}),
}


def ratio(a,b,multiplier=1):
    if a is None or b in (None,0):return None
    return (Decimal(a)/Decimal(b)*multiplier).quantize(Decimal('.000001'))


def deviation(current,baseline):
    if current is None or baseline in (None,0):return None
    return ((Decimal(current)-Decimal(baseline))/Decimal(baseline)*100).quantize(Decimal('.000001'))


def metric(row):
    return {'spend':row.spend,'impressions':row.impressions,'clicks':row.clicks,'purchase':row.purchase,
        'revenue':row.revenue,'ctr':ratio(row.clicks,row.impressions,100),'cpm':ratio(row.spend,row.impressions,1000),
        'cpa':ratio(row.spend,row.purchase),'roas':ratio(row.revenue,row.spend),'frequency':row.frequency}


def average(rows):
    values=[metric(row) for row in rows];result={}
    for key in values[0] if values else ():
        present=[Decimal(item[key]) for item in values if item[key] is not None]
        result[key]=(sum(present,Decimal(0))/len(present)).quantize(Decimal('.000001')) if present else None
    return result


def serial(values):
    return {key:str(value) if isinstance(value,Decimal) else value for key,value in values.items()}


def fingerprint(*parts):
    return hashlib.sha256(':'.join(str(part) for part in parts).encode()).hexdigest()


async def ensure_rules(db,target):
    existing={row.code:row for row in await db.scalars(select(AdRule).where(AdRule.connection_id==target.connection_id,
        AdRule.account_id==target.account_id))}
    for code,(name,conditions,action) in RULES.items():
        row=existing.get(code)
        if not row:
            db.add(AdRule(connection_id=target.connection_id,connection_version=target.connection_version,
                workspace_id=target.workspace_id,account_id=target.account_id,platform='meta',code=code,name=name,
                conditions_json=conditions,action_json=action,mode='advisor',enabled=True))
        else:
            row.connection_version=target.connection_version


def confidence(current,target,run_days,needs_conversion=True):
    checks=[Decimal(current['spend'] or 0)>=target.minimum_spend,
        (current['impressions'] or 0)>=target.minimum_impressions,(current['clicks'] or 0)>=target.minimum_clicks,
        run_days>=target.minimum_run_days]
    if needs_conversion:checks.append(Decimal(current['purchase'] or 0)>=target.minimum_conversions)
    score=sum(checks)/len(checks)
    return Decimal('0.9') if score==1 else Decimal('0.65') if score>=.6 else Decimal('0.3')


async def analyze(db,conn,user_id,account_id,as_of,granularity,hour,request_key):
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==account_id,AdEntity.kind=='account'))
    target=await db.scalar(select(AdTarget).where(AdTarget.connection_id==conn.id,AdTarget.account_id==account_id))
    if not account:raise ValueError('intelligence_account_unavailable')
    if not target:raise ValueError('intelligence_target_required')
    target.connection_version=conn.version;await ensure_rules(db,target)
    query=select(AdMetric).where(AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,
        AdMetric.account_id==account_id,AdMetric.level=='campaign',AdMetric.granularity==granularity,
        AdMetric.attribution==ATTRIBUTION,AdMetric.day==as_of)
    query=query.where(AdMetric.hour==(-1 if granularity=='daily' else hour))
    current_rows=list(await db.scalars(query.order_by(AdMetric.entity_id)))
    if not current_rows:raise ValueError('intelligence_data_unavailable')
    history=list(await db.scalars(select(AdMetric).where(AdMetric.connection_id==conn.id,
        AdMetric.connection_version==conn.version,AdMetric.account_id==account_id,AdMetric.level=='campaign',
        AdMetric.granularity==granularity,AdMetric.attribution==ATTRIBUTION,AdMetric.day>=as_of-timedelta(days=35),
        AdMetric.day<as_of,AdMetric.hour==(-1 if granularity=='daily' else hour)).order_by(AdMetric.day.desc())))
    latest=max(row.updated_at for row in current_rows)
    run=AdIntelligenceRun(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,user_id=user_id,
        account_id=account_id,request_key=request_key,granularity=granularity,period_start=as_of-timedelta(days=35),
        period_end=as_of,hour=hour if granularity=='hourly' else None,analyst_version=ANALYST_VERSION,
        source_updated_at=latest,summary={})
    db.add(run);await db.flush()
    names=dict((await db.execute(select(AdEntity.remote_id,AdEntity.name).where(AdEntity.connection_id==conn.id,
        AdEntity.connection_version==conn.version,AdEntity.account_id==account_id,AdEntity.kind=='campaign'))).all())
    enabled={row.code for row in await db.scalars(select(AdRule).where(AdRule.connection_id==conn.id,
        AdRule.account_id==account_id,AdRule.connection_version==conn.version,AdRule.enabled.is_(True)))}
    detected=set();recommended=set();anomalies=[];recommendations=[]
    for row in current_rows:
        current=metric(row)
        tracking=await db.scalar(select(AttributionMetric).join(AttributionRun,AttributionRun.id==AttributionMetric.run_id).where(
            AttributionRun.connection_id==conn.id,AttributionRun.connection_version==conn.version,
            AttributionRun.account_id==account_id,AttributionRun.period_end<=as_of,
            AttributionMetric.campaign_id==row.entity_id).order_by(AttributionRun.period_end.desc(),AttributionRun.created_at.desc()).limit(1))
        same_slot=[item for item in history if item.entity_id==row.entity_id and item.day.weekday()==as_of.weekday()][:4]
        baseline=average(same_slot)
        evidence={'current':serial(current),'baseline':serial(baseline),'baseline_samples':len(same_slot),
            'comparison':'same_weekday_hour' if granularity=='hourly' else 'same_weekday',
            'tracking':None if not tracking else {'status':tracking.tracking_status,'purchase_discrepancy_pct':str(tracking.purchase_discrepancy_pct) if tracking.purchase_discrepancy_pct is not None else None,
                'revenue_discrepancy_pct':str(tracking.revenue_discrepancy_pct) if tracking.revenue_discrepancy_pct is not None else None}}
        candidates=[]
        if len(same_slot)>=2:
            for kind,key,direction,threshold,severity in [
                ('SPEND_ANOMALY','spend','up',50,'warning'),('CPA_SPIKE','cpa','up',50,'warning'),
                ('ROAS_COLLAPSE','roas','down',40,'critical'),('CTR_COLLAPSE','ctr','down',40,'warning'),
                ('CPM_SPIKE','cpm','up',50,'notice'),('FREQUENCY_SPIKE','frequency','up',50,'notice')]:
                change=deviation(current[key],baseline.get(key))
                if change is not None and (change>=threshold if direction=='up' else change<=-threshold):
                    candidates.append((kind,severity,current[key],baseline.get(key),change))
            if Decimal(baseline.get('purchase') or 0)>=1 and Decimal(current['purchase'] or 0)==0:
                candidates.append(('CONVERSION_DISAPPEARANCE','critical',current['purchase'],baseline.get('purchase'),Decimal('-100')))
        if (not tracking or tracking.tracking_status!='unhealthy') and (((current['revenue'] or 0)>0 and Decimal(current['purchase'] or 0)==0) or ((current['purchase'] or 0)>0 and current['revenue'] is None)):
            candidates.append(('TRACKING_DISCREPANCY','critical',current['revenue'],current['purchase'],None))
        if tracking and tracking.tracking_status=='unhealthy':
            candidates.append(('TRACKING_DISCREPANCY','critical',tracking.platform_purchases,Decimal(tracking.actual_orders),tracking.purchase_discrepancy_pct))
        for kind,severity,value,base,change in candidates:
            key=fingerprint(conn.id,account_id,row.entity_id,kind,granularity,hour)
            detected.add(key)
            item=await db.scalar(select(AdAnomaly).where(AdAnomaly.fingerprint==key))
            if not item:
                item=AdAnomaly(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,
                    run_id=run.id,account_id=account_id,resource_id=row.entity_id,kind=kind,severity=severity,
                    fingerprint=key,current_value=value,baseline_value=base,deviation_pct=change,evidence=evidence)
                db.add(item)
            else:
                was_resolved=item.resolved
                item.connection_version=conn.version;item.run_id=run.id;item.severity=severity;item.current_value=value
                item.baseline_value=base;item.deviation_pct=change;item.evidence=evidence;item.last_seen=now();item.resolved=False
                if was_resolved:item.acknowledged=False
            anomalies.append(item)
        daily=[item for item in history if item.entity_id==row.entity_id and item.granularity=='daily']
        run_days=len({item.day for item in daily if Decimal(item.spend or 0)>0})+(1 if Decimal(row.spend or 0)>0 else 0)
        recent=[row]+[item for item in daily if item.day>=as_of-timedelta(days=2)]
        stable=len({item.day for item in recent})>=3 and target.target_roas is not None and all(
            (metric(item)['roas'] or 0)>=target.target_roas for item in recent)
        rules=[]
        if ('NO_PURCHASE_AFTER_TARGET_SPEND' in enabled and target.target_cpa is not None and
            Decimal(current['spend'] or 0)>=target.target_cpa*2 and Decimal(current['purchase'] or 0)==0 and
            (current['impressions'] or 0)>=target.minimum_impressions):
            rules.append(('pause_review',['NO_PURCHASE_AFTER_TARGET_SPEND'],confidence(current,target,run_days,False),
                'Chi tiêu đã vượt 2× target CPA mà chưa ghi nhận purchase. Cần kiểm tra funnel và tracking trước khi quyết định.',
                {'type':'pause','resource_id':row.entity_id,'executable':False,'requires':['phase_12_ads_approval']}))
        if ('CPA_ABOVE_TARGET' in enabled and target.target_cpa is not None and current['cpa'] is not None and
            current['cpa']>=target.target_cpa*Decimal('1.2') and Decimal(current['purchase'] or 0)>=target.minimum_conversions):
            rules.append(('funnel_review',['CPA_ABOVE_TARGET'],confidence(current,target,run_days),
                'CPA cao hơn target; hãy chẩn đoán CPM → CTR → CPC → landing/checkout trước khi thay đổi quảng cáo.',
                {'type':'diagnose_funnel','resource_id':row.entity_id,'executable':False}))
        if ('ROAS_ABOVE_TARGET_STABLE' in enabled and target.target_roas is not None and current['roas'] is not None and
            current['roas']>=target.target_roas*Decimal('1.3') and Decimal(current['purchase'] or 0)>=target.minimum_conversions and stable):
            rules.append(('scale_review',['ROAS_ABOVE_TARGET','STABLE_3_DAYS'],confidence(current,target,run_days),
                'ROAS vượt target và ổn định ba ngày. Chỉ xem xét scale sau khi có budget history, learning state và creative health.',
                {'type':'budget_change','percent':15,'resource_id':row.entity_id,'executable':False,
                 'blocked_by':['budget_change_history','learning_state','creative_health','phase_12_ads_approval']}))
        if not rules and Decimal(current['spend'] or 0)>0 and confidence(current,target,run_days)<Decimal('.65'):
            rules.append(('collect_more_data',['LOW_SAMPLE_SIZE'],Decimal('.3'),
                'Mẫu chưa đạt guardrail; tiếp tục thu thập dữ liệu trước khi đưa khuyến nghị mạnh.',
                {'type':'none','executable':False}))
        freshness=max(0,int((now()-latest).total_seconds()))
        stale=freshness>target.freshness_minutes*60
        for kind,codes,score,explanation,action in rules:
            if kind in ('pause_review','funnel_review'):
                action={**action,'funnel_evidence':serial({key:current[key] for key in ('cpm','ctr','cpa','purchase','revenue')})}
            if stale:codes=[*codes,'STALE_DATA'];score=min(score,Decimal('.3'));action={**action,'blocked_by':sorted(set(action.get('blocked_by',[])+['stale_data']))}
            if tracking and tracking.tracking_status in ('watch','unhealthy'):
                code='TRACKING_UNHEALTHY' if tracking.tracking_status=='unhealthy' else 'TRACKING_WATCH'
                codes=[*codes,code];score=min(score,Decimal('.3') if tracking.tracking_status=='unhealthy' else Decimal('.55'))
                action={**action,'blocked_by':sorted(set(action.get('blocked_by',[])+['tracking_health']))}
            key=fingerprint(conn.id,account_id,row.entity_id,kind)
            recommended.add(key)
            source={'table':'ad_metrics','platform':'meta','account_id':account_id,'resource_id':row.entity_id,
                'time_range':{'start':run.period_start.isoformat(),'end':as_of.isoformat()},'granularity':granularity,
                'hour':hour if granularity=='hourly' else None,'attribution':ATTRIBUTION,'last_sync':latest.isoformat(),
                'source_job_ids':sorted({item.source_job_id for item in [row,*same_slot]})}
            item=await db.scalar(select(AdRecommendation).where(AdRecommendation.fingerprint==key))
            impact={'risk':'high' if kind=='pause_review' else 'medium' if kind in ('funnel_review','scale_review') else 'low'}
            if not item:
                item=AdRecommendation(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,
                    run_id=run.id,account_id=account_id,resource_id=row.entity_id,type=kind,confidence=score,
                    impact=impact,reason_codes=codes,explanation=explanation,proposed_action=action,source=source,
                    data_freshness_seconds=freshness,fingerprint=key,status='active')
                db.add(item)
            else:
                item.connection_version=conn.version;item.run_id=run.id;item.confidence=score;item.impact=impact
                item.reason_codes=codes;item.explanation=explanation;item.proposed_action=action;item.source=source
                item.data_freshness_seconds=freshness;item.last_seen=now()
                if item.status=='resolved':item.status='active'
            if item.status=='active':recommendations.append(item)
    active_anomalies=list(await db.scalars(select(AdAnomaly).where(AdAnomaly.connection_id==conn.id,
        AdAnomaly.account_id==account_id,AdAnomaly.resolved.is_(False))))
    for item in active_anomalies:
        if item.fingerprint not in detected:item.resolved=True;item.last_seen=now()
    active_recs=list(await db.scalars(select(AdRecommendation).where(AdRecommendation.connection_id==conn.id,
        AdRecommendation.account_id==account_id,AdRecommendation.status.in_(['active','dismissed']))))
    for item in active_recs:
        if item.fingerprint not in recommended:item.status='resolved';item.last_seen=now()
    await db.flush()
    run.summary={'campaigns_analyzed':len(current_rows),'anomalies_detected':len(anomalies),
        'recommendations_active':len(recommendations),'baseline':'same weekday/hour, up to 4 prior samples',
        'target_id':target.id,'currency':account.currency,'timezone':account.timezone,
        'resource_names':{row.entity_id:names.get(row.entity_id) for row in current_rows},
        'anomaly_ids':[item.id for item in anomalies],'recommendation_ids':[item.id for item in recommendations]}
    await db.flush()
    await record_analysis_completed(db,run,Principal(user_id,0))
    return run


async def schedule_intelligence(ctx):
    """Analyze each newly published complete daily/hourly slot exactly once."""
    async with Session() as db:
        ids=list(await db.scalars(select(AdTarget.id).order_by(AdTarget.updated_at).limit(20)))
    for ident in ids:
        for granularity in ('daily','hourly'):
            async with Session.begin() as db:
                target=await db.get(AdTarget,ident,with_for_update=True)
                if not target:continue
                conn=await db.get(MetaConnection,target.connection_id)
                member=await db.get(Member,(target.workspace_id,conn.user_id)) if conn else None
                account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==target.connection_id,
                    AdEntity.connection_version==target.connection_version,AdEntity.account_id==target.account_id,AdEntity.kind=='account'))
                if not conn or conn.version!=target.connection_version or not member or member.role not in ('owner','admin') or not account:continue
                local=now().astimezone(ZoneInfo(account.timezone))
                conditions=[AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,
                    AdMetric.account_id==target.account_id,AdMetric.level=='campaign',AdMetric.granularity==granularity,
                    AdMetric.attribution==ATTRIBUTION]
                if granularity=='daily':conditions.append(AdMetric.day<local.date())
                else:conditions.append(or_(AdMetric.day<local.date(),(AdMetric.day==local.date())&(AdMetric.hour<local.hour)))
                latest=await db.scalar(select(AdMetric).where(*conditions).order_by(AdMetric.day.desc(),AdMetric.hour.desc(),AdMetric.updated_at.desc()).limit(1))
                if not latest:continue
                key=f'intelligence-auto:{target.id}:{granularity}:{latest.day}:{latest.hour}:{int(latest.updated_at.timestamp())}'
                if await db.scalar(select(AdIntelligenceRun.id).where(AdIntelligenceRun.connection_id==conn.id,AdIntelligenceRun.request_key==key)):continue
                try:await analyze(db,conn,conn.user_id,target.account_id,latest.day,granularity,latest.hour if granularity=='hourly' else None,key)
                except ValueError:continue
