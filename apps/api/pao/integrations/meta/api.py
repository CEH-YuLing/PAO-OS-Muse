import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...access import membership
from ...auth import Principal, principal, rate_limit
from ...config import settings
from ...db import database
from ...models import MetaConnection, MetaOAuthState, MetaSyncJob, MetaSnapshot, User, Workspace, Member, now
from .client import MetaClient, MetaError, configured, encrypt, FIELDS
from .schemas import ConnectionOut, OAuthStart, SyncCreate, SyncOut, SnapshotOut
from . import app_config
from .. import ads_apps,ads_oauth
from ...modules.connections import ads_authority

router=APIRouter(prefix='/v1/integrations/meta',tags=['meta'])
COOKIE='pao_meta_state'
CALLBACK='/v1/integrations/meta/callback'


@router.get('/tenant-app',response_model=ads_apps.AppStatus)
async def tenant_app(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await ads_apps.status(db,who,str(workspace_id),'meta')


@router.put('/tenant-app',response_model=ads_apps.AppStatus)
async def save_tenant_app(body:ads_apps.AppSave,workspace_id:UUID,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await rate_limit(request.app.state.redis,'meta-tenant-app',who.id,10,60)
    return await ads_apps.save(db,who,str(workspace_id),'meta',body)


async def app_config_owner(db, who, workspace_id):
    member = await membership(db, str(workspace_id), who)
    if member.role != 'owner':
        raise HTTPException(403, 'Chỉ owner được cấu hình Meta App của bản cài.')
    # SME ownership must never grant host .env authority in SaaS, even when
    # this happens to be the first/only enterprise. Explicit host-only opt-in
    # retains the old single-owner loopback installer, not a tenant setting.
    if not settings().meta_installation_config_enabled:
        raise HTTPException(410,'meta_installation_config_disabled')
    # This is a host .env setting, not a tenant-scoped credential store.
    owners = await db.scalar(select(func.count(func.distinct(Member.user_id))).where(Member.role == 'owner'))
    workspaces = await db.scalar(select(func.count(Workspace.id)))
    if owners != 1 or workspaces != 1:
        raise HTTPException(409, 'meta_app_config_requires_single_owner_workspace')


@router.get('/app-config', response_model=app_config.MetaAppStatus)
async def get_app_config(workspace_id: UUID, response: Response, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    await app_config_owner(db, who, workspace_id)
    response.headers['Cache-Control'] = 'no-store'
    return app_config.status()


@router.put('/app-config', response_model=app_config.MetaAppStatus)
async def put_app_config(body: app_config.MetaAppSave, workspace_id: UUID, request: Request,
                         response: Response, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    await app_config_owner(db, who, workspace_id)
    if request.client is None or request.client.host not in ('127.0.0.1', '::1'):
        raise HTTPException(403, 'meta_app_config_local_only')
    await rate_limit(request.app.state.redis, 'meta-app-config', who.id, 5, 60)
    await db.execute(select(Workspace.id).where(Workspace.id == str(workspace_id)).with_for_update())
    if await db.scalar(select(func.count(MetaConnection.id)).where(MetaConnection.token_ciphertext.is_not(None))):
        raise HTTPException(409, 'meta_app_disconnect_before_change')
    if await db.scalar(select(func.count(MetaSyncJob.id)).where(MetaSyncJob.status.in_(('queued', 'running')))):
        raise HTTPException(409, 'meta_app_wait_for_sync')
    if await db.scalar(select(func.count(MetaOAuthState.digest)).where(MetaOAuthState.used.is_(False), MetaOAuthState.expires_at > now())):
        raise HTTPException(409, 'meta_app_wait_for_oauth')
    response.headers['Cache-Control'] = 'no-store'
    return app_config.save(body)


class HideOAuthQuery(logging.Filter):
    def filter(self, record):
        if isinstance(record.args,tuple) and len(record.args)==5 and str(record.args[2]).split('?')[0]==CALLBACK:
            args=list(record.args);args[2]=CALLBACK;record.args=tuple(args)
        return True


logging.getLogger('uvicorn.access').addFilter(HideOAuthQuery())


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def require_config():
    try:configured()
    except MetaError as exc:raise HTTPException(503,str(exc)) from None


async def connection(db,who,wid,write=False,create=False,management=False):
    member=await membership(db,str(wid),who)
    if write and member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được quản lý kết nối Meta')
    # Serialize creation and sync requests across API processes.
    if write:await db.execute(select(Workspace.id).where(Workspace.id==str(wid)).with_for_update())
    row=await db.scalar(select(MetaConnection).where(MetaConnection.workspace_id==str(wid),MetaConnection.user_id==who.id).with_for_update() if write else select(MetaConnection).where(MetaConnection.workspace_id==str(wid),MetaConnection.user_id==who.id))
    if row is None and create:
        row=MetaConnection(workspace_id=str(wid),user_id=who.id);db.add(row);await db.flush()
    if not write and not management:await ads_authority.legacy(db,row,'meta_ads')
    return row


@router.get('/connection',response_model=ConnectionOut)
async def status(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id,management=True)
    try:ads_apps.validate(await ads_apps.resolve(db,str(workspace_id),'meta'),'meta');ready=True
    except MetaError:ready=False
    state=row.status if row else 'disconnected'
    if row and row.expires_at and row.expires_at<=now():state='expired'
    if row and row.status=='connected' and not await ads_apps.matches(db,row,'meta'):state='expired'
    return ConnectionOut(configured=ready,status=state,remote_user_id=row.remote_user_id if row else None,
        scopes=row.scopes if row else [],expires_at=row.expires_at if row else None)


@router.post('/oauth/start',response_model=OAuthStart)
async def start(workspace_id: UUID,request: Request,response: Response,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    return await ads_oauth.start(db,who,workspace_id,request,response,'meta',connection,COOKIE,CALLBACK)


@router.get('/callback',response_class=HTMLResponse)
async def callback(request: Request,state: str=Query('',max_length=256),code: str=Query('',max_length=8192),db: AsyncSession=Depends(database)):
    return await ads_oauth.callback(db,request,state,code,'meta',COOKIE,CALLBACK)


@router.delete('/connection',status_code=204)
async def disconnect(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id,True)
    if row:
        row.version+=1;row.status='disconnected';row.token_ciphertext=None;row.scopes=[];row.expires_at=None;row.remote_user_id=None
        await db.execute(update(MetaOAuthState).where(MetaOAuthState.connection_id==row.id).values(used=True))
        await db.execute(update(MetaSyncJob).where(MetaSyncJob.connection_id==row.id,MetaSyncJob.status.in_(['queued','running'])).values(status='cancelled',updated_at=now()))
        await db.commit()


@router.post('/sync',response_model=SyncOut,status_code=202)
async def sync(body: SyncCreate,request: Request,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    from ...modules.connections import read_resources
    try:await membership(db,str(body.workspace_id),who,True)
    except HTTPException as exc:
        if body.grant_id and exc.status_code==404:raise HTTPException(403,ads_authority.DENIED) from None
        raise
    await read_resources.lock(db,str(body.workspace_id))
    await rate_limit(request.app.state.redis,'meta-sync',who.id,10,60)
    authority=None
    if body.grant_id:
        row,authority=await ads_authority.selected(db,str(body.workspace_id),who.id,
            str(body.brand_id) if body.brand_id else None,body.account_id,str(body.grant_id),'meta_ads',write=True)
    else:
        row=await connection(db,who,body.workspace_id,True)
        await ads_authority.legacy(db,row,'meta_ads')
    if not row or row.status!='connected' or not row.expires_at or row.expires_at<=now():raise HTTPException(409,'Kết nối lại Meta trước khi đồng bộ')
    try:app_context=await ads_apps.bound(db,row,'meta')
    except MetaError as exc:raise HTTPException(409,str(exc)) from None
    old=await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id==row.id,MetaSyncJob.request_key==str(body.request_key)))
    dates=(body.since.isoformat() if body.since else None,body.until.isoformat() if body.until else None)
    if old:
        if old.authority_pin!=authority:raise HTTPException(409,'ads_sync_authority_request_key_conflict')
        if (old.kind,old.account_id,old.since,old.until,old.connection_version,old.warehouse,old.granularity)!=(body.kind,body.account_id,*dates,row.version,body.warehouse,body.granularity):raise HTTPException(409,'request_key đã dùng cho yêu cầu khác')
        return old
    active=await db.scalar(select(MetaSyncJob.id).where(MetaSyncJob.connection_id==row.id,MetaSyncJob.status.in_(['queued','running'])))
    if active:raise HTTPException(409,'Đang có một lượt đồng bộ Meta')
    if body.kind=='historical' and authority is None:
        account=await db.scalar(select(MetaSnapshot.id).join(MetaSyncJob).where(MetaSyncJob.connection_id==row.id,
            MetaSyncJob.connection_version==row.version,MetaSyncJob.status=='completed',MetaSnapshot.kind=='accounts',MetaSnapshot.remote_key==body.account_id))
        if not account:raise HTTPException(409,'Đồng bộ danh sách tài khoản và chọn tài khoản được phép trước')
    await read_resources.admit(db,row.workspace_id)
    job=MetaSyncJob(connection_id=row.id,connection_version=row.version,api_version=app_context.config.meta_graph_api_version,
        authority_pin=authority,
        request_key=str(body.request_key),kind=body.kind,account_id=body.account_id,since=dates[0],until=dates[1],warehouse=body.warehouse,granularity=body.granularity)
    db.add(job);await db.commit()
    # Durable DB queue is dispatched by the existing single ARQ worker.
    return job


@router.get('/jobs',response_model=list[SyncOut])
async def jobs(workspace_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id,management=True)
    if not row:return []
    return list(await db.scalars(select(MetaSyncJob).where(MetaSyncJob.connection_id==row.id).order_by(MetaSyncJob.created_at.desc()).limit(20)))


@router.get('/snapshots',response_model=SnapshotOut)
async def snapshots(workspace_id: UUID,kind: str=Query('accounts',pattern='^(accounts|campaigns|adsets|ads|insights)$'),
    account_id: str | None=Query(None,pattern=r'^act_[0-9]{1,32}$'),offset: int=Query(0,ge=0,le=100000),
    who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    row=await connection(db,who,workspace_id)
    await ads_authority.legacy(db,row,'meta_ads')
    if not row or row.status!='connected':return SnapshotOut(job=None,rows=[],has_more=False)
    job=await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id==row.id,MetaSyncJob.connection_version==row.version,
        MetaSyncJob.status=='completed',MetaSyncJob.warehouse.is_(False),MetaSyncJob.kind==('accounts' if kind=='accounts' else 'historical'),
        MetaSyncJob.account_id==(None if kind=='accounts' else account_id)).order_by(MetaSyncJob.created_at.desc()).limit(1))
    if not job:return SnapshotOut(job=None,rows=[],has_more=False)
    rows=list(await db.scalars(select(MetaSnapshot.payload).where(MetaSnapshot.job_id==job.id,MetaSnapshot.kind==kind).order_by(MetaSnapshot.remote_key).offset(offset).limit(51)))
    return SnapshotOut(job=SyncOut.model_validate(job),rows=rows[:50],has_more=len(rows)>50)
