import hashlib,json
from datetime import date,datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .attribution import analyze
from .auth import Principal,principal,rate_limit
from .db import database
from .integrations.meta.api import connection
from .models import (AdEntity,AnalyticsEvent,AttributionMetric,AttributionRun,AttributionSource,
    BusinessOrder,CrmLead,CrmStageEvent,TrackingAlert,now)

router=APIRouter(prefix='/v1/attribution',tags=['attribution-crm'])

def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()
def aware(value):
    if value.tzinfo is None or value.utcoffset() is None:raise ValueError('Timestamp phải có timezone')
    return value

class SourceInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID;account_id: str=Field(pattern=r'^act_[0-9]{1,32}$');kind: Literal['ga4','crm','orders'];name: str=Field(min_length=1,max_length=120)

class SourceOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;account_id: str;kind: str;name: str;currency: str;timezone: str;enabled: bool;version: int;updated_at: datetime;created_at: datetime

class AnalyticsEventInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_id: str=Field(min_length=1,max_length=180);occurred_at: datetime;event_name: Literal['session','bounce','scroll','cta_click','form_start','form_submit','checkout','purchase']
    visitor_ref_hash: str|None=Field(None,pattern=r'^[a-f0-9]{64}$');session_ref_hash: str|None=Field(None,pattern=r'^[a-f0-9]{64}$')
    campaign_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$');adset_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$');ad_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$')
    utm_source: str|None=Field(None,max_length=120);utm_medium: str|None=Field(None,max_length=120);utm_campaign: str|None=Field(None,max_length=180)
    value: Decimal|None=Field(None,ge=0,max_digits=24,decimal_places=6);currency: str|None=Field(None,pattern=r'^[A-Z]{3}$')
    _tz=field_validator('occurred_at')(aware)

class LeadInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_id: str=Field(min_length=1,max_length=180);customer_ref_hash: str|None=Field(None,pattern=r'^[a-f0-9]{64}$');acquired_at: datetime
    campaign_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$');adset_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$');ad_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$')
    utm_source: str|None=Field(None,max_length=120);utm_medium: str|None=Field(None,max_length=120);utm_campaign: str|None=Field(None,max_length=180)
    _tz=field_validator('acquired_at')(aware)

class StageInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_id: str=Field(min_length=1,max_length=180);lead_external_id: str=Field(min_length=1,max_length=180)
    stage: Literal['lead','qualified','appointment','sale','lost'];occurred_at: datetime
    _tz=field_validator('occurred_at')(aware)

class OrderInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    external_id: str=Field(min_length=1,max_length=180);version: int=Field(0,ge=0);occurred_at: datetime
    status: Literal['pending','paid','refunded','cancelled'];revenue: Decimal=Field(ge=0,max_digits=24,decimal_places=6);currency: str=Field(pattern=r'^[A-Z]{3}$')
    customer_ref_hash: str|None=Field(None,pattern=r'^[a-f0-9]{64}$');lead_external_id: str|None=Field(None,max_length=180)
    campaign_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$');adset_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$');ad_id: str|None=Field(None,pattern=r'^[0-9]{1,64}$')
    attribution_method: Literal['campaign_id','lead_link','utm','unattributed']='unattributed'
    _tz=field_validator('occurred_at')(aware)
    @model_validator(mode='after')
    def attribution_key(self):
        if self.attribution_method=='campaign_id' and not self.campaign_id:raise ValueError('campaign_id attribution cần campaign_id')
        if self.attribution_method=='lead_link' and not self.lead_external_id:raise ValueError('lead_link attribution cần lead_external_id')
        if self.attribution_method=='utm' and not self.campaign_id:raise ValueError('utm attribution phải được nguồn resolve sang campaign_id')
        return self

class ImportResult(BaseModel):inserted: int;updated: int=0;unchanged: int;total: int
class EventBatch(BaseModel):model_config=ConfigDict(extra='forbid');rows:list[AnalyticsEventInput]=Field(min_length=1,max_length=500)
class LeadBatch(BaseModel):model_config=ConfigDict(extra='forbid');rows:list[LeadInput]=Field(min_length=1,max_length=500)
class StageBatch(BaseModel):model_config=ConfigDict(extra='forbid');rows:list[StageInput]=Field(min_length=1,max_length=500)
class OrderBatch(BaseModel):model_config=ConfigDict(extra='forbid');rows:list[OrderInput]=Field(min_length=1,max_length=500)

class AnalyzeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID;account_id: str=Field(pattern=r'^act_[0-9]{1,32}$');period_start: date;period_end: date;request_key: UUID
    discrepancy_threshold_pct: Decimal=Field(25,ge=1,le=100,max_digits=7,decimal_places=3)

class AttributionRunOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;account_id: str;period_start: date;period_end: date;discrepancy_threshold_pct: Decimal;analyst_version: str;summary: dict;source_updated_at: datetime;created_at: datetime

class AttributionMetricOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;campaign_id: str;campaign_name: str|None;currency: str;spend: Decimal;platform_purchases: Decimal;platform_revenue: Decimal
    analytics_sessions: int;analytics_form_submits: int;analytics_purchases: int;leads: int;qualified_leads: int;appointments: int;sales: int
    actual_orders: int;actual_revenue: Decimal;landing_cvr: Decimal|None;cpl: Decimal|None;cost_qualified_lead: Decimal|None
    cost_appointment: Decimal|None;cac: Decimal|None;revenue_per_lead: Decimal|None;purchase_discrepancy_pct: Decimal|None
    revenue_discrepancy_pct: Decimal|None;tracking_status: str;evidence: dict

class TrackingAlertOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;run_id: str;account_id: str;campaign_id: str;severity: str;discrepancy_pct: Decimal|None;evidence: dict
    acknowledged: bool;resolved: bool;first_seen_at: datetime;last_seen_at: datetime

class AttributionDashboardOut(BaseModel):
    run: AttributionRunOut|None;sources:list[SourceOut];metrics:list[AttributionMetricOut];alerts:list[TrackingAlertOut];read_only: bool=True

async def get_source(db,who,workspace_id,source_id,kind):
    conn=await connection(db,who,workspace_id,True);row=await db.get(AttributionSource,str(source_id))
    if not conn or not row or row.connection_id!=conn.id or row.connection_version!=conn.version or row.kind!=kind or not row.enabled:raise HTTPException(404,'Không tìm thấy nguồn dữ liệu đang hoạt động')
    return row

@router.post('/sources',response_model=SourceOut,status_code=201)
async def create_source(body: SourceInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,body.workspace_id,True)
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,AdEntity.account_id==body.account_id,AdEntity.kind=='account')) if conn else None
    if not account:raise HTTPException(409,'Kết nối Meta và đồng bộ account trước')
    old=await db.scalar(select(AttributionSource).where(AttributionSource.connection_id==conn.id,AttributionSource.account_id==body.account_id,AttributionSource.kind==body.kind,AttributionSource.name==body.name))
    if old:return old
    row=AttributionSource(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,account_id=body.account_id,
        kind=body.kind,name=body.name,currency=account.currency,timezone=account.timezone,updated_by=who.id);db.add(row);await db.commit();return row

@router.get('/sources',response_model=list[SourceOut])
async def sources(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    return list(await db.scalars(select(AttributionSource).where(AttributionSource.connection_id==conn.id,AttributionSource.connection_version==conn.version,
        AttributionSource.account_id==account_id).order_by(AttributionSource.kind,AttributionSource.name))) if conn else []

@router.post('/sources/{source_id}/analytics',response_model=ImportResult)
async def import_analytics(source_id: UUID,workspace_id: UUID,body: EventBatch,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    source=await get_source(db,who,workspace_id,source_id,'ga4');inserted=unchanged=0
    for item in body.rows:
        data=item.model_dump(mode='json');key=digest(data);old=await db.scalar(select(AnalyticsEvent).where(AnalyticsEvent.source_id==source.id,AnalyticsEvent.external_id==item.external_id))
        if old:
            if old.fingerprint!=key:raise HTTPException(409,f'event_conflict:{item.external_id}')
            unchanged+=1;continue
        if item.currency and item.currency!=source.currency:raise HTTPException(422,'event_currency_mismatch')
        db.add(AnalyticsEvent(source_id=source.id,workspace_id=source.workspace_id,fingerprint=key,**item.model_dump()));inserted+=1
    await db.commit();return ImportResult(inserted=inserted,unchanged=unchanged,total=len(body.rows))

@router.post('/sources/{source_id}/leads',response_model=ImportResult)
async def import_leads(source_id: UUID,workspace_id: UUID,body: LeadBatch,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    source=await get_source(db,who,workspace_id,source_id,'crm');inserted=unchanged=0
    for item in body.rows:
        data=item.model_dump(mode='json');key=digest(data);old=await db.scalar(select(CrmLead).where(CrmLead.source_id==source.id,CrmLead.external_id==item.external_id))
        if old:
            if old.fingerprint!=key:raise HTTPException(409,f'lead_conflict:{item.external_id}')
            unchanged+=1;continue
        lead=CrmLead(source_id=source.id,workspace_id=source.workspace_id,fingerprint=key,stage='lead',stage_at=item.acquired_at,**item.model_dump());db.add(lead);await db.flush()
        db.add(CrmStageEvent(source_id=source.id,lead_id=lead.id,workspace_id=source.workspace_id,external_id=f'lead:{item.external_id}',fingerprint=key,stage='lead',occurred_at=item.acquired_at));inserted+=1
    await db.commit();return ImportResult(inserted=inserted,unchanged=unchanged,total=len(body.rows))

@router.post('/sources/{source_id}/stages',response_model=ImportResult)
async def import_stages(source_id: UUID,workspace_id: UUID,body: StageBatch,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    source=await get_source(db,who,workspace_id,source_id,'crm');inserted=unchanged=0
    for item in body.rows:
        data=item.model_dump(mode='json');key=digest(data);old=await db.scalar(select(CrmStageEvent).where(CrmStageEvent.source_id==source.id,CrmStageEvent.external_id==item.external_id))
        if old:
            if old.fingerprint!=key:raise HTTPException(409,f'stage_conflict:{item.external_id}')
            unchanged+=1;continue
        lead=await db.scalar(select(CrmLead).where(CrmLead.source_id==source.id,CrmLead.external_id==item.lead_external_id).with_for_update())
        if not lead:raise HTTPException(409,f'lead_missing:{item.lead_external_id}')
        db.add(CrmStageEvent(source_id=source.id,lead_id=lead.id,workspace_id=source.workspace_id,external_id=item.external_id,fingerprint=key,stage=item.stage,occurred_at=item.occurred_at))
        if item.occurred_at>=lead.stage_at:lead.stage=item.stage;lead.stage_at=item.occurred_at;lead.version+=1;lead.updated_at=now()
        inserted+=1
    await db.commit();return ImportResult(inserted=inserted,unchanged=unchanged,total=len(body.rows))

@router.post('/sources/{source_id}/orders',response_model=ImportResult)
async def import_orders(source_id: UUID,workspace_id: UUID,body: OrderBatch,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    source=await get_source(db,who,workspace_id,source_id,'orders');inserted=updated=unchanged=0
    for item in body.rows:
        if item.currency!=source.currency:raise HTTPException(422,'order_currency_mismatch')
        data=item.model_dump(exclude={'version'},mode='json');key=digest(data);old=await db.scalar(select(BusinessOrder).where(BusinessOrder.source_id==source.id,BusinessOrder.external_id==item.external_id).with_for_update())
        if old:
            if old.fingerprint==key:unchanged+=1;continue
            if old.version!=item.version:raise HTTPException(409,f'order_version_conflict:{item.external_id}')
            for field,value in item.model_dump(exclude={'version','external_id'}).items():setattr(old,field,value)
            old.fingerprint=key;old.version+=1;old.updated_at=now();updated+=1;continue
        if item.version!=0:raise HTTPException(409,f'order_version_conflict:{item.external_id}')
        db.add(BusinessOrder(source_id=source.id,workspace_id=source.workspace_id,fingerprint=key,**item.model_dump(exclude={'version'})));inserted+=1
    await db.commit();return ImportResult(inserted=inserted,updated=updated,unchanged=unchanged,total=len(body.rows))

async def detail(db,conn,account_id,run=None):
    sources=list(await db.scalars(select(AttributionSource).where(AttributionSource.connection_id==conn.id,AttributionSource.connection_version==conn.version,AttributionSource.account_id==account_id).order_by(AttributionSource.kind)))
    if run is None:run=await db.scalar(select(AttributionRun).where(AttributionRun.connection_id==conn.id,AttributionRun.connection_version==conn.version,AttributionRun.account_id==account_id).order_by(AttributionRun.created_at.desc()).limit(1))
    metrics=list(await db.scalars(select(AttributionMetric).where(AttributionMetric.run_id==run.id).order_by(AttributionMetric.cac,AttributionMetric.campaign_id))) if run else []
    alerts=list(await db.scalars(select(TrackingAlert).where(TrackingAlert.connection_id==conn.id,TrackingAlert.connection_version==conn.version,TrackingAlert.account_id==account_id,TrackingAlert.resolved.is_(False)).order_by(TrackingAlert.severity,TrackingAlert.last_seen_at.desc())))
    return AttributionDashboardOut(run=run,sources=sources,metrics=metrics,alerts=alerts)

@router.post('/analyze',response_model=AttributionDashboardOut,status_code=201)
async def analyze_now(body: AnalyzeInput,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    if not 0<=(body.period_end-body.period_start).days<366:raise HTTPException(422,'Khoảng phân tích tối đa 366 ngày')
    await rate_limit(request.app.state.redis,'attribution-intelligence',who.id,10,60);conn=await connection(db,who,body.workspace_id,True)
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,AdEntity.account_id==body.account_id,AdEntity.kind=='account')) if conn else None
    if not account:raise HTTPException(409,'Kết nối Meta và đồng bộ warehouse trước')
    if body.period_end>=now().astimezone(ZoneInfo(account.timezone)).date():raise HTTPException(422,'Chỉ phân tích ngày đã hoàn tất')
    key=str(body.request_key);old=await db.scalar(select(AttributionRun).where(AttributionRun.connection_id==conn.id,AttributionRun.request_key==key))
    if old:
        if (old.account_id,old.period_start,old.period_end,old.discrepancy_threshold_pct)!=(body.account_id,body.period_start,body.period_end,body.discrepancy_threshold_pct):raise HTTPException(409,'request_key đã dùng cho lần phân tích khác')
        return await detail(db,conn,body.account_id,old)
    try:run=await analyze(db,conn,who.id,body.account_id,body.period_start,body.period_end,body.discrepancy_threshold_pct,key)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    await db.commit();return await detail(db,conn,body.account_id,run)

@router.get('/dashboard',response_model=AttributionDashboardOut)
async def dashboard(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id);return await detail(db,conn,account_id) if conn else AttributionDashboardOut(run=None,sources=[],metrics=[],alerts=[])

@router.post('/alerts/{alert_id}/acknowledge',response_model=TrackingAlertOut)
async def acknowledge(alert_id: UUID,workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id,True);row=await db.get(TrackingAlert,str(alert_id),with_for_update=True)
    if not conn or not row or row.connection_id!=conn.id or row.connection_version!=conn.version:raise HTTPException(404,'Không tìm thấy cảnh báo tracking')
    row.acknowledged=True;row.last_seen_at=now();await db.commit();return row
