"""Small installation settings API. No inference and no per-user model grants."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal, check_session
from ...db import database
from ...access import membership
from ..engines.contract import EngineFailure
from ..engines.service import digest
from . import service
from .models import InstallationAIResource, InstallationAIRevision

router=APIRouter(prefix='/v1/installation-ai',tags=['installation-ai'])


class Save(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:UUID
    expected_revision:int=Field(ge=1,strict=True)
    enabled:StrictBool
    is_default:StrictBool=False
    default_model:str=Field(min_length=1,max_length=120)


@router.get('')
async def listing(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await membership(db,str(workspace_id),who)
    await check_session(db,who)
    if not service.enabled():
        return {'enabled':False,'can_manage':False,'resources':[],'provider_calls':False}
    can_manage=await service.manager(db,who.id)
    rows=await service.catalog(db,str(workspace_id),who.id)
    result=[]
    for item in rows:
        row=await db.get(InstallationAIResource,item['installation_resource_id'])
        result.append({**item,'revision':row.revision,'enabled':row.enabled,
            'is_default':row.is_default,'default_model':row.default_model,
            'availability':'catalog_only','tools_granted':False})
    from .compatibility import preview
    return {'enabled':True,'can_manage':can_manage,'resources':result,'provider_calls':False,
            'compatibility_preview':await preview(db,str(workspace_id),who.id) if can_manage else None}


@router.put('/{resource_id}')
async def save(resource_id:UUID,body:Save,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await check_session(db,who)
    if not await service.manager(db,who.id):
        raise HTTPException(403,'Chỉ quản trị bản cài được cấu hình tài nguyên AI dùng chung')
    await service.lock(db)
    row=await db.scalar(select(InstallationAIResource).where(InstallationAIResource.id==str(resource_id)).with_for_update())
    if not row:raise HTTPException(404,'Không tìm thấy tài nguyên AI')
    fingerprint=digest({'resource_id':str(resource_id),**body.model_dump(mode='json')})
    old=await db.scalar(select(InstallationAIRevision).where(InstallationAIRevision.request_key==str(body.request_key)))
    if old:
        if old.actor_id!=who.id or old.resource_id!=row.id or old.fingerprint!=fingerprint:
            raise HTTPException(409,'installation_ai_request_conflict')
        return {'saved_revision':old.revision,'replayed':True,'provider_calls':False}
    if row.revision!=body.expected_revision:raise HTTPException(409,'installation_ai_revision_conflict')
    from .catalog import selection
    try:
        selection(row.catalog,body.default_model)
        if body.enabled:
            from .modalities import require_chat
            require_chat(row.provider,body.default_model,next(v for v in row.catalog if v['model']==body.default_model))
    except ValueError:raise HTTPException(422,'Model không có trong danh mục đã đọc') from None
    if body.enabled:
        if row.source_kind=='cli' and row.provider!='muse':raise HTTPException(409,'installation_ai_cli_adapter_pending')
        try:
            if not await service.manager(db,row.owner_id) or await service.source(db,row)!=row.source_stamp:
                raise EngineFailure('installation_ai_source_changed')
        except EngineFailure as exc:raise HTTPException(409,exc.code) from None
    if body.is_default and body.enabled:
        # Explicit replacement, with history for the old default too. No run is
        # repinned. A disabled resource can always be disabled after disconnect.
        other=await db.scalar(select(InstallationAIResource).where(InstallationAIResource.is_default.is_(True),InstallationAIResource.id!=row.id).with_for_update())
        if other:
            other.is_default=False;other.revision+=1
            from uuid import uuid4
            await service.record(db,other,who.id,str(uuid4()),digest({'replaced_by':row.id,'revision':other.revision}))
            await db.flush()
    row.enabled=body.enabled;row.is_default=body.enabled and body.is_default
    row.default_model=body.default_model;row.revision+=1
    await service.record(db,row,who.id,str(body.request_key),fingerprint)
    await db.commit()
    return {'saved_revision':row.revision,'replayed':False,'provider_calls':False}
