from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, principal, rate_limit
from .db import database
from .integrations.meta.api import connection
from .intelligence import analyze, ensure_rules
from .models import (AdAnomaly, AdEntity, AdIntelligenceRun, AdRecommendation,
                     AdRule, AdTarget, now)

router=APIRouter(prefix='/v1/ads',tags=['performance-intelligence'])


class TargetInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    target_cpa: Decimal|None=Field(None,gt=0,max_digits=24,decimal_places=6)
    target_roas: Decimal|None=Field(None,gt=0,max_digits=24,decimal_places=6)
    minimum_spend: Decimal=Field(0,ge=0,max_digits=24,decimal_places=6)
    minimum_impressions: int=Field(1000,ge=0,le=10**12)
    minimum_clicks: int=Field(20,ge=0,le=10**12)
    minimum_conversions: int=Field(3,ge=0,le=10**9)
    minimum_run_days: int=Field(3,ge=1,le=30)
    freshness_minutes: int=Field(180,ge=15,le=10080)

    @model_validator(mode='after')
    def objective(self):
        if self.target_cpa is None and self.target_roas is None:raise ValueError('Cần ít nhất target CPA hoặc target ROAS')
        return self


class TargetOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    account_id: str
    target_cpa: Decimal|None
    target_roas: Decimal|None
    minimum_spend: Decimal
    minimum_impressions: int
    minimum_clicks: int
    minimum_conversions: int
    minimum_run_days: int
    freshness_minutes: int
    updated_at: datetime


class RuleOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    account_id: str
    platform: str
    code: str
    name: str
    conditions_json: dict
    action_json: dict
    mode: str
    enabled: bool
    updated_at: datetime


class RuleUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool


class AnalyzeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    as_of: date
    granularity: Literal['daily','hourly']='daily'
    hour: int|None=Field(None,ge=0,le=23)
    request_key: UUID

    @model_validator(mode='after')
    def slot(self):
        if (self.granularity=='daily') != (self.hour is None):raise ValueError('Daily không dùng hour; hourly cần hour 0–23')
        return self


class IntelligenceRunOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    account_id: str
    granularity: str
    period_start: date
    period_end: date
    hour: int|None
    analyst_version: str
    summary: dict
    source_updated_at: datetime
    created_at: datetime


class AnomalyOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    run_id: str
    account_id: str
    resource_id: str
    kind: str
    severity: str
    current_value: Decimal|None
    baseline_value: Decimal|None
    deviation_pct: Decimal|None
    evidence: dict
    first_seen: datetime
    last_seen: datetime
    acknowledged: bool
    resolved: bool


class RecommendationOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str
    run_id: str
    account_id: str
    resource_id: str
    type: str
    confidence: Decimal
    impact: dict
    reason_codes: list
    explanation: str
    proposed_action: dict
    source: dict
    data_freshness_seconds: int
    status: str
    first_seen: datetime
    last_seen: datetime


class IntelligenceOut(BaseModel):
    run: IntelligenceRunOut
    anomalies: list[AnomalyOut]
    recommendations: list[RecommendationOut]


async def run_detail(db,run):
    anomaly_ids=run.summary.get('anomaly_ids',[]);recommendation_ids=run.summary.get('recommendation_ids',[])
    anomalies=list(await db.scalars(select(AdAnomaly).where(AdAnomaly.id.in_(anomaly_ids)).order_by(AdAnomaly.severity,AdAnomaly.resource_id))) if anomaly_ids else []
    recommendations=list(await db.scalars(select(AdRecommendation).where(AdRecommendation.id.in_(recommendation_ids)).order_by(AdRecommendation.confidence.desc()))) if recommendation_ids else []
    return IntelligenceOut(run=IntelligenceRunOut.model_validate(run),anomalies=anomalies,recommendations=recommendations)


@router.get('/targets',response_model=list[TargetOut])
async def targets(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    return list(await db.scalars(select(AdTarget).where(AdTarget.connection_id==conn.id).order_by(AdTarget.account_id)))


@router.put('/targets',response_model=TargetOut)
async def set_target(body: TargetInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta và đồng bộ warehouse trước')
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==body.account_id,AdEntity.kind=='account'))
    if not account:raise HTTPException(409,'Không có account trong warehouse hiện tại')
    row=await db.scalar(select(AdTarget).where(AdTarget.connection_id==conn.id,AdTarget.account_id==body.account_id))
    if not row:
        row=AdTarget(connection_id=conn.id,workspace_id=conn.workspace_id,account_id=body.account_id);db.add(row)
    row.connection_version=conn.version
    for key,value in body.model_dump(exclude={'workspace_id','account_id'}).items():setattr(row,key,value)
    row.updated_at=now();await db.flush();await ensure_rules(db,row);await db.commit();return row


@router.get('/rules',response_model=list[RuleOut])
async def rules(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    return list(await db.scalars(select(AdRule).where(AdRule.connection_id==conn.id,AdRule.connection_version==conn.version,
        AdRule.account_id==account_id).order_by(AdRule.code)))


@router.put('/rules/{rule_id}',response_model=RuleOut)
async def set_rule(rule_id: UUID,body: RuleUpdate,workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id,True)
    row=await db.get(AdRule,str(rule_id),with_for_update=True)
    if not conn or not row or row.connection_id!=conn.id or row.connection_version!=conn.version:raise HTTPException(404,'Không tìm thấy rule')
    row.enabled=body.enabled;row.updated_at=now();await db.commit();return row


@router.post('/intelligence/analyze',response_model=IntelligenceOut,status_code=201)
async def analyze_now(body: AnalyzeInput,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'ads-intelligence',who.id,10,60)
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta và đồng bộ warehouse trước')
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==body.account_id,AdEntity.kind=='account'))
    if not account:raise HTTPException(409,'Không có account trong warehouse hiện tại')
    local=now().astimezone(ZoneInfo(account.timezone))
    if body.as_of>local.date() or body.granularity=='daily' and body.as_of>=local.date() or body.granularity=='hourly' and body.as_of==local.date() and body.hour>=local.hour:
        raise HTTPException(422,'Chỉ phân tích khoảng thời gian đã hoàn tất')
    key=str(body.request_key)
    old=await db.scalar(select(AdIntelligenceRun).where(AdIntelligenceRun.connection_id==conn.id,AdIntelligenceRun.request_key==key))
    if old:
        if (old.account_id,old.period_end,old.granularity,old.hour)!=(body.account_id,body.as_of,body.granularity,body.hour):raise HTTPException(409,'request_key đã dùng cho lần phân tích khác')
        return await run_detail(db,old)
    try:run=await analyze(db,conn,who.id,body.account_id,body.as_of,body.granularity,body.hour,key)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    await db.commit();return await run_detail(db,run)


@router.get('/anomalies',response_model=list[AnomalyOut])
async def anomalies(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),include_resolved: bool=False,
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    conditions=[AdAnomaly.connection_id==conn.id,AdAnomaly.connection_version==conn.version,AdAnomaly.account_id==account_id]
    if not include_resolved:conditions.append(AdAnomaly.resolved.is_(False))
    return list(await db.scalars(select(AdAnomaly).where(*conditions).order_by(AdAnomaly.last_seen.desc()).limit(100)))


@router.post('/anomalies/{anomaly_id}/acknowledge',response_model=AnomalyOut)
async def acknowledge(anomaly_id: UUID,workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id,True);row=await db.get(AdAnomaly,str(anomaly_id),with_for_update=True)
    if not conn or not row or row.connection_id!=conn.id or row.connection_version!=conn.version:raise HTTPException(404,'Không tìm thấy anomaly')
    row.acknowledged=True;await db.commit();return row


@router.get('/recommendations',response_model=list[RecommendationOut])
async def recommendations(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),include_resolved: bool=False,
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    if not conn:return []
    conditions=[AdRecommendation.connection_id==conn.id,AdRecommendation.connection_version==conn.version,AdRecommendation.account_id==account_id]
    if not include_resolved:conditions.append(AdRecommendation.status=='active')
    return list(await db.scalars(select(AdRecommendation).where(*conditions).order_by(AdRecommendation.confidence.desc(),AdRecommendation.last_seen.desc()).limit(100)))


@router.post('/recommendations/{recommendation_id}/dismiss',response_model=RecommendationOut)
async def dismiss(recommendation_id: UUID,workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id,True);row=await db.get(AdRecommendation,str(recommendation_id),with_for_update=True)
    if not conn or not row or row.connection_id!=conn.id or row.connection_version!=conn.version:raise HTTPException(404,'Không tìm thấy recommendation')
    row.status='dismissed';row.last_seen=now();await db.commit();return row
