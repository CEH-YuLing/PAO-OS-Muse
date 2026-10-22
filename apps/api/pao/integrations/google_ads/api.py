import hashlib,logging,secrets
from datetime import timedelta,date,datetime
from decimal import Decimal
from urllib.parse import urlencode,urlsplit
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select,update
from sqlalchemy.ext.asyncio import AsyncSession
from ...access import membership
from ...auth import Principal,principal,rate_limit
from ...config import settings
from ...db import database
from ...models import AdEntity,AdMetric,GoogleAdsConnection,GoogleAdsOAuthState,GoogleAdsSyncJob,Member,User,Workspace,now
from .client import GoogleAdsClient,GoogleAdsError,SCOPE,configured,encrypt
from .schemas import ConnectionOut,OAuthStart,SyncCreate,SyncOut,AccountOut
from ...modules.connections import ads_authority
from .. import ads_apps,ads_oauth

router=APIRouter(prefix='/v1/integrations/google-ads',tags=['google-ads']);COOKIE='pao_google_ads_state';CALLBACK='/v1/integrations/google-ads/callback'

@router.get('/tenant-app',response_model=ads_apps.AppStatus)
async def tenant_app(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await ads_apps.status(db,who,str(workspace_id),'google')

@router.put('/tenant-app',response_model=ads_apps.AppStatus)
async def save_tenant_app(body:ads_apps.AppSave,workspace_id:UUID,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'google-tenant-app',who.id,10,60)
    return await ads_apps.save(db,who,str(workspace_id),'google',body)
class Hide(logging.Filter):
    def filter(self,record):
        if isinstance(record.args,tuple) and len(record.args)==5 and str(record.args[2]).split('?')[0]==CALLBACK:
            x=list(record.args);x[2]=CALLBACK;record.args=tuple(x)
        return True
logging.getLogger('uvicorn.access').addFilter(Hide())
def digest(x):return hashlib.sha256(x.encode()).hexdigest()
def require_config():
    try:configured()
    except GoogleAdsError as exc:raise HTTPException(503,str(exc)) from None
async def connection(db,who,wid,write=False,create=False,management=False):
    member=await membership(db,str(wid),who)
    if write and member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được quản lý Google Ads')
    if write:await db.execute(select(Workspace.id).where(Workspace.id==str(wid)).with_for_update())
    query=select(GoogleAdsConnection).where(GoogleAdsConnection.workspace_id==str(wid),GoogleAdsConnection.user_id==who.id)
    row=await db.scalar(query.with_for_update() if write else query)
    if row is None and create:row=GoogleAdsConnection(workspace_id=str(wid),user_id=who.id);db.add(row);await db.flush()
    if not write and not management:await ads_authority.legacy(db,row,'google_ads')
    return row
@router.get('/connection',response_model=ConnectionOut)
async def status(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id,management=True)
    try:ads_apps.validate(await ads_apps.resolve(db,str(workspace_id),'google'),'google');ready=True
    except GoogleAdsError:ready=False
    state=row.status if row else 'disconnected'
    if row and row.status=='connected' and not await ads_apps.matches(db,row,'google'):state='expired'
    return ConnectionOut(configured=ready,status=state,scopes=row.scopes if row else [])
@router.post('/oauth/start',response_model=OAuthStart)
async def start(workspace_id:UUID,request:Request,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await ads_oauth.start(db,who,workspace_id,request,response,'google',connection,COOKIE,CALLBACK)
@router.get('/callback',response_class=HTMLResponse)
async def callback(request:Request,state:str=Query('',max_length=256),code:str=Query('',max_length=8192),db:AsyncSession=Depends(database)):
    return await ads_oauth.callback(db,request,state,code,'google',COOKIE,CALLBACK)
@router.delete('/connection',status_code=204)
async def disconnect(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id,True)
    if row:row.version+=1;row.status='disconnected';row.refresh_token_ciphertext=None;row.scopes=[];await db.execute(update(GoogleAdsOAuthState).where(GoogleAdsOAuthState.connection_id==row.id).values(used=True));await db.execute(update(GoogleAdsSyncJob).where(GoogleAdsSyncJob.connection_id==row.id,GoogleAdsSyncJob.status.in_(['queued','running'])).values(status='cancelled',updated_at=now()));await db.commit()
@router.post('/sync',response_model=SyncOut,status_code=202)
async def sync(body:SyncCreate,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'google-ads-sync',who.id,10,60)
    from ...modules.connections import read_resources
    try:await membership(db,str(body.workspace_id),who,True)
    except HTTPException as exc:
        if body.grant_id and exc.status_code==404:raise HTTPException(403,ads_authority.DENIED) from None
        raise
    await read_resources.lock(db,str(body.workspace_id))
    authority=None
    if body.grant_id:
        row,authority=await ads_authority.selected(db,str(body.workspace_id),who.id,
            str(body.brand_id) if body.brand_id else None,body.account_id,str(body.grant_id),'google_ads',write=True)
    else:
        row=await connection(db,who,body.workspace_id,True)
        await ads_authority.legacy(db,row,'google_ads')
    if not row or row.status!='connected' or not row.refresh_token_ciphertext:raise HTTPException(409,'Kết nối lại Google Ads trước khi đồng bộ')
    try:app_context=await ads_apps.bound(db,row,'google')
    except GoogleAdsError as exc:raise HTTPException(409,str(exc)) from None
    old=await db.scalar(select(GoogleAdsSyncJob).where(GoogleAdsSyncJob.connection_id==row.id,GoogleAdsSyncJob.request_key==str(body.request_key)));dates=(body.since.isoformat() if body.since else None,body.until.isoformat() if body.until else None)
    if old:
        if old.authority_pin!=authority:raise HTTPException(409,'ads_sync_authority_request_key_conflict')
        if (old.kind,old.account_id,old.since,old.until,old.connection_version,old.granularity)!=(body.kind,body.account_id,*dates,row.version,body.granularity):raise HTTPException(409,'request_key đã dùng cho yêu cầu khác')
        return old
    if await db.scalar(select(GoogleAdsSyncJob.id).where(GoogleAdsSyncJob.connection_id==row.id,GoogleAdsSyncJob.status.in_(['queued','running']))):raise HTTPException(409,'Đang có một lượt đồng bộ Google Ads')
    if body.kind=='historical' and not await db.scalar(select(AdEntity.id).where(AdEntity.google_connection_id==row.id,AdEntity.connection_version==row.version,AdEntity.platform=='google',AdEntity.kind=='account',AdEntity.account_id==body.account_id)):raise HTTPException(409,'Đồng bộ và chọn Google Ads account trước')
    await read_resources.admit(db,row.workspace_id)
    job=GoogleAdsSyncJob(connection_id=row.id,connection_version=row.version,api_version=app_context.config.google_ads_api_version,authority_pin=authority,request_key=str(body.request_key),kind=body.kind,account_id=body.account_id,since=dates[0],until=dates[1],granularity=body.granularity);db.add(job);await db.commit();return job
@router.get('/jobs',response_model=list[SyncOut])
async def jobs(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id,management=True);return list(await db.scalars(select(GoogleAdsSyncJob).where(GoogleAdsSyncJob.connection_id==row.id).order_by(GoogleAdsSyncJob.created_at.desc()).limit(20))) if row else []
@router.get('/accounts',response_model=list[AccountOut])
async def accounts(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id)
    await ads_authority.legacy(db,row,'google_ads')
    if not row:return []
    items=list(await db.scalars(select(AdEntity).where(AdEntity.google_connection_id==row.id,AdEntity.connection_version==row.version,AdEntity.platform=='google',AdEntity.kind=='account').order_by(AdEntity.remote_id)))
    return [AccountOut(id=x.remote_id,name=x.name,currency=x.currency,timezone=x.timezone,status=x.status,manager=False) for x in items]
class MetricOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    account_id:str;level:str;entity_id:str;campaign_id:str|None;adset_id:str|None;day:date;hour:int;granularity:str;currency:str;timezone:str;attribution:str;spend:Decimal|None;impressions:int|None;clicks:int|None;conversions:Decimal|None;conversion_value:Decimal|None;ctr:Decimal|None;cpc:Decimal|None;cpm:Decimal|None;cpa:Decimal|None;roas:Decimal|None;updated_at:datetime
@router.get('/metrics',response_model=list[MetricOut])
async def metrics(workspace_id:UUID,account_id:str=Query(pattern=r'^\d{10}$'),since:date=Query(),until:date=Query(),level:str=Query('campaign',pattern='^(campaign|adset|ad)$'),granularity:str=Query('daily',pattern='^(daily|hourly)$'),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    if not 0<=(until-since).days<366:raise HTTPException(422,'Khoảng truy vấn tối đa 366 ngày')
    row=await connection(db,who,workspace_id)
    if not row:return []
    await ads_authority.legacy(db,row,'google_ads')
    return list(await db.scalars(select(AdMetric).where(AdMetric.google_connection_id==row.id,AdMetric.connection_version==row.version,AdMetric.platform=='google',AdMetric.account_id==account_id,AdMetric.level==level,AdMetric.granularity==granularity,AdMetric.day>=since,AdMetric.day<=until).order_by(AdMetric.day.desc(),AdMetric.hour,AdMetric.entity_id).limit(500)))
