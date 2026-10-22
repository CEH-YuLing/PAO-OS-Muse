"""Typed warehouse translation. No metrics are summed across entity levels."""
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import delete, select
from .models import AdEntity, AdMetric, now
from .integrations.meta.client import MetaError

ATTRIBUTION='7d_click+1d_view;report=impression'
HOUR='hourly_stats_aggregated_by_advertiser_time_zone'


def number(value,integer=False):
    if value is None:return None
    try:
        if isinstance(value,bool):raise ValueError()
        result=Decimal(str(value))
        if not result.is_finite() or result<0 or result>=Decimal('1e18') or integer and result!=result.to_integral_value():raise ValueError()
        return int(result) if integer else result.quantize(Decimal('.000001'))
    except (InvalidOperation,ValueError,TypeError):raise MetaError('warehouse_invalid_number') from None


def ratio(a,b,multiplier=1):
    return number(Decimal(a)*multiplier/Decimal(b)) if a is not None and b is not None and b!=0 else None


def action(rows,aliases):
    if rows is None:return None
    if not isinstance(rows,list):raise MetaError('warehouse_invalid_actions')
    found={}
    for row in rows:
        if not isinstance(row,dict):raise MetaError('warehouse_invalid_actions')
        key=row.get('action_type')
        if key in found:raise MetaError('warehouse_duplicate_action')
        found[key]=row.get('value')
    # Broad events and their pixel/app aliases overlap: choose one, never sum aliases.
    for key in aliases:
        if key in found:return number(found[key])
    return None


def normalize_metric(payload,job,account,level):
    ident=payload.get(level+'_id')
    if not isinstance(ident,str) or not re.fullmatch(r'\d{1,64}',ident):raise MetaError('warehouse_invalid_entity')
    if str(payload.get('account_id','')).removeprefix('act_')!=job.account_id.removeprefix('act_'):raise MetaError('warehouse_account_mismatch')
    try:day=date.fromisoformat(payload['date_start'])
    except (ValueError,KeyError,TypeError):raise MetaError('warehouse_invalid_date') from None
    if payload.get('date_stop')!=day.isoformat() or not job.since<=day.isoformat()<=job.until:raise MetaError('warehouse_invalid_date')
    if payload.get('account_currency',account['currency'])!=account['currency']:raise MetaError('warehouse_currency_mismatch')
    hour=-1
    if job.granularity=='hourly':
        match=re.fullmatch(r'(\d{2}):00:00 - (\d{2}):59:59',str(payload.get(HOUR,'')))
        if not match or match[1]!=match[2] or not 0<=int(match[1])<=23:raise MetaError('warehouse_invalid_hour')
        hour=int(match[1])
    result=dict(connection_id=job.connection_id,connection_version=job.connection_version,account_id=job.account_id,
        level=level,entity_id=ident,campaign_id=payload.get('campaign_id'),adset_id=payload.get('adset_id'),day=day,hour=hour,
        granularity=job.granularity,currency=account['currency'],timezone=account['timezone_name'],attribution=ATTRIBUTION,
        source_job_id=job.id,updated_at=now())
    for field in ('spend','impressions','clicks','reach'):
        result[field]=number(payload.get(field),integer=field!='spend') if field!='reach' or job.granularity=='daily' else None
    result['link_clicks']=number(payload.get('inline_link_clicks'),True)
    for name,aliases in {'leads':['lead','offsite_conversion.fb_pixel_lead'],
        'add_to_cart':['add_to_cart','offsite_conversion.fb_pixel_add_to_cart'],
        'checkout':['initiate_checkout','offsite_conversion.fb_pixel_initiate_checkout'],
        'purchase':['purchase','omni_purchase','offsite_conversion.fb_pixel_purchase']}.items():
        result[name]=action(payload.get('actions'),aliases)
    result['revenue']=action(payload.get('action_values'),['purchase','omni_purchase','offsite_conversion.fb_pixel_purchase'])
    result['conversions']=result['purchase'];result['conversion_value']=result['revenue']
    for field,a,b,m in [('ctr','clicks','impressions',100),('cpc','spend','clicks',1),('cpm','spend','impressions',1000),
        ('frequency','impressions','reach',1),('cpl','spend','leads',1),('cpa','spend','purchase',1),('roas','revenue','spend',1)]:
        result[field]=ratio(result[a],result[b],m)
    return result


async def fetch_warehouse(client,job):
    entities=[];metrics=[];seen=set();budget=0;account=None
    def count(row):
        nonlocal budget
        budget+=len(json.dumps(row,default=str).encode())
        if budget>16_000_000 or len(entities)+len(metrics)>10000:raise MetaError('warehouse_limit_reduce_range')
    if getattr(job,'authority_pin',None) is not None:
        account=await client.account(job.account_id);count(account)
    else:
        async for row in client.rows('accounts'):
            count(row)
            if row.get('id')==job.account_id:account=row
    if not account:raise MetaError('warehouse_account_unavailable')
    if not re.fullmatch(r'[A-Z]{3}',str(account.get('currency',''))):raise MetaError('warehouse_currency_missing')
    try:ZoneInfo(account['timezone_name'])
    except (KeyError,TypeError,ValueError,ZoneInfoNotFoundError):raise MetaError('warehouse_timezone_missing') from None
    def entity(row,kind,parent=None):
        ident=row.get('id')
        if not isinstance(ident,str) or not re.fullmatch(r'(act_)?\d{1,64}',ident):raise MetaError('warehouse_invalid_entity')
        key=(kind,ident)
        if key in seen:return
        seen.add(key)
        creative=row.get('creative') or {}
        entities.append(dict(connection_id=job.connection_id,connection_version=job.connection_version,account_id=job.account_id,
            kind=kind,remote_id=ident,parent_id=parent,creative_id=creative.get('id'),name=row.get('name'),
            status=row.get('effective_status') or str(row['account_status']) if 'account_status' in row else row.get('effective_status') or row.get('status'),
            objective=row.get('objective'),currency=account['currency'],timezone=account['timezone_name'],source_job_id=job.id,updated_at=now()))
    entity(account,'account')
    for kind in ('campaign','adset','ad'):
        async for row in client.rows({'campaign':'campaigns','adset':'adsets','ad':'ads'}[kind],job.account_id):
            count(row)
            if str(row.get('account_id','')).removeprefix('act_')!=job.account_id.removeprefix('act_'):raise MetaError('warehouse_account_mismatch')
            entity(row,kind,job.account_id if kind=='campaign' else row.get('campaign_id' if kind=='adset' else 'adset_id'))
            if kind=='ad' and row.get('creative'):entity(row['creative'],'creative')
    keys=set()
    for level in ('campaign','adset','ad'):
        start=date.fromisoformat(job.since);end=date.fromisoformat(job.until)
        while start<=end:
            last=min(start+timedelta(days=6 if job.granularity=='daily' else 0),end)
            async for row in client.rows('insights',job.account_id,start.isoformat(),last.isoformat(),level=level,granularity=job.granularity,warehouse=True):
                count(row);metric=normalize_metric(row,job,account,level)
                key=(level,metric['entity_id'],metric['day'],metric['hour'])
                if key in keys:raise MetaError('warehouse_duplicate_metric')
                keys.add(key);metrics.append(metric)
            start=last+timedelta(days=1)
    return entities,metrics


async def publish_warehouse(db,job,entities,metrics):
    # Replace exactly the fully fetched coverage in one transaction. Restatements can
    # remove previously reported rows; upsert alone would retain those stale values.
    scope=[AdMetric.connection_id==job.connection_id,AdMetric.connection_version==job.connection_version,
        AdMetric.account_id==job.account_id,AdMetric.granularity==job.granularity,
        AdMetric.day>=date.fromisoformat(job.since),AdMetric.day<=date.fromisoformat(job.until),AdMetric.attribution==ATTRIBUTION]
    await db.execute(delete(AdMetric).where(*scope))
    await db.execute(delete(AdEntity).where(AdEntity.connection_id==job.connection_id,
        AdEntity.connection_version==job.connection_version,AdEntity.account_id==job.account_id))
    db.add_all([AdEntity(**row) for row in entities]);db.add_all([AdMetric(**row) for row in metrics])
