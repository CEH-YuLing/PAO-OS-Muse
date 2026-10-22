from datetime import date,datetime,timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from .auth import Principal,principal,rate_limit
from .config import settings
from .db import database,Session
from .models import AdEntity,AdReport,AdReportDelivery,AdReportSchedule,MetaConnection,TelegramPeer,now
from .integrations.meta.api import connection
from .integrations.meta.sync import permitted as meta_permitted
from .reporting import build_report,queue_report,delivery_status,next_delivery
from .telegram import queue,permitted as telegram_permitted
from .reconciliation import ExportTotals, ReconciliationOut, compare_report

router=APIRouter(prefix='/v1/reports',tags=['ads-reporting'])


class ReportCreate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    kind: Literal['daily','weekly']
    period_end: date
    request_key: UUID


class ReportOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    account_id: str
    kind: str
    period_start: date
    period_end: date
    currency: str
    timezone: str
    attribution: str
    spend: Decimal | None
    revenue: Decimal | None
    purchases: Decimal | None
    leads: Decimal | None
    impressions: int | None
    clicks: int | None
    roas: Decimal | None
    cpa: Decimal | None
    comparison: dict
    campaigns: list[dict]
    coverage_days: int
    expected_days: int
    data_through: date | None
    source_updated_at: datetime
    created_at: datetime


class DeliveryOut(BaseModel):
    id: str
    report_id: str
    status: str
    created_at: datetime


class ReportDetail(BaseModel):
    report: ReportOut
    deliveries: list[DeliveryOut]


class DashboardOut(BaseModel):
    latest_daily: ReportOut | None
    latest_weekly: ReportOut | None
    daily_trend: list[ReportOut]


class ReportScheduleInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    kind: Literal['daily','weekly']
    enabled: bool=False
    delivery_hour: int=Field(default=8,ge=0,le=23)
    weekday: int | None=Field(default=None,ge=0,le=6)
    telegram: bool=True
    telegram_binding_id: UUID | None=None


class ReportScheduleOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    account_id: str
    kind: str
    enabled: bool
    delivery_hour: int
    weekday: int | None
    telegram: bool
    telegram_binding_id: str | None=None
    next_at: datetime


async def owned_report(db,who,report_id):
    report=await db.get(AdReport,str(report_id))
    if not report or report.user_id!=who.id:raise HTTPException(404,'Không tìm thấy báo cáo')
    conn=await connection(db,who,report.workspace_id)
    if not conn or report.connection_id!=conn.id or report.connection_version!=conn.version:raise HTTPException(404,'Không tìm thấy báo cáo')
    return report,conn


@router.post('/{report_id}/reconciliation-preview', response_model=ReconciliationOut)
async def reconciliation_preview(report_id: UUID, body: ExportTotals,
                                 who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    report, _ = await owned_report(db, who, report_id)
    # Pure comparison of one authorized saved record, no write or provider call.
    return compare_report(report, body)


async def detail(db,report):
    deliveries=list(await db.scalars(select(AdReportDelivery).where(AdReportDelivery.report_id==report.id).order_by(AdReportDelivery.created_at)))
    return ReportDetail(report=ReportOut.model_validate(report),deliveries=[DeliveryOut(id=row.id,report_id=row.report_id,
        status=await delivery_status(db,row),created_at=row.created_at) for row in deliveries])


@router.post('',response_model=ReportDetail,status_code=201)
async def create(body: ReportCreate,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'ads-report-create',who.id,20,60)
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta và đồng bộ warehouse trước')
    try:today=now().astimezone(ZoneInfo((await db.scalar(select(AdEntity.timezone).where(AdEntity.connection_id==conn.id,
        AdEntity.connection_version==conn.version,AdEntity.account_id==body.account_id,AdEntity.kind=='account'))))).date()
    except Exception:raise HTTPException(409,'Không có account trong warehouse hiện tại') from None
    if body.period_end>=today:raise HTTPException(422,'Chỉ tạo báo cáo cho ngày đã hoàn tất theo múi giờ tài khoản')
    key=str(body.request_key)
    old=await db.scalar(select(AdReport).where(AdReport.connection_id==conn.id,AdReport.request_key==key))
    if old:
        if (old.account_id,old.kind,old.period_end)!=(body.account_id,body.kind,body.period_end):raise HTTPException(409,'request_key đã dùng cho báo cáo khác')
        return await detail(db,old)
    try:report=await build_report(db,conn,who.id,body.account_id,body.kind,body.period_end,key)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    await db.commit();return await detail(db,report)


@router.get('',response_model=list[ReportOut])
async def reports(workspace_id: UUID,account_id: str|None=Query(None,pattern=r'^act_[0-9]{1,32}$'),kind: Literal['daily','weekly']|None=None,
    offset: int=Query(0,ge=0,le=100000),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    conditions=[AdReport.connection_id==conn.id,AdReport.connection_version==conn.version]
    if account_id:conditions.append(AdReport.account_id==account_id)
    if kind:conditions.append(AdReport.kind==kind)
    return list(await db.scalars(select(AdReport).where(*conditions).order_by(AdReport.period_end.desc(),AdReport.created_at.desc()).offset(offset).limit(50)))


@router.get('/dashboard',response_model=DashboardOut)
async def dashboard(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return DashboardOut(latest_daily=None,latest_weekly=None,daily_trend=[])
    base=[AdReport.connection_id==conn.id,AdReport.connection_version==conn.version,AdReport.account_id==account_id]
    daily=list(await db.scalars(select(AdReport).where(*base,AdReport.kind=='daily').order_by(AdReport.period_end.desc(),AdReport.created_at.desc()).limit(30)))
    weekly=await db.scalar(select(AdReport).where(*base,AdReport.kind=='weekly').order_by(AdReport.period_end.desc(),AdReport.created_at.desc()).limit(1))
    # Keep the latest generation for each daily period in the chart.
    trend=[];seen=set()
    for row in daily:
        if row.period_end not in seen:seen.add(row.period_end);trend.append(row)
    return DashboardOut(latest_daily=ReportOut.model_validate(trend[0]) if trend else None,
        latest_weekly=ReportOut.model_validate(weekly) if weekly else None,daily_trend=[ReportOut.model_validate(x) for x in reversed(trend)])


@router.get('/{report_id}',response_model=ReportDetail)
async def get_report(report_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    report,_=await owned_report(db,who,report_id);return await detail(db,report)


@router.post('/{report_id}/telegram',response_model=DeliveryOut,status_code=202)
async def send_telegram(report_id: UUID,request: Request,binding_id:UUID|None=None,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'ads-report-send',who.id,10,60)
    report,_=await owned_report(db,who,report_id)
    if binding_id is not None:
        from .modules.channels import telegram_reports as scoped_reports
        from .models import AdReportDelivery
        binding=await scoped_reports.destination(db,report.workspace_id,who.id,str(binding_id))
        outbox=await scoped_reports.queue_report(db,report,binding)
        delivery=await db.scalar(select(AdReportDelivery).where(AdReportDelivery.report_id==report.id,AdReportDelivery.peer_id==binding.peer_id))
        if not delivery:
            delivery=AdReportDelivery(report_id=report.id,peer_id=binding.peer_id,dedup_prefix='ads-report:'+report.id+':'+binding.peer_id)
            db.add(delivery)
        await db.commit()
        return DeliveryOut(id=delivery.id,report_id=report.id,status=await delivery_status(db,delivery),created_at=delivery.created_at)
    if not settings().telegram_enabled or not settings().telegram_bot_token:raise HTTPException(409,'Telegram chưa được cấu hình')
    peer=await db.scalar(select(TelegramPeer).where(TelegramPeer.connection_id.is_(None),TelegramPeer.user_id==who.id,TelegramPeer.workspace_id==report.workspace_id,TelegramPeer.enabled.is_(True)).limit(1))
    if not await telegram_permitted(db,peer):raise HTTPException(409,'Chưa có Telegram peer được phép')
    delivery=await queue_report(db,report,peer,queue);await db.commit()
    return DeliveryOut(id=delivery.id,report_id=report.id,status=await delivery_status(db,delivery),created_at=delivery.created_at)


@router.get('/configuration/schedules',response_model=list[ReportScheduleOut])
async def schedules(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    return list(await db.scalars(select(AdReportSchedule).where(AdReportSchedule.connection_id==conn.id,
        AdReportSchedule.connection_version==conn.version).order_by(AdReportSchedule.account_id,AdReportSchedule.kind).limit(100)))


@router.put('/configuration/schedules',response_model=ReportScheduleOut)
async def set_schedule(body: ReportScheduleInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta và đồng bộ warehouse trước')
    if body.kind=='daily' and body.weekday is not None or body.kind=='weekly' and body.weekday is None:
        raise HTTPException(422,'Daily không dùng weekday; weekly cần weekday 0–6')
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==body.account_id,AdEntity.kind=='account'))
    if not account:raise HTTPException(409,'Không có account trong warehouse hiện tại')
    scoped_binding=None
    if body.enabled and body.telegram and body.telegram_binding_id:
        from .modules.channels.telegram_reports import destination
        scoped_binding=await destination(db,conn.workspace_id,who.id,str(body.telegram_binding_id))
    elif body.enabled and body.telegram:
        if not settings().telegram_enabled or not settings().telegram_bot_token:raise HTTPException(409,'Telegram chưa được cấu hình')
        peer=await db.scalar(select(TelegramPeer).where(TelegramPeer.connection_id.is_(None),TelegramPeer.user_id==who.id,TelegramPeer.workspace_id==conn.workspace_id,TelegramPeer.enabled.is_(True)).limit(1))
        if not await telegram_permitted(db,peer):raise HTTPException(409,'Chưa có Telegram peer được phép')
    row=await db.scalar(select(AdReportSchedule).where(AdReportSchedule.connection_id==conn.id,
        AdReportSchedule.account_id==body.account_id,AdReportSchedule.kind==body.kind))
    if not row:row=AdReportSchedule(connection_id=conn.id,account_id=body.account_id,kind=body.kind);db.add(row)
    row.connection_version=conn.version;row.enabled=body.enabled;row.delivery_hour=body.delivery_hour
    row.weekday=body.weekday;row.telegram=body.telegram
    row.telegram_binding_id=scoped_binding.id if scoped_binding else None
    row.telegram_binding_version=scoped_binding.version if scoped_binding else None
    row.next_at=next_delivery(account.timezone,body.kind,body.delivery_hour,body.weekday)
    await db.commit();return row


# Compatibility alias; workers import the service directly.
from .modules.business.report_scheduler import schedule_reports
