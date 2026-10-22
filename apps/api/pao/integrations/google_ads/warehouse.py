"""Translate Google Ads GAQL responses into the shared Ads Warehouse model."""
from datetime import date
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from sqlalchemy import delete
from ...models import AdEntity,AdMetric,now
from .client import GoogleAdsError

ATTRIBUTION='google_ads;primary_conversions;report=interaction'
def num(value,integer=False):
    if value is None:return None
    try:
        if isinstance(value,bool):raise ValueError()
        result=Decimal(str(value))
        if not result.is_finite() or result<0 or result>=Decimal('1e18') or integer and result!=result.to_integral_value():raise ValueError()
        return int(result) if integer else result.quantize(Decimal('.000001'))
    except (InvalidOperation,ValueError,TypeError):raise GoogleAdsError('google_ads_invalid_number') from None
def ratio(a,b,m=1):return num(Decimal(a)*m/Decimal(b)) if a is not None and b not in (None,0) else None
def common(job):return dict(connection_id=None,google_connection_id=job.connection_id,connection_version=job.connection_version,platform='google',account_id=job.account_id,source_job_id=None,google_source_job_id=job.id,updated_at=now())
async def one(client,token,customer,query):
    rows=[x async for x in client.search(token,customer,query)]
    if len(rows)!=1:raise GoogleAdsError('google_ads_account_unavailable')
    return rows[0]
async def account_row(client,token,customer):
    row=await one(client,token,customer,'SELECT customer.id, customer.descriptive_name, customer.currency_code, customer.time_zone, customer.status, customer.manager FROM customer LIMIT 1');c=row.get('customer',{})
    if str(c.get('id'))!=customer or not isinstance(c.get('currencyCode'),str) or len(c['currencyCode'])!=3:raise GoogleAdsError('google_ads_invalid_account')
    try:ZoneInfo(c['timeZone'])
    except (KeyError,TypeError,ValueError,ZoneInfoNotFoundError):raise GoogleAdsError('google_ads_invalid_account') from None
    return c
async def fetch_accounts(client,refresh,job):
    token,ids=await client.accessible(refresh);entities=[]
    for customer in ids:
        c=await account_row(client,token,customer);entities.append(dict(common(job),account_id=customer,kind='account',remote_id=customer,parent_id=None,creative_id=None,name=c.get('descriptiveName'),status=c.get('status'),objective=None,currency=c['currencyCode'],timezone=c['timeZone']))
    return entities
async def fetch_historical(client,refresh,job):
    if getattr(job,'authority_pin',None) is not None:
        token=await client.access(refresh)
    else:
        token,accessible=await client.accessible(refresh)
        if job.account_id not in accessible:raise GoogleAdsError('google_ads_account_scope_mismatch')
    account=await account_row(client,token,job.account_id);currency=account['currencyCode'];tz=account['timeZone'];entities=[];metrics=[];seen=set()
    base=common(job)
    def add(kind,ident,parent,name,status,objective=None):
        ident=str(ident)
        if not ident.isdecimal() or len(ident)>64:raise GoogleAdsError('google_ads_invalid_entity')
        key=(kind,ident)
        if key in seen:return
        seen.add(key);entities.append(dict(base,kind=kind,remote_id=ident,parent_id=str(parent) if parent is not None else None,creative_id=None,name=name,status=status,objective=objective,currency=currency,timezone=tz))
    add('account',job.account_id,None,account.get('descriptiveName'),account.get('status'))
    entity_queries={
      'campaign':'SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type FROM campaign',
      'adset':'SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status FROM ad_group',
      'ad':'SELECT campaign.id, ad_group.id, ad_group_ad.ad.id, ad_group_ad.status FROM ad_group_ad'}
    for level,query in entity_queries.items():
        async for row in client.search(token,job.account_id,query):
            if level=='campaign':x=row.get('campaign',{});add(level,x.get('id'),job.account_id,x.get('name'),x.get('status'),x.get('advertisingChannelType'))
            elif level=='adset':x=row.get('adGroup',{});add(level,x.get('id'),row.get('campaign',{}).get('id'),x.get('name'),x.get('status'))
            else:x=row.get('adGroupAd',{});add(level,x.get('ad',{}).get('id'),row.get('adGroup',{}).get('id'),None,x.get('status'))
    segment='segments.date'+(', segments.hour' if job.granularity=='hourly' else '')
    resources={'campaign':('campaign','campaign.id'),'adset':('ad_group','campaign.id, ad_group.id'),'ad':('ad_group_ad','campaign.id, ad_group.id, ad_group_ad.ad.id')}
    for level,(resource,fields) in resources.items():
        query=f"SELECT {fields}, {segment}, metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions, metrics.conversions_value FROM {resource} WHERE segments.date BETWEEN '{job.since}' AND '{job.until}'"
        async for row in client.search(token,job.account_id,query):
            seg=row.get('segments',{});met=row.get('metrics',{});campaign=str(row.get('campaign',{}).get('id',''));adgroup=str(row.get('adGroup',{}).get('id','')) or None
            ident=campaign if level=='campaign' else adgroup if level=='adset' else str(row.get('adGroupAd',{}).get('ad',{}).get('id',''))
            try:day=date.fromisoformat(seg['date'])
            except Exception:raise GoogleAdsError('google_ads_invalid_date') from None
            hour=num(seg.get('hour'),True) if job.granularity=='hourly' else -1
            if not job.since<=day.isoformat()<=job.until or job.granularity=='hourly' and not 0<=hour<=23:raise GoogleAdsError('google_ads_invalid_date')
            cost=num(met.get('costMicros'));spend=num(cost/Decimal(1_000_000)) if cost is not None else None;impressions=num(met.get('impressions'),True);clicks=num(met.get('clicks'),True);conv=num(met.get('conversions'));value=num(met.get('conversionsValue'))
            metrics.append(dict(base,level=level,entity_id=ident,campaign_id=campaign or None,adset_id=adgroup,day=day,hour=hour,granularity=job.granularity,currency=currency,timezone=tz,attribution=ATTRIBUTION,spend=spend,impressions=impressions,reach=None,clicks=clicks,link_clicks=None,frequency=None,ctr=ratio(clicks,impressions,100),cpc=ratio(spend,clicks),cpm=ratio(spend,impressions,1000),leads=None,add_to_cart=None,checkout=None,purchase=None,revenue=None,conversions=conv,conversion_value=value,cpl=None,cpa=ratio(spend,conv),roas=ratio(value,spend)))
    if len(entities)+len(metrics)>10000:raise GoogleAdsError('google_ads_row_limit_reduce_range')
    return entities,metrics
async def publish_accounts(db,job,entities):
    await db.execute(delete(AdEntity).where(AdEntity.google_connection_id==job.connection_id,AdEntity.connection_version==job.connection_version,AdEntity.platform=='google',AdEntity.kind=='account'))
    db.add_all([AdEntity(**x) for x in entities])
async def publish_historical(db,job,entities,metrics):
    scope=[AdMetric.google_connection_id==job.connection_id,AdMetric.connection_version==job.connection_version,AdMetric.platform=='google',AdMetric.account_id==job.account_id,AdMetric.granularity==job.granularity,AdMetric.day>=date.fromisoformat(job.since),AdMetric.day<=date.fromisoformat(job.until),AdMetric.attribution==ATTRIBUTION]
    await db.execute(delete(AdMetric).where(*scope));await db.execute(delete(AdEntity).where(AdEntity.google_connection_id==job.connection_id,AdEntity.connection_version==job.connection_version,AdEntity.account_id==job.account_id));db.add_all([AdEntity(**x) for x in entities]);db.add_all([AdMetric(**x) for x in metrics])
