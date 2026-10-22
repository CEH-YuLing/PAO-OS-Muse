"""Deterministic Phase 15 attribution and CRM value analysis."""
import hashlib
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .models import (AdEntity, AdMetric, AnalyticsEvent, AttributionMetric, AttributionRun,
    AttributionSource, BusinessOrder, CrmLead, CrmStageEvent, TrackingAlert, now)
from .warehouse import ATTRIBUTION

ZERO=Decimal('0');Q=Decimal('.000001')

def ratio(a,b,multiplier=Decimal('1')):
    return (Decimal(a)*multiplier/Decimal(b)).quantize(Q,rounding=ROUND_HALF_UP) if b not in (None,0,ZERO) else None

def discrepancy(platform,actual):
    if Decimal(actual or 0)==0:return ZERO if Decimal(platform or 0)==0 else Decimal('100')
    return ratio(abs(Decimal(platform or 0)-Decimal(actual)),actual,Decimal('100'))

def serial(value):
    if isinstance(value,Decimal):return str(value)
    if isinstance(value,datetime):return value.isoformat()
    return value

def fingerprint(*parts):return hashlib.sha256('\x1f'.join(str(x) for x in parts).encode()).hexdigest()

async def analyze(db,conn,user_id,account_id,period_start,period_end,threshold,request_key):
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==account_id,AdEntity.kind=='account'))
    if not account:raise ValueError('attribution_account_unavailable')
    sources=list(await db.scalars(select(AttributionSource).where(AttributionSource.connection_id==conn.id,
        AttributionSource.connection_version==conn.version,AttributionSource.account_id==account_id,AttributionSource.enabled.is_(True))))
    if not sources:raise ValueError('attribution_sources_required')
    local=ZoneInfo(account.timezone);start=datetime.combine(period_start,time.min,local).astimezone(timezone.utc)
    end=datetime.combine(period_end+timedelta(days=1),time.min,local).astimezone(timezone.utc)
    meta=list(await db.scalars(select(AdMetric).where(AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,
        AdMetric.account_id==account_id,AdMetric.level=='campaign',AdMetric.granularity=='daily',AdMetric.attribution==ATTRIBUTION,
        AdMetric.day.between(period_start,period_end))))
    ga4_ids=[x.id for x in sources if x.kind=='ga4'];crm_ids=[x.id for x in sources if x.kind=='crm'];order_ids=[x.id for x in sources if x.kind=='orders']
    events=list(await db.scalars(select(AnalyticsEvent).where(AnalyticsEvent.source_id.in_(ga4_ids),AnalyticsEvent.occurred_at>=start,AnalyticsEvent.occurred_at<end))) if ga4_ids else []
    leads=list(await db.scalars(select(CrmLead).where(CrmLead.source_id.in_(crm_ids),CrmLead.acquired_at>=start,CrmLead.acquired_at<end))) if crm_ids else []
    stage_rows=list(await db.scalars(select(CrmStageEvent).where(CrmStageEvent.lead_id.in_([x.id for x in leads]),
        CrmStageEvent.occurred_at<end).order_by(CrmStageEvent.occurred_at))) if leads else []
    stage_as_of={x.lead_id:x.stage for x in stage_rows}
    orders=list(await db.scalars(select(BusinessOrder).where(BusinessOrder.source_id.in_(order_ids),BusinessOrder.occurred_at>=start,
        BusinessOrder.occurred_at<end,BusinessOrder.status=='paid'))) if order_ids else []
    # Orders can point to leads acquired before this reporting cohort. Load those
    # leads only for deterministic order attribution; keep funnel counts cohort-bound.
    linked_ids={x.lead_external_id for x in orders if x.attribution_method=='lead_link' and x.lead_external_id}
    linked_leads=list(await db.scalars(select(CrmLead).where(CrmLead.source_id.in_(crm_ids),
        CrmLead.external_id.in_(linked_ids)))) if crm_ids and linked_ids else []
    grouped_leads=defaultdict(list)
    for lead in linked_leads:grouped_leads[lead.external_id].append(lead)
    # Duplicate external IDs across CRM sources are ambiguous and remain unattributed.
    lead_map={key:rows[0] for key,rows in grouped_leads.items() if len(rows)==1}
    def order_campaign(order):
        if order.attribution_method in ('campaign_id','utm'):return order.campaign_id
        if order.attribution_method!='lead_link':return None
        lead=lead_map.get(order.lead_external_id) if order.lead_external_id else None
        return lead.campaign_id if lead else None
    campaign_ids={x.entity_id for x in meta}|{x.campaign_id for x in events+leads if x.campaign_id}|{order_campaign(x) for x in orders if order_campaign(x)}
    if not campaign_ids:raise ValueError('attribution_data_unavailable')
    names=dict((await db.execute(select(AdEntity.remote_id,AdEntity.name).where(AdEntity.connection_id==conn.id,
        AdEntity.connection_version==conn.version,AdEntity.account_id==account_id,AdEntity.kind=='campaign'))).all())
    all_rows=[*meta,*events,*leads,*stage_rows,*orders];latest=max((getattr(x,'updated_at',None) or x.created_at for x in all_rows),default=now())
    run=AttributionRun(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,user_id=user_id,
        account_id=account_id,request_key=request_key,period_start=period_start,period_end=period_end,
        discrepancy_threshold_pct=threshold,source_updated_at=latest);db.add(run);await db.flush()
    metrics=[];detected=set();threshold=Decimal(threshold)
    for campaign_id in sorted(campaign_ids):
        ads=[x for x in meta if x.entity_id==campaign_id];web=[x for x in events if x.campaign_id==campaign_id]
        crm=[x for x in leads if x.campaign_id==campaign_id];sales=[x for x in orders if order_campaign(x)==campaign_id]
        spend=sum((Decimal(x.spend or 0) for x in ads),ZERO);platform_purchases=sum((Decimal(x.purchase or 0) for x in ads),ZERO)
        platform_revenue=sum((Decimal(x.revenue or 0) for x in ads),ZERO);sessions=sum(x.event_name=='session' for x in web)
        forms=sum(x.event_name=='form_submit' for x in web);analytics_purchases=sum(x.event_name=='purchase' for x in web)
        qualified=sum(stage_as_of.get(x.id,'lead') in ('qualified','appointment','sale') for x in crm)
        appointments=sum(stage_as_of.get(x.id,'lead') in ('appointment','sale') for x in crm);closed=sum(stage_as_of.get(x.id,'lead')=='sale' for x in crm)
        actual_revenue=sum((Decimal(x.revenue) for x in sales),ZERO);purchase_gap=discrepancy(platform_purchases,len(sales)) if order_ids else None
        revenue_gap=discrepancy(platform_revenue,actual_revenue) if order_ids else None;worst=max((x for x in (purchase_gap,revenue_gap) if x is not None),default=None)
        status='insufficient' if not order_ids else 'healthy' if worst<=threshold else 'watch' if worst<=threshold*2 else 'unhealthy'
        evidence={'period':[period_start.isoformat(),period_end.isoformat()],'attribution':ATTRIBUTION,'source_ids':sorted(x.id for x in sources),
            'deterministic_only':True,'order_source_connected':bool(order_ids),'unattributed_excluded':True}
        row=AttributionMetric(run_id=run.id,campaign_id=campaign_id,campaign_name=names.get(campaign_id),currency=account.currency,spend=spend,
            platform_purchases=platform_purchases,platform_revenue=platform_revenue,analytics_sessions=sessions,analytics_form_submits=forms,
            analytics_purchases=analytics_purchases,leads=len(crm),qualified_leads=qualified,appointments=appointments,sales=closed,
            actual_orders=len(sales),actual_revenue=actual_revenue,landing_cvr=ratio(forms,sessions,Decimal('100')),cpl=ratio(spend,len(crm)),
            cost_qualified_lead=ratio(spend,qualified),cost_appointment=ratio(spend,appointments),cac=ratio(spend,len(sales)),
            revenue_per_lead=ratio(actual_revenue,len(crm)),purchase_discrepancy_pct=purchase_gap,revenue_discrepancy_pct=revenue_gap,
            tracking_status=status,evidence=evidence);db.add(row);metrics.append(row)
        key=fingerprint(conn.id,account_id,campaign_id,'TRACKING_DISCREPANCY')
        if status=='unhealthy':
            detected.add(key);alert=await db.scalar(select(TrackingAlert).where(TrackingAlert.fingerprint==key))
            severity='critical' if worst>=Decimal('50') else 'warning';alert_evidence={**evidence,'platform_purchases':str(platform_purchases),
                'actual_orders':len(sales),'platform_revenue':str(platform_revenue),'actual_revenue':str(actual_revenue)}
            if not alert:
                alert=TrackingAlert(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,run_id=run.id,
                    account_id=account_id,campaign_id=campaign_id,severity=severity,discrepancy_pct=worst,fingerprint=key,evidence=alert_evidence);db.add(alert)
            else:
                was_resolved=alert.resolved;alert.connection_version=conn.version;alert.run_id=run.id;alert.severity=severity
                alert.discrepancy_pct=worst;alert.evidence=alert_evidence;alert.last_seen_at=now();alert.resolved=False
                if was_resolved:alert.acknowledged=False
    active=list(await db.scalars(select(TrackingAlert).where(TrackingAlert.connection_id==conn.id,TrackingAlert.account_id==account_id,TrackingAlert.resolved.is_(False))))
    for alert in active:
        if alert.fingerprint not in detected:alert.resolved=True;alert.last_seen_at=now()
    unattributed={'analytics':sum(x.campaign_id is None for x in events),'leads':sum(x.campaign_id is None for x in leads),'orders':sum(order_campaign(x) is None for x in orders)}
    await db.flush();run.summary={'campaigns_analyzed':len(metrics),'tracking_unhealthy':sum(x.tracking_status=='unhealthy' for x in metrics),
        'tracking_watch':sum(x.tracking_status=='watch' for x in metrics),'sources':{kind:sum(x.kind==kind for x in sources) for kind in ('ga4','crm','orders')},
        'unattributed':unattributed,'metric_ids':[x.id for x in metrics],'read_only':True,'optimization_blocked':bool(detected)}
    await db.flush();return run
