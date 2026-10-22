"""Secret-free CLI preparation. Saving is not login, probe, consent or execution."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal, check_session
from ...config import settings
from ...db import database, Session
from ...models import CliModelConnection, CliModelDispatch, Workspace, now
from ..engines.contract import EngineFailure
from ..connections.grants import active_member

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/cli-connections', tags=['cli-connections'])


class Create(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: UUID
    model: str = Field(min_length=1, max_length=120, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/+-]*$')


class Revision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1, strict=True)


def enabled():
    if not settings().cli_connections_enabled:
        raise HTTPException(503, 'cli_connections_disabled')


async def actor(db, workspace, who):
    enabled()
    await active_member(db, workspace, who.id, managing=True)
    await check_session(db, who)
    from ..operations.request_trace import bind_workspace
    bind_workspace(workspace)


def public(row):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'owner_id': row.owner_id,
            'provider': row.provider, 'model': row.model, 'version': row.version,
            'status': row.status, 'device_id': row.device_id, 'profile_id': row.profile_id,
            'authentication_ready': row.status == 'connected' and row.auth_checked_at is not None,
            'credentials_stored_in_PAO': False, 'scope': 'local_personal_self_only',
            'profile_operation_pending': row.setup_operation_id is not None,
            'tools_enabled': False, 'activation_required': True,
            'setup_help': 'Lưu chỉ tạo hồ sơ riêng. Đăng nhập bằng luồng chính thức của Codex trên thiết bị được chỉ định; '
                          'không dán token. Kiểm tra đăng nhập, chọn mô hình và duyệt quyền riêng trước khi chạy. '
                          'Ngắt PAO không đăng xuất hoặc thu hồi phiên Codex của ứng dụng khác.'}


@router.get('')
async def listing(workspace_id: UUID, response: Response, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    workspace = str(workspace_id)
    await actor(db, workspace, who)
    rows = list(await db.scalars(select(CliModelConnection).where(CliModelConnection.workspace_id == workspace,
        CliModelConnection.owner_id == who.id).order_by(CliModelConnection.created_at, CliModelConnection.id).limit(100)))
    return {'items': [public(row) for row in rows], 'external_calls': False}


@router.post('', status_code=201)
async def create(workspace_id: UUID, body: Create, response: Response,
                 who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    workspace = str(workspace_id)
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await actor(db, workspace, who)
    try:
        from .runtime import configured_device
        configured = configured_device()
        device = str(UUID(configured))
        if device != configured:
            raise ValueError()
    except (ValueError, TypeError, AttributeError, EngineFailure):
        raise HTTPException(503, 'cli_device_not_provisioned') from None
    old = await db.scalar(select(CliModelConnection).where(CliModelConnection.workspace_id == workspace,
        CliModelConnection.owner_id == who.id, CliModelConnection.request_key == str(body.request_key)))
    if old:
        if old.model != body.model or old.device_id != device:
            raise HTTPException(409, 'cli_registration_request_key_conflict')
        return {**public(old), 'replayed': True}
    count = await db.scalar(select(func.count()).select_from(CliModelConnection).where(CliModelConnection.workspace_id == workspace))
    if count >= 100:
        raise HTTPException(409, 'cli_connection_storage_limit')
    row = CliModelConnection(workspace_id=workspace, owner_id=who.id, provider='codex_cli',
        device_id=device, profile_id=str(uuid4()), request_key=str(body.request_key), model=body.model,
        version=1, status='pending')
    db.add(row)
    await db.flush()
    result = public(row)
    await db.commit()
    return {**result, 'replayed': False}


@router.post('/{connection_id}/disconnect')
async def disconnect(workspace_id: UUID, connection_id: UUID, body: Revision, response: Response,
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    workspace = str(workspace_id)
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await actor(db, workspace, who)
    row = await db.scalar(select(CliModelConnection).where(CliModelConnection.id == str(connection_id),
        CliModelConnection.workspace_id == workspace, CliModelConnection.owner_id == who.id).with_for_update())
    if row is None:
        raise HTTPException(404, 'cli_connection_not_found')
    if row.version != body.version:
        raise HTTPException(409, 'cli_connection_version_conflict')
    row.status = 'disconnected'
    row.auth_checked_at = None
    row.version += 1
    result = public(row)
    await db.commit()
    return {**result, 'provider_logout_performed': False}


async def managed(db, workspace, who, connection_id, version):
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await actor(db, workspace, who)
    row = await db.scalar(select(CliModelConnection).where(CliModelConnection.id == connection_id,
        CliModelConnection.workspace_id == workspace, CliModelConnection.owner_id == who.id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, 'cli_connection_not_found')
    if row.version != version:
        raise HTTPException(409, 'cli_connection_version_conflict')
    return row


async def profile_operation(db, workspace, who, connection_id, version, mode):
    from . import runtime, service
    from pao_cli_runtime.docker_transport import ImagePin
    from pao_cli_runtime.profile_transport import ProfileAdmin
    row = await managed(db, workspace, who, connection_id, version)
    try:
        config = runtime.device_config()
    except EngineFailure as error:
        raise HTTPException(503, error.code) from None
    if config['device_id'] != row.device_id:
        raise HTTPException(409, 'cli_device_changed')
    # Changing/rechecking authentication is an explicit setup operation, not a
    # silent mutation of an active grant. Disconnect first; old pins stay old.
    if row.status == 'connected':
        raise HTTPException(409, 'cli_disconnect_before_auth_change')
    if row.setup_operation_id or await db.scalar(select(CliModelDispatch.id).where(
            CliModelDispatch.connection_id == row.id, CliModelDispatch.status.in_(('dispatched','unknown')))):
        raise HTTPException(409, 'cli_profile_busy')
    if mode == 'status' and (row.status == 'disconnected' or not row.runtime_image_id):
        raise HTTPException(409, 'cli_profile_prepare_required')
    pin = {**service.pin(row), 'binary_sha256':config['binary_sha256'],
           'binary_version':config['binary_version'], 'runtime_image_id':config['image_id']}
    if mode == 'status' and (row.binary_sha256 != pin['binary_sha256'] or row.binary_version != pin['binary_version']
                             or row.runtime_image_id != pin['runtime_image_id']):
        raise HTTPException(409, 'cli_runtime_pin_changed')
    operation_id = str(uuid4())
    row.setup_operation_id = operation_id
    await db.commit()  # Durable setup fence; no DB lock across Docker I/O.
    admin = ProfileAdmin(ImagePin(config['image_id'], config['binary_sha256'], config['binary_version']))
    try:
        try:
            outcome = await admin.operation(pin, mode)
        except Exception:
            raise HTTPException(503, 'cli_profile_operation_failed') from None
        row = await managed(db, workspace, who, connection_id, version)
        if row.setup_operation_id != operation_id or runtime.device_config() != config:
            raise HTTPException(409, 'cli_runtime_pin_changed')
        if mode == 'initialize':
            row.binary_sha256, row.binary_version = pin['binary_sha256'], pin['binary_version']
            row.runtime_image_id = pin['runtime_image_id']
            row.status, row.auth_checked_at = 'pending', None
            row.version += 1
        elif outcome['auth_mode'] == 'chatgpt':
            row.status, row.auth_checked_at = 'connected', now()
            row.version += 1
        elif row.status != 'error':
            row.status, row.auth_checked_at = 'error', None
            row.version += 1
        if not admin.cleanup_verified:
            raise HTTPException(503, 'cli_profile_cleanup_unverified')
        row.setup_operation_id = None
        result = public(row)
        await db.commit()
        return {**result, 'provider_inference_verified': False, 'grant_activated': False,
                **({'login_command': admin.login_command(pin),
                    'login_help': 'Chạy lệnh bằng PowerShell trên đúng máy PAO, rồi đăng nhập trong trang chính thức của OpenAI. '
                                  'Không gửi mã đăng nhập hoặc token vào chat. Sau đó bấm kiểm tra đăng nhập; '
                                  'chọn mô hình và duyệt quyền riêng trước khi chạy.'} if mode == 'initialize' else {})}
    finally:
        # Housekeeping may release only this completed operation, even after
        # membership/session revocation. Unverified cleanup keeps a durable fence.
        await db.rollback()
        if admin.cleanup_verified:
            async with Session.begin() as cleanup:
                owned = await cleanup.scalar(select(CliModelConnection).where(CliModelConnection.id == connection_id,
                    CliModelConnection.workspace_id == workspace, CliModelConnection.setup_operation_id == operation_id).with_for_update())
                if owned:
                    owned.setup_operation_id = None


@router.post('/{connection_id}/prepare')
async def prepare_profile(workspace_id: UUID, connection_id: UUID, body: Revision, response: Response,
                          who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    return await profile_operation(db, str(workspace_id), who, str(connection_id), body.version, 'initialize')


@router.post('/{connection_id}/check-auth')
async def check_auth(workspace_id: UUID, connection_id: UUID, body: Revision, response: Response,
                     who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    return await profile_operation(db, str(workspace_id), who, str(connection_id), body.version, 'status')


class LoginStart(Revision):
    request_key: UUID
    allow_personal_login: StrictBool


class LoginCancel(Revision):
    operation_id: UUID


async def login_access(db,workspace,who,response):
    response.headers['Cache-Control']='no-store'
    response.headers['Pragma']='no-cache'
    await actor(db,workspace,who)
    if not settings().cli_browser_login_enabled:
        raise HTTPException(503,'cli_browser_login_disabled')
    if not who.token_hash:
        raise HTTPException(403,'cli_login_browser_session_required')


async def own_connection(db,workspace,who,connection,lock=False):
    query=select(CliModelConnection).where(CliModelConnection.id==connection,
        CliModelConnection.workspace_id==workspace,CliModelConnection.owner_id==who.id).execution_options(populate_existing=True)
    row=await db.scalar(query.with_for_update() if lock else query)
    if row is None:raise HTTPException(404,'cli_connection_not_found')
    return row


@router.get('/login-capabilities')
async def login_capabilities(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await actor(db,str(workspace_id),who)
    return {'provider':'codex_cli','browser_login_enabled':settings().cli_browser_login_enabled,
            'scope':'local_personal_self_only','managed_by':'official_codex_app_server',
            'subscription_sharing_enabled':False,'tools_enabled':False}


@router.post('/{connection_id}/login')
async def login_start(workspace_id:UUID,connection_id:UUID,body:LoginStart,request:Request,response:Response,
                      who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    workspace=str(workspace_id)
    await login_access(db,workspace,who,response)
    if not body.allow_personal_login:raise HTTPException(400,'cli_login_consent_required')
    from ...auth import rate_limit
    await rate_limit(request.app.state.redis,'cli-login',workspace+':'+who.id,6,60)
    await db.scalar(select(Workspace.id).where(Workspace.id==workspace).with_for_update())
    row=await own_connection(db,workspace,who,str(connection_id),True)
    if await db.scalar(select(CliModelDispatch.id).where(CliModelDispatch.connection_id==row.id,CliModelDispatch.status.in_(('dispatched','unknown')))):
        raise HTTPException(409,'cli_profile_busy')
    from .runtime import device_config
    try:config=device_config()
    except EngineFailure:raise HTTPException(503,'cli_runtime_pin_invalid') from None
    return await request.app.state.cli_logins.start(db,row,who,body.version,str(body.request_key),config)


@router.get('/{connection_id}/login')
async def login_status(workspace_id:UUID,connection_id:UUID,request:Request,response:Response,
                       who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    workspace=str(workspace_id)
    await login_access(db,workspace,who,response)
    row=await own_connection(db,workspace,who,str(connection_id))
    manager=request.app.state.cli_logins
    items=[x for x in manager.entries.values() if (x.workspace,x.actor,x.connection)==(workspace,who.id,row.id)]
    latest=max(items,key=lambda x:x.created,default=None)
    if latest and latest.version==row.version and (row.setup_operation_id==latest.operation or latest.task.done()):
        return latest.view(who)
    return {'operation_id':row.setup_operation_id,'connection_id':row.id,'version':row.version,
            'status':'interrupted' if row.setup_operation_id else 'connected' if row.status=='connected' and row.auth_checked_at else 'idle',
            'user_code':None,'verification_url':None,'expires_in':0,
            'provider_inference_verified':False,'grant_activated':False}


@router.post('/{connection_id}/login/cancel')
async def login_cancel(workspace_id:UUID,connection_id:UUID,body:LoginCancel,request:Request,response:Response,
                       who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    workspace=str(workspace_id)
    await login_access(db,workspace,who,response)
    await db.scalar(select(Workspace.id).where(Workspace.id==workspace).with_for_update())
    row=await own_connection(db,workspace,who,str(connection_id),True)
    operation=str(body.operation_id)
    if row.version!=body.version or row.setup_operation_id!=operation:
        raise HTTPException(409,'cli_login_operation_changed')
    row.version+=1;row.status='error';row.auth_checked_at=None
    from . import service
    pin=service.pin(row)
    await db.commit()
    manager=request.app.state.cli_logins
    item=manager.entries.get(operation)
    if item:
        if (item.workspace,item.actor,item.connection)!=(workspace,who.id,str(connection_id)):
            raise HTTPException(409,'cli_login_operation_changed')
        await manager.cancel(item)
    # Also handles an API restart or cancellation before the task first ran.
    from .login_transport import LoginTransport
    transport=LoginTransport(pin,operation)
    try:await transport.recover()
    except Exception:raise HTTPException(503,'cli_login_cleanup_required') from None
    async with Session.begin() as cleanup:
        owned=await cleanup.scalar(select(CliModelConnection).where(CliModelConnection.id==str(connection_id),
            CliModelConnection.workspace_id==workspace,CliModelConnection.setup_operation_id==operation).with_for_update())
        if owned:owned.setup_operation_id=None
    await login_access(db,workspace,who,response)
    current=await own_connection(db,workspace,who,str(connection_id))
    return {'connection_id':current.id,'version':current.version,'status':'cancelled','cleanup_verified':True,
            'provider_logout_performed':False,'grant_activated':False}
