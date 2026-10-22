from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import Principal, principal
from .db import database, Session
from .config import settings
from .models import AdMetric, AdEntity, AdSyncSchedule, MetaConnection, MetaSyncJob, now
from .integrations.meta.api import connection, require_config
from .integrations.meta.sync import permitted
from .modules.connections import ads_authority

router=APIRouter(prefix='/v1/warehouse',tags=['warehouse'])


class MetricOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    platform: str
    account_id: str
    level: str
    entity_id: str
    campaign_id: str | None
    adset_id: str | None
    day: date
    hour: int
    granularity: str
    currency: str
    timezone: str
    attribution: str
    spend: Decimal | None
    impressions: int | None
    reach: int | None
    clicks: int | None
    link_clicks: int | None
    frequency: Decimal | None
    ctr: Decimal | None
    cpc: Decimal | None
    cpm: Decimal | None
    leads: Decimal | None
    add_to_cart: Decimal | None
    checkout: Decimal | None
    purchase: Decimal | None
    revenue: Decimal | None
    conversions: Decimal | None
    conversion_value: Decimal | None
    cpl: Decimal | None
    cpa: Decimal | None
    roas: Decimal | None
    source_job_id: str | None
    google_source_job_id: str | None
    updated_at: datetime


class MetricsPage(BaseModel):
    rows: list[MetricOut]
    has_more: bool


class EntityOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    account_id: str
    kind: str
    remote_id: str
    parent_id: str | None
    creative_id: str | None
    name: str | None
    status: str | None
    objective: str | None
    currency: str
    timezone: str
    source_job_id: str | None
    google_source_job_id: str | None
    updated_at: datetime


class ScheduleInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    granularity: Literal['daily','hourly']='daily'
    enabled: bool=False
    interval_minutes: int=Field(default=1440,ge=15,le=10080)
    lookback_days: int=Field(default=3,ge=1,le=31)


class ScheduleOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    account_id: str
    granularity: str
    enabled: bool
    interval_minutes: int
    lookback_days: int
    next_at: datetime


@router.get('/metrics',response_model=MetricsPage)
async def metrics(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),
    since: date=Query(),until: date=Query(),level: Literal['campaign','adset','ad']='campaign',
    granularity: Literal['daily','hourly']='daily',offset: int=Query(0,ge=0,le=100000),
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    if not 0<=(until-since).days<366:raise HTTPException(422,'Khoảng truy vấn tối đa 366 ngày')
    conn=await connection(db,who,workspace_id)
    await ads_authority.legacy(db,conn,'meta_ads')
    if not conn or conn.status=='disconnected':return MetricsPage(rows=[],has_more=False)
    rows=list(await db.scalars(select(AdMetric).where(AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,
        AdMetric.account_id==account_id,AdMetric.level==level,AdMetric.granularity==granularity,AdMetric.day>=since,AdMetric.day<=until)
        .order_by(AdMetric.day.desc(),AdMetric.hour,AdMetric.entity_id).offset(offset).limit(51)))
    return MetricsPage(rows=[MetricOut.model_validate(row) for row in rows[:50]],has_more=len(rows)>50)


@router.get('/entities',response_model=list[EntityOut])
async def entities(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),
    kind: Literal['account','campaign','adset','ad','creative']='campaign',offset: int=Query(0,ge=0,le=100000),
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    await ads_authority.legacy(db,conn,'meta_ads')
    if not conn or conn.status=='disconnected':return []
    return list(await db.scalars(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==account_id,AdEntity.kind==kind).order_by(AdEntity.remote_id).offset(offset).limit(50)))


@router.get('/schedules',response_model=list[ScheduleOut])
async def schedules(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    return list(await db.scalars(select(AdSyncSchedule).where(AdSyncSchedule.connection_id==conn.id,AdSyncSchedule.connection_version==conn.version).order_by(AdSyncSchedule.account_id).limit(100)))


@router.put('/schedules',response_model=ScheduleOut)
async def schedule(body: ScheduleInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta trước')
    if body.enabled:
        if not await permitted(db,conn,conn.version):raise HTTPException(409,'Kết nối Meta hết hạn hoặc bị thu hồi')
        account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
            AdEntity.account_id==body.account_id,AdEntity.kind=='account'))
        if not account:raise HTTPException(409,'Đồng bộ warehouse thủ công thành công trước khi bật lịch')
    row=await db.scalar(select(AdSyncSchedule).where(AdSyncSchedule.connection_id==conn.id,
        AdSyncSchedule.account_id==body.account_id,AdSyncSchedule.granularity==body.granularity))
    if not row:
        row=AdSyncSchedule(connection_id=conn.id,account_id=body.account_id,granularity=body.granularity);db.add(row)
    row.connection_version=conn.version;row.enabled=body.enabled;row.interval_minutes=body.interval_minutes
    row.lookback_days=body.lookback_days;row.next_at=now()+timedelta(minutes=body.interval_minutes)
    await db.commit();return row


# Compatibility alias for existing scripts/tests; worker imports the service directly.
from .modules.business.warehouse_scheduler import schedule_warehouse
