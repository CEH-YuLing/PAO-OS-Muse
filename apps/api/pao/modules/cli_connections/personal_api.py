"""Simple own-profile setup. No Docker/auth/inference I/O or member sharing."""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field,StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal,check_session
from ...access import membership
from ...db import database
from ...models import Workspace,CliModelConnection,PersonalCliPolicy,PersonalCliRevision
from ..engines.contract import EngineFailure
from ..engines.service import digest
from . import personal,service
router=APIRouter(prefix='/v1/workspaces/{workspace_id}/personal-cli',tags=['personal-cli'])
class Save(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:UUID
    expected_revision:int=Field(ge=0,strict=True)
    connection_id:UUID|None=None
    enabled:StrictBool
    make_default:StrictBool=False
    allow_personal_inference_ack:StrictBool=False

async def managing(db,wid,who):
    await membership(db,wid,who);await check_session(db,who)
    try:return await personal.principal_state(db,wid,who.id)
    except EngineFailure:raise HTTPException(403,'Chỉ chủ sở hữu/quản trị viên được thiết lập Codex của chính mình') from None

async def view(db,wid,uid):
    row=await personal.policy(db,wid,uid);ready=False
    if row and row.content.get('enabled'):
        try:await personal.pin(db,wid,uid);ready=True
        except EngineFailure:pass
    rows=list(await db.scalars(select(CliModelConnection).where(CliModelConnection.workspace_id==wid,
        CliModelConnection.owner_id==uid).order_by(CliModelConnection.created_at,CliModelConnection.id).limit(100)))
    selected=(row.content.get('source_pin') or {}).get('connection_id') if row else None
    return {'workspace_id':wid,'actor_id':uid,'revision':row.revision if row else 0,'enabled':bool(row and row.content['enabled']),
        'make_default':bool(row and row.content.get('make_default')),'ready':ready,'connection_id':selected,
        'connections':[{'id':v.id,'model':v.model,'status':v.status,'authentication_ready':v.status=='connected' and v.auth_checked_at is not None,
            'operation_pending':v.setup_operation_id is not None} for v in rows],
        'scope':'local_personal_self_only','tools_enabled':False,'provider_calls':False,'expires_at':None,
        'help':'Chỉ hồ sơ của bạn trong không gian này. Lưu không chạy AI. Tắt thiết lập hoặc ngắt hồ sơ để dừng; quyền cá nhân cũ là cơ chế riêng.'}

@router.get('')
async def read(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id);await managing(db,wid,who)
    return await view(db,wid,who.id)

@router.put('')
async def save(workspace_id:UUID,body:Save,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await membership(db,wid,who)
    await db.scalar(select(Workspace.id).where(Workspace.id==wid).with_for_update())
    epoch,auth,_=await managing(db,wid,who)
    fingerprint=digest(body.model_dump(mode='json'))
    old=await db.scalar(select(PersonalCliRevision).where(PersonalCliRevision.workspace_id==wid,
        PersonalCliRevision.actor_id==who.id,PersonalCliRevision.request_key==str(body.request_key)))
    if old:
        if old.fingerprint!=fingerprint:raise HTTPException(409,'personal_cli_request_conflict')
        return {**await view(db,wid,who.id),'replayed':True,'saved_revision':old.revision}
    row=await personal.policy(db,wid,who.id)
    if body.expected_revision!=(row.revision if row else 0):raise HTTPException(409,'personal_cli_revision_conflict')
    source_pin=None
    if body.enabled:
        if not body.connection_id or not body.allow_personal_inference_ack:raise HTTPException(422,'personal_cli_consent_required')
        try:source_pin=service.pin(await service.source(db,wid,who.id,str(body.connection_id)))
        except EngineFailure as error:raise HTTPException(409,error.code) from None
    content={'version':personal.VERSION,'enabled':body.enabled,'make_default':body.enabled and body.make_default,
        'source_pin':source_pin,'membership_epoch':epoch,'auth_version':auth}
    from .model_catalog import next_revision
    revision=await next_revision(db,wid,who.id)
    if row:row.revision=revision;row.content=content
    else:row=PersonalCliPolicy(workspace_id=wid,actor_id=who.id,revision=revision,content=content);db.add(row)
    db.add(PersonalCliRevision(workspace_id=wid,actor_id=who.id,revision=row.revision,content=content,
        request_key=str(body.request_key),fingerprint=fingerprint))
    await db.commit()
    return {**await view(db,wid,who.id),'replayed':False,'saved_revision':row.revision}
