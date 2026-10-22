from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, principal, rate_limit
from .creative_intelligence import analyze
from .db import database
from .integrations.meta.api import connection
from .models import (AdEntity, Brand, CreativeAnalysisRun, CreativeAsset, CreativeFeature,
    CreativeLearning, CreativeMetadata, CreativePerformance, now)

router=APIRouter(prefix='/v1/creatives',tags=['creative-intelligence'])

class AnalyzeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id: UUID
    account_id: str=Field(pattern=r'^act_[0-9]{1,32}$')
    as_of: date
    request_key: UUID
    current_days: int=Field(3,ge=2,le=14)
    baseline_days: int=Field(3,ge=2,le=28)
    minimum_impressions: int=Field(1000,ge=100,le=10**12)
    minimum_age_days: int=Field(7,ge=1,le=365)
    saturation_impressions: int=Field(10000,ge=100,le=10**12)
    frequency_rise_pct: Decimal=Field(20,ge=1,le=500)
    ctr_decline_pct: Decimal=Field(20,ge=1,le=100)
    cpa_increase_pct: Decimal=Field(20,ge=1,le=500)
    cpm_stable_pct: Decimal=Field(15,ge=1,le=100)

class MetadataInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version: int=Field(0,ge=0)
    brand_id: UUID|None=None
    product: str|None=Field(None,max_length=160)
    market: str|None=Field(None,max_length=80)
    language: str|None=Field(None,max_length=32)
    format: str|None=Field(None,max_length=64)
    duration_seconds: int|None=Field(None,ge=1,le=86400)
    hook: str|None=Field(None,max_length=1000)
    angle: str|None=Field(None,max_length=1000)
    offer: str|None=Field(None,max_length=1000)
    cta: str|None=Field(None,max_length=160)
    creator: str|None=Field(None,max_length=160)
    landing_page: HttpUrl|None=None

class AssetOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;account_id: str;creative_id: str;name: str|None;first_seen_at: datetime;last_seen_at: datetime

class MetadataOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;asset_id: str;brand_id: str|None;product: str|None;market: str|None;language: str|None;format: str|None
    duration_seconds: int|None;hook: str|None;angle: str|None;offer: str|None;cta: str|None;creator: str|None;landing_page: str|None
    source: str;version: int;updated_at: datetime

class PerformanceOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    sample_window: str;period_start: date;period_end: date;currency: str;timezone: str;spend: Decimal;impressions: int;clicks: int
    purchases: Decimal;revenue: Decimal;ctr: Decimal|None;cpm: Decimal|None;cpa: Decimal|None;roas: Decimal|None;frequency: Decimal|None
    ad_count: int;coverage_days: int

class FeatureOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    fatigue_status: Literal['healthy','watch','fatigued','insufficient'];fatigue_score: Decimal;confidence: Decimal;age_days: int;signals: dict;strategy_brief: dict

class CreativeAnalysisRunOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;account_id: str;as_of: date;current_days: int;baseline_days: int;configuration: dict;analyst_version: str;summary: dict;source_updated_at: datetime;created_at: datetime

class LearningOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: str;dimension: str;value: str;statement: str;confidence: Decimal;evidence: dict;status: str;first_seen_at: datetime;last_seen_at: datetime

class CreativeView(BaseModel):
    asset: AssetOut;metadata: MetadataOut|None;current: PerformanceOut|None;baseline: PerformanceOut|None;feature: FeatureOut|None

class CreativeDashboardOut(BaseModel):
    run: CreativeAnalysisRunOut|None;creatives: list[CreativeView];learnings: list[LearningOut];read_only: bool=True

async def dashboard_detail(db,conn,account_id,run=None):
    if run is None:
        run=await db.scalar(select(CreativeAnalysisRun).where(CreativeAnalysisRun.connection_id==conn.id,
            CreativeAnalysisRun.connection_version==conn.version,CreativeAnalysisRun.account_id==account_id).order_by(CreativeAnalysisRun.created_at.desc()).limit(1))
    assets=list(await db.scalars(select(CreativeAsset).where(CreativeAsset.connection_id==conn.id,
        CreativeAsset.connection_version==conn.version,CreativeAsset.account_id==account_id).order_by(CreativeAsset.name,CreativeAsset.creative_id)))
    metadata={x.asset_id:x for x in await db.scalars(select(CreativeMetadata).where(CreativeMetadata.asset_id.in_([x.id for x in assets])))} if assets else {}
    performance={};features={}
    if run:
        performance={(x.asset_id,x.sample_window):x for x in await db.scalars(select(CreativePerformance).where(CreativePerformance.run_id==run.id))}
        features={x.asset_id:x for x in await db.scalars(select(CreativeFeature).where(CreativeFeature.run_id==run.id))}
    learnings=list(await db.scalars(select(CreativeLearning).where(CreativeLearning.connection_id==conn.id,
        CreativeLearning.connection_version==conn.version,CreativeLearning.account_id==account_id,CreativeLearning.status=='active').order_by(CreativeLearning.confidence.desc())))
    return CreativeDashboardOut(run=run,creatives=[CreativeView(asset=x,metadata=metadata.get(x.id),current=performance.get((x.id,'current')),
        baseline=performance.get((x.id,'baseline')),feature=features.get(x.id)) for x in assets],learnings=learnings)

@router.post('/analyze',response_model=CreativeDashboardOut,status_code=201)
async def analyze_now(body: AnalyzeInput,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'creative-intelligence',who.id,10,60)
    conn=await connection(db,who,body.workspace_id,True)
    if not conn:raise HTTPException(409,'Kết nối Meta và đồng bộ warehouse trước')
    account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==body.account_id,AdEntity.kind=='account'))
    if not account:raise HTTPException(409,'Không có account trong warehouse hiện tại')
    if body.as_of>=now().astimezone(ZoneInfo(account.timezone)).date():raise HTTPException(422,'Chỉ phân tích ngày đã hoàn tất')
    config=body.model_dump(exclude={'workspace_id','account_id','as_of','request_key'},mode='json')
    key=str(body.request_key);old=await db.scalar(select(CreativeAnalysisRun).where(CreativeAnalysisRun.connection_id==conn.id,CreativeAnalysisRun.request_key==key))
    if old:
        if (old.account_id,old.as_of,old.configuration)!=(body.account_id,body.as_of,config):raise HTTPException(409,'request_key đã dùng cho lần phân tích khác')
        return await dashboard_detail(db,conn,body.account_id,old)
    try:run=await analyze(db,conn,who.id,body.account_id,body.as_of,key,config)
    except ValueError as exc:raise HTTPException(409,str(exc)) from None
    await db.commit();return await dashboard_detail(db,conn,body.account_id,run)

@router.get('/dashboard',response_model=CreativeDashboardOut)
async def dashboard(workspace_id: UUID,account_id: str=Query(pattern=r'^act_[0-9]{1,32}$'),who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id)
    return await dashboard_detail(db,conn,account_id) if conn else CreativeDashboardOut(run=None,creatives=[],learnings=[])

@router.put('/assets/{asset_id}/metadata',response_model=MetadataOut)
async def update_metadata(asset_id: UUID,workspace_id: UUID,body: MetadataInput,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    conn=await connection(db,who,workspace_id,True);asset=await db.get(CreativeAsset,str(asset_id))
    if not conn or not asset or asset.connection_id!=conn.id or asset.connection_version!=conn.version:raise HTTPException(404,'Không tìm thấy creative')
    if body.brand_id and not await db.scalar(select(Brand.id).where(Brand.id==str(body.brand_id),Brand.workspace_id==conn.workspace_id)):raise HTTPException(404,'Không tìm thấy brand')
    row=await db.scalar(select(CreativeMetadata).where(CreativeMetadata.asset_id==asset.id).with_for_update())
    if row and row.version!=body.version:raise HTTPException(409,'Metadata đã thay đổi; hãy tải lại trước khi lưu')
    if not row:
        if body.version!=0:raise HTTPException(409,'Metadata đã thay đổi; hãy tải lại trước khi lưu')
        row=CreativeMetadata(asset_id=asset.id,workspace_id=conn.workspace_id,updated_by=who.id);db.add(row)
    else:row.version+=1
    values=body.model_dump(exclude={'version'},mode='json')
    for key,value in values.items():setattr(row,key,str(value) if key in ('brand_id','landing_page') and value is not None else value)
    row.updated_by=who.id;row.updated_at=now();await db.commit();return row
