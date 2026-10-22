"""Deterministic ads reports over normalized daily campaign metrics."""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from .models import (AdEntity, AdMetric, AdReport, AdReportDelivery, AttributionMetric,
    AttributionRun, TelegramDelivery, TelegramPeer, now)
from .warehouse import ATTRIBUTION


def divide(a,b):
    return (Decimal(a)/Decimal(b)).quantize(Decimal('.000001')) if a is not None and b not in (None,0) else None


def add(values):
    present=[value for value in values if value is not None]
    return sum(present,Decimal(0)) if present else None


def add_count(values):
    present=[value for value in values if value is not None]
    return sum(present,0) if present else None


def pct(current,baseline):
    return ((Decimal(current)-Decimal(baseline))/Decimal(baseline)*100).quantize(Decimal('.000001')) if current is not None and baseline not in (None,0) else None


def periods(kind,end):
    days=1 if kind=='daily' else 7
    start=end-timedelta(days=days-1)
    previous_end=start-timedelta(days=1)
    previous_start=previous_end-timedelta(days=days-1)
    # Daily also compares with the seven complete days before the report date.
    average_start=end-timedelta(days=7) if kind=='daily' else previous_start
    return start,end,previous_start,previous_end,average_start


async def aggregate(db,conn,account_id,start,end):
    rows=list((await db.execute(select(AdMetric.entity_id,
        func.sum(AdMetric.spend),func.sum(AdMetric.revenue),func.sum(AdMetric.purchase),func.sum(AdMetric.leads),
        func.sum(AdMetric.impressions),func.sum(AdMetric.clicks),func.count(func.distinct(AdMetric.day)),func.max(AdMetric.updated_at))
        .where(AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,AdMetric.account_id==account_id,
            AdMetric.level=='campaign',AdMetric.granularity=='daily',AdMetric.attribution==ATTRIBUTION,
            AdMetric.day>=start,AdMetric.day<=end)
        .group_by(AdMetric.entity_id))).all())
    totals={key:add(row[index] for row in rows) for index,key in enumerate(('spend','revenue','purchases','leads'),start=1)}
    totals.update({key:add_count(row[index] for row in rows) for index,key in ((5,'impressions'),(6,'clicks'))})
    totals['coverage_days']=await db.scalar(select(func.count(func.distinct(AdMetric.day))).where(AdMetric.connection_id==conn.id,
        AdMetric.connection_version==conn.version,AdMetric.account_id==account_id,AdMetric.level=='campaign',
        AdMetric.granularity=='daily',AdMetric.attribution==ATTRIBUTION,AdMetric.day>=start,AdMetric.day<=end)) or 0
    totals['source_updated_at']=max((row[8] for row in rows if row[8]),default=now())
    totals['data_through']=await db.scalar(select(func.max(AdMetric.day)).where(AdMetric.connection_id==conn.id,
        AdMetric.connection_version==conn.version,AdMetric.account_id==account_id,AdMetric.level=='campaign',
        AdMetric.granularity=='daily',AdMetric.attribution==ATTRIBUTION,AdMetric.day>=start,AdMetric.day<=end))
    totals['campaign_rows']=rows
    return totals


async def build_report(db,conn,user_id,account_id,kind,end,request_key):
    start,end,previous_start,previous_end,average_start=periods(kind,end)
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==account_id,AdEntity.kind=='account'))
    if not account:raise ValueError('report_account_unavailable')
    current=await aggregate(db,conn,account_id,start,end)
    if not current['campaign_rows']:raise ValueError('report_data_unavailable')
    previous=await aggregate(db,conn,account_id,previous_start,previous_end)
    average=await aggregate(db,conn,account_id,average_start,end-timedelta(days=1))
    names=dict((await db.execute(select(AdEntity.remote_id,AdEntity.name).where(AdEntity.connection_id==conn.id,
        AdEntity.connection_version==conn.version,AdEntity.account_id==account_id,AdEntity.kind=='campaign'))).all())
    campaigns=[]
    for row in current['campaign_rows']:
        spend,revenue,purchases=row[1],row[2],row[3]
        campaigns.append({'id':row[0],'name':names.get(row[0]),'spend':str(spend) if spend is not None else None,
            'revenue':str(revenue) if revenue is not None else None,'purchases':str(purchases) if purchases is not None else None,
            'roas':str(divide(revenue,spend)) if divide(revenue,spend) is not None else None})
    campaigns.sort(key=lambda item:(Decimal(item['spend']) if item['spend'] is not None else Decimal(-1),item['id']),reverse=True)
    comparisons={}
    previous_complete=previous['coverage_days']==(previous_end-previous_start).days+1
    average_complete=average['coverage_days']==7
    for key in ('spend','revenue','purchases'):
        prior=pct(current[key],previous[key]) if previous_complete else None
        comparisons[key]={'previous_period_pct':str(prior) if prior is not None else None}
        if kind=='daily':
            baseline=Decimal(average[key])/7 if average_complete and average[key] is not None else None
            comparisons[key]['previous_7d_average_pct']=str(pct(current[key],baseline)) if pct(current[key],baseline) is not None else None
    attribution_run=await db.scalar(select(AttributionRun).where(AttributionRun.connection_id==conn.id,
        AttributionRun.connection_version==conn.version,AttributionRun.account_id==account_id,
        AttributionRun.period_start==start,AttributionRun.period_end==end).order_by(AttributionRun.created_at.desc()).limit(1))
    if attribution_run:
        business=list(await db.scalars(select(AttributionMetric).where(AttributionMetric.run_id==attribution_run.id)))
        actual_orders=sum((row.actual_orders for row in business),0);actual_revenue=sum((Decimal(row.actual_revenue) for row in business),Decimal(0))
        crm_leads=sum((row.leads for row in business),0);unhealthy=sum(row.tracking_status=='unhealthy' for row in business)
        comparisons['business']={'attribution_run_id':attribution_run.id,'actual_orders':actual_orders,'actual_revenue':str(actual_revenue),
            'crm_leads':crm_leads,'cac':str(divide(current['spend'],actual_orders)) if divide(current['spend'],actual_orders) is not None else None,
            'revenue_per_lead':str(divide(actual_revenue,crm_leads)) if divide(actual_revenue,crm_leads) is not None else None,
            'tracking_unhealthy_campaigns':unhealthy,'optimization_blocked':unhealthy>0}
    report=AdReport(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,user_id=user_id,
        account_id=account_id,request_key=request_key,kind=kind,period_start=start,period_end=end,currency=account.currency,
        timezone=account.timezone,attribution=ATTRIBUTION,spend=current['spend'],revenue=current['revenue'],
        purchases=current['purchases'],leads=current['leads'],impressions=current['impressions'],clicks=current['clicks'],
        roas=divide(current['revenue'],current['spend']),cpa=divide(current['spend'],current['purchases']),
        comparison=comparisons,campaigns=campaigns[:10],coverage_days=current['coverage_days'],
        expected_days=(end-start).days+1,data_through=current['data_through'],source_updated_at=current['source_updated_at'])
    db.add(report);await db.flush();return report


def value(value,currency=False):
    if value is None:return '—'
    return f'{Decimal(value):,.2f}' if currency else f'{Decimal(value):,.3f}'.rstrip('0').rstrip('.')


def report_text(report):
    heading='DAILY' if report.kind=='daily' else 'WEEKLY'
    lines=[f'META ADS — {heading}',f'{report.period_start} → {report.period_end}',
        f'Dữ liệu: {report.coverage_days}/{report.expected_days} ngày · {report.currency} · {report.timezone}',
        f'Spend: {value(report.spend,True)} {report.currency}',f'Revenue: {value(report.revenue,True)} {report.currency}',
        f'ROAS: {value(report.roas)}',f'CPA (purchase): {value(report.cpa,True)} {report.currency}',
        '', 'SO SÁNH']
    for metric,label in [('spend','Spend'),('revenue','Revenue'),('purchases','Purchase')]:
        item=report.comparison.get(metric,{})
        lines.append(f'{label} vs kỳ trước: {value(item.get("previous_period_pct"))}%')
        if report.kind=='daily':lines.append(f'{label} vs TB 7 ngày trước: {value(item.get("previous_7d_average_pct"))}%')
    lines+=['','TOP CAMPAIGNS THEO SPEND']
    for index,item in enumerate(report.campaigns[:5],1):
        lines.append(f'{index}. {item.get("name") or item["id"]} · Spend {value(item.get("spend"),True)} · ROAS {value(item.get("roas"))}')
    business=report.comparison.get('business')
    if business:
        lines+=['','BUSINESS VALUE',f'Actual orders: {business.get("actual_orders")}',
            f'Actual revenue: {value(business.get("actual_revenue"),True)} {report.currency}',
            f'CAC: {value(business.get("cac"),True)} {report.currency}',f'Revenue/lead: {value(business.get("revenue_per_lead"),True)} {report.currency}',
            f'Tracking unhealthy campaigns: {business.get("tracking_unhealthy_campaigns")}']
    else:lines+=['','BUSINESS VALUE: chưa có Attribution run khớp chính xác kỳ báo cáo (Phase 15)']
    lines+=['','UNDERPERFORMERS: chưa đánh giá (Phase 10)','CREATIVE FATIGUE: chưa đánh giá (Phase 14)',
        'RECOMMENDATIONS: chưa đánh giá (Phase 10)','ACTIONS TAKEN: không có; hệ thống chỉ đọc']
    if report.kind=='weekly':
        lines+=['WINNING/LOSING CAMPAIGNS: chưa phân loại (Phase 10)',
            'CREATIVE WINNERS: chưa đánh giá (Phase 14)',
            'BUDGET MOVEMENT: chưa có dữ liệu (Phase 11)','EXPERIMENTS: chưa triển khai',
            'PREVIOUS DECISIONS: chưa có Ads actions','NEXT WEEK RECOMMENDATIONS: chưa đánh giá (Phase 10)']
    return '\n'.join(lines)


async def queue_report(db,report,peer,queue):
    existing=await db.scalar(select(AdReportDelivery).where(AdReportDelivery.report_id==report.id,AdReportDelivery.peer_id==peer.id))
    if existing:return existing
    delivery=AdReportDelivery(report_id=report.id,peer_id=peer.id,dedup_prefix=f'ads-report:{report.id}')
    db.add(delivery);await db.flush();await queue(db,peer,delivery.dedup_prefix,report_text(report));return delivery


async def delivery_status(db,delivery):
    peer=await db.get(TelegramPeer,delivery.peer_id)
    if peer and peer.connection_id is not None:
        from .models import ChannelBinding,ChannelOutbox
        rows=list(await db.scalars(select(ChannelOutbox.status).join(ChannelBinding,ChannelBinding.id==ChannelOutbox.binding_id).where(
            ChannelBinding.peer_id==peer.id,ChannelOutbox.connection_id==peer.connection_id,
            ChannelOutbox.request_key.in_(['ads-report:'+delivery.report_id]) | ChannelOutbox.request_key.startswith('ads-report:'+delivery.report_id+':p:'))))
        if not rows:return 'missing'
        if 'unknown' in rows or 'sending' in rows:return 'unknown'
        if any(x in ('failed','cancelled') for x in rows):return 'failed'
        return 'sent' if all(x=='sent' for x in rows) else 'queued'
    rows=list(await db.scalars(select(TelegramDelivery.status).where(TelegramDelivery.dedup_key.startswith(delivery.dedup_prefix+':'))))
    if not rows:return 'missing'
    if any(x=='unknown' for x in rows):return 'unknown'
    if any(x in ('failed','cancelled') for x in rows):return 'failed'
    if all(x=='sent' for x in rows):return 'sent'
    return 'queued'


def next_delivery(account_timezone,kind,hour,weekday,after=None):
    zone=ZoneInfo(account_timezone);local=(after or now()).astimezone(zone)
    candidate=datetime.combine(local.date(),time(hour),zone)
    if kind=='daily':
        if candidate<=local:candidate+=timedelta(days=1)
    else:
        candidate+=timedelta(days=(weekday-candidate.weekday())%7)
        if candidate<=local:candidate+=timedelta(days=7)
    return candidate.astimezone(timezone.utc)
