"""Template != actual connection != encrypted secret; owner explicitly opts in."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query,Response,Header
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal
from ...access import membership
from ...db import database
from ...models import ConnectionReadActivation, ConnectorConnection,ConnectorSecret,ConnectorEvent,TenantConnectionGrant,Workspace
from ...config import settings
from ..studio.contracts import Closed,validate_value
from .transport import endpoint,ConnectorFailure
from .service import owned,enabled,event,revision,seal,public,view,probe,cancel_calls,approved_tool
router=APIRouter(prefix='/v1/connectors')

class Connect(Closed):
    workspace_id:str
    brain_id:str|None=None
    endpoint:str=Field(min_length=8,max_length=1000)
    token:str|None=Field(default=None,min_length=12,max_length=2048,repr=False,pattern=r'^[\x21-\x7e]+$')
    readonly_credentials_ack:Literal[True]
class Version(Closed):version:int=Field(ge=1)
class Permission(Version):
    tool_id:str=Field(max_length=64)
    schema_hash:str=Field(pattern=r'^[0-9a-f]{64}$')
    bound_arguments:dict
    readonly_server_ack:Literal[True]
class Rotate(Version):
    token:str=Field(min_length=12,max_length=2048,repr=False,pattern=r'^[\x21-\x7e]+$')
class Call(Closed):
    run_id:UUID=Field(strict=False)
    tool_id:str=Field(max_length=64)
    request_key:str=Field(min_length=1,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')
    grant_id:UUID|None=Field(default=None,strict=False)

@router.get('/grants')
async def granted_connections(workspace_id:UUID,response:Response,brand_id:UUID|None=None,brain_id:UUID|None=None,run_id:UUID|None=None,
                              limit:int=Query(50,ge=1,le=100),offset:int=Query(0,ge=0,le=10000),
                              who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    """Own eligible grants only; metadata is not a probe or tool permission."""
    from ..connections import grants,read_authority
    enabled();response.headers['Cache-Control']='no-store';workspace=str(workspace_id)
    await grants.active_member(db,workspace,who.id)
    brand=str(brand_id) if brand_id else None;brain=str(brain_id) if brain_id else None
    if run_id:
        from ...access import owned_run
        from ...models import ChatSession
        from ..brains.context import check_run_brain
        run=await owned_run(db,str(run_id),who,True)
        if run.workspace_id!=workspace:raise HTTPException(404,'connector_run_not_found')
        chat=await db.get(ChatSession,run.session_id)
        current=await check_run_brain(db,run,chat)
        run_brand=(run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id
        if current and (current.workspace_id!=workspace or current.brand_id!=run_brand):
            raise HTTPException(403,'connector_brain_scope_denied')
        if (brand_id and brand!=run_brand) or (brain_id and brain!=run.brain_id):
            raise HTTPException(403,'connector_run_scope_denied')
        brand=run_brand;brain=run.brain_id
    if brain:
        from ..brains.access import require_brain
        selected=await require_brain(db,who,brain,True)
        if selected.workspace_id!=workspace or selected.brand_id!=brand:
            raise HTTPException(404,'connector_brain_not_found')
    ids=list(await db.scalars(select(TenantConnectionGrant.id).join(ConnectionReadActivation,
        ConnectionReadActivation.grant_id==TenantConnectionGrant.id).where(
        TenantConnectionGrant.workspace_id==workspace,TenantConnectionGrant.grantee_id==who.id,
        TenantConnectionGrant.brand_id==brand,ConnectionReadActivation.kind=='mcp')
        .order_by(TenantConnectionGrant.created_at,TenantConnectionGrant.id).offset(offset).limit(limit+1)))
    items=[]
    for gid in ids[:limit]:
        try:
            authority=await read_authority.pin(db,workspace,who.id,brand,gid)
            row=await db.scalar(select(ConnectorConnection).where(ConnectorConnection.id==authority['source_id'],
                ConnectorConnection.workspace_id==workspace))
            if not row or (row.brain_id and row.brain_id!=brain):continue
            tools=[]
            for tid,permission in row.permissions.items():
                tool=approved_tool(row,tid,permission['hash'])
                tools.append({'id':tid,'name':tid.rsplit('.',1)[-1],'schema_hash':tool['hash']})
            items.append({'grant_id':gid,'connection_id':row.id,'brain_id':row.brain_id,'tools':tools,
                          'expires_at':authority['expires_at'],'native_skill_review_required':True})
        except HTTPException:continue
    return {'items':items,'has_more':len(ids)>limit,'external_calls':False,
            'acceptance':'local_authority_not_provider_health'}

@router.get('/templates')
async def templates(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await membership(db,str(workspace_id),who)
    return {'available':settings().connectors_enabled,'external_smoke':'not_verified','templates':[{
        'id':'mcp-https-readonly','transport':'streamable_http','protocol':'2025-11-25','requires_owner':True,
        'installed':False,'connected':False,'stdio_enabled':False,'code_install_enabled':False}]}

@router.get('/connections')
async def connections(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();await membership(db,str(workspace_id),who)
    rows=list(await db.scalars(select(ConnectorConnection).where(ConnectorConnection.workspace_id==str(workspace_id),ConnectorConnection.owner_id==who.id).limit(20)))
    return [public(row,bool(await db.scalar(select(ConnectorSecret.id).where(ConnectorSecret.connection_id==row.id,ConnectorSecret.ciphertext.is_not(None))))) for row in rows]

@router.post('/connections',status_code=201)
async def connect(body:Connect,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled()
    try:workspace=str(UUID(body.workspace_id));url=endpoint(body.endpoint)
    except (ValueError,ConnectorFailure):raise HTTPException(422,'connector_endpoint_or_scope_invalid') from None
    member=await membership(db,workspace,who,True)
    if member.role not in ('owner','admin'):raise HTTPException(403,'connector_owner_required')
    await db.scalar(select(Workspace).where(Workspace.id==workspace).with_for_update())
    if len(list(await db.scalars(select(ConnectorConnection.id).where(ConnectorConnection.workspace_id==workspace).limit(20))))>=20:
        raise HTTPException(409,'connector_connection_limit')
    brain_id=None
    if body.brain_id:
        from ..brains.access import require_brain
        brain=await require_brain(db,who,body.brain_id)
        if brain.workspace_id!=workspace:raise HTTPException(404,'connector_brain_not_found')
        brain_id=brain.id
    cipher=seal(body.token) if body.token else None
    row=ConnectorConnection(workspace_id=workspace,owner_id=who.id,brain_id=brain_id,endpoint=url,status='draft',
        version=1,manifest={},permissions={},failures=0)
    db.add(row);await db.flush()
    db.add(ConnectorSecret(workspace_id=workspace,connection_id=row.id,ciphertext=cipher))
    event(db,row,who.id,'draft_created',readonly_credentials_ack=True)
    await db.commit()
    return public(row,bool(cipher))

@router.post('/connections/{connection_id}/test')
async def test(connection_id:UUID,body:Version,response:Response,idempotency_key:UUID|None=Header(default=None),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    row=await probe(db,str(connection_id),who,body.version,idempotency_key)
    return await view(db,row)

@router.put('/connections/{connection_id}/permissions')
async def permissions(connection_id:UUID,body:Permission,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await owned(db,connection_id,who,True);revision(row,body.version)
    if row.status!='connected':raise HTTPException(409,'connector_not_connected')
    tool=approved_tool(row,body.tool_id,body.schema_hash)
    try:validate_value(tool['input_schema'],body.bound_arguments)
    except (ValueError,TypeError):raise HTTPException(422,'connector_arguments_invalid') from None
    row.permissions={**row.permissions,body.tool_id:{'hash':tool['hash'],'arguments':body.bound_arguments}}
    row.version+=1;await cancel_calls(db,row)
    event(db,row,who.id,'read_grant',tool_id=body.tool_id,hash=tool['hash'],readonly_server_ack=True)
    await db.commit();return await view(db,row)

@router.put('/connections/{connection_id}/credential')
async def rotate(connection_id:UUID,body:Rotate,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await owned(db,connection_id,who,True);revision(row,body.version)
    secret=await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row.id))
    secret.ciphertext=seal(body.token);row.version+=1;row.status='draft';row.permissions={}
    await cancel_calls(db,row);event(db,row,who.id,'credential_rotated')
    await db.commit();return public(row,True)

@router.post('/connections/{connection_id}/disconnect')
async def disconnect(connection_id:UUID,body:Version,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await owned(db,connection_id,who,True)
    if row.version!=body.version:raise HTTPException(409,'connector_revision_conflict')
    row.status='revoked';row.permissions={};row.version+=1
    secret=await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row.id))
    if secret:secret.ciphertext=None
    await cancel_calls(db,row);event(db,row,who.id,'revoked',credential_purged=True)
    await db.commit();return public(row)

@router.get('/connections/{connection_id}/audit')
async def history(connection_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await owned(db,connection_id,who)
    events=list(await db.scalars(select(ConnectorEvent).where(ConnectorEvent.connection_id==row.id).order_by(ConnectorEvent.created_at.desc()).limit(100)))
    return [{'id':item.id,'action':item.action,'data':item.data} for item in events]

@router.post('/connections/{connection_id}/calls',status_code=202)
async def call(connection_id:UUID,body:Call,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .gateway import propose
    if body.grant_id is None:await owned(db,connection_id,who)
    value=await propose(str(connection_id),str(body.run_id),who,body.tool_id,body.request_key,
                        str(body.grant_id) if body.grant_id else None)
    return {'id':value.id,'status':value.status,'result':value.result,'error_code':value.error_code}
