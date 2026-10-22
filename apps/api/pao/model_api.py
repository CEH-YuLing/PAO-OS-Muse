from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter,Depends,HTTPException,Request,Response,Header
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select,update
from sqlalchemy.ext.asyncio import AsyncSession

from .access import membership
from .auth import Principal,principal,rate_limit
from .db import database
from .gateway import cloud_gateway
from .model_router import PROVIDERS,ModelRouterError,choose_model,decrypt_key,encrypt_key,fetch_models
from .model_router import fetch_model_catalog
from .modules.installation_ai import service as installation_ai
from .models import Member,ModelProviderConnection,now
from .modules.connections import model_fence
from .modules.connections import resources
from .modules.connections import model_metadata
from .db import Session
import asyncio
from uuid import uuid4
from .modules.engines.contract import EngineFailure
import hashlib

Provider=Literal['openai','anthropic','gemini','openrouter']
router=APIRouter(prefix='/v1/model-providers',tags=['model-providers'])

class ConnectIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id:UUID
    api_key:str=Field(min_length=12,max_length=4096)
    model:str=Field(default='',max_length=160)
class ModelIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    workspace_id:UUID
    model:str=Field(min_length=1,max_length=160)
class ProviderOut(BaseModel):
    provider:str;name:str;configured:bool;status:str;is_default:bool;model:str|None=None
    model_count:int=0;last_checked_at:datetime|None=None;last_error:str|None=None;key_hint:str|None=None
class ConnectOut(ProviderOut):models:list[str]

async def access(db,wid,who,write=False):
    member=await membership(db,str(wid),who,write)
    if write and member.role not in ('owner','admin'):raise HTTPException(403,'Chỉ owner/admin được quản lý cloud model')
    return member
def fail(exc):
    messages={'provider_authentication_failed':'API key không hợp lệ hoặc không có quyền truy cập',
              'provider_unavailable':'Không thể kết nối nhà cung cấp model',
              'provider_has_no_chat_models':'Nhà cung cấp không trả về model chat khả dụng',
              'model_not_available':'Model đã chọn không còn khả dụng',
              'model_encryption_not_configured':'PAO chưa cấu hình mã hóa credential'}
    raise HTTPException(422 if str(exc) in ('model_not_available','provider_has_no_chat_models') else 503,messages.get(str(exc),'Không thể cấu hình cloud model'))

async def unregistered_probe(db,wid):
    try:await model_fence.unregistered(db,wid)
    except EngineFailure:raise HTTPException(403,'model_probe_requires_explicit_grant_run') from None
def output(provider,row=None):
    return {'provider':provider,'name':PROVIDERS[provider]['name'],'configured':bool(row),
            'status':row.status if row else 'available','is_default':bool(row and row.is_default),
            'model':row.model if row else None,'model_count':row.model_count if row else 0,
            'last_checked_at':row.last_checked_at if row else None,'last_error':row.last_error if row else None,
            'key_hint':('••••'+decrypt_key(row.api_key_ciphertext)[-4:]) if row else None}

@router.get('',response_model=list[ProviderOut])
async def listing(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await access(db,workspace_id,who)
    rows={x.provider:x for x in await db.scalars(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==str(workspace_id)))}
    return [output(provider,rows.get(provider)) for provider in PROVIDERS]

@router.post('/{provider}/connect',response_model=ConnectOut)
async def connect(provider:Provider,body:ConnectIn,request:Request,response:Response,idempotency_key:UUID|None=Header(default=None),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await access(db,body.workspace_id,who,True);await rate_limit(request.app.state.redis,'model-connect',who.id,10,60)
    try:
        wid=str(body.workspace_id)
        row,expected,lease=await model_metadata.begin(db,wid,provider,who,'model_connect',idempotency_key)
        cipher=encrypt_key(body.api_key)
        shared=await installation_ai.manager(db,who.id)
        catalogue=await model_metadata.admitted_fetch(db,provider,body.api_key,fetch_model_catalog if shared else fetch_models,lease)
        models=[v['model'] for v in catalogue] if shared else catalogue
        model=choose_model(provider,models,body.model)
        row=await model_metadata.source(db,wid,provider,who,expected,publication=True)
        if not row:
            has_default=await db.scalar(select(ModelProviderConnection.id).where(ModelProviderConnection.workspace_id==str(body.workspace_id),ModelProviderConnection.is_default.is_(True)))
            row=ModelProviderConnection(workspace_id=str(body.workspace_id),provider=provider,api_key_ciphertext=cipher,model=model,is_default=not bool(has_default))
            db.add(row)
        else:row.api_key_ciphertext=cipher;row.model=model
        row.status='connected';row.model_count=len(models);row.last_checked_at=now();row.last_error=None;row.updated_at=now()
        if shared:
            await db.flush()
            await installation_ai.capture(db,who.id,wid,row.id,'api',catalogue)
        await db.commit();return {**output(provider,row),'models':models}
    except ModelRouterError as exc:
        await db.rollback();fail(exc)
    except HTTPException:
        await db.rollback();raise
    except Exception:
        await db.rollback();raise HTTPException(503,'Không thể lưu cấu hình cloud model')

@router.get('/{provider}/models')
async def models(provider:Provider,workspace_id:UUID,request:Request,response:Response,idempotency_key:UUID|None=Header(default=None),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await access(db,workspace_id,who,True);await rate_limit(request.app.state.redis,'model-list',who.id,20,60)
    wid=str(workspace_id)
    row,expected,lease=await model_metadata.begin(db,wid,provider,who,'model_catalogue',idempotency_key,existing=True)
    shared=await installation_ai.manager(db,who.id)
    try:catalogue=await model_metadata.admitted_fetch(db,provider,decrypt_key(row.api_key_ciphertext),fetch_model_catalog if shared else fetch_models,lease)
    except ModelRouterError as exc:fail(exc)
    items=[v['model'] for v in catalogue] if shared else catalogue
    row=await model_metadata.source(db,wid,provider,who,expected,publication=True)
    row.model_count=len(items);row.last_checked_at=now();row.last_error=None
    if shared:await installation_ai.capture(db,who.id,wid,row.id,'api',catalogue)
    await db.commit()
    return {'provider':provider,'models':items,'selected':row.model}

@router.put('/{provider}/model',response_model=ProviderOut)
async def set_model(provider:Provider,body:ModelIn,response:Response,idempotency_key:UUID|None=Header(default=None),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await access(db,body.workspace_id,who,True)
    wid=str(body.workspace_id)
    row,expected,lease=await model_metadata.begin(db,wid,provider,who,'model_select',idempotency_key,existing=True)
    try:
        items=await model_metadata.admitted_fetch(db,provider,decrypt_key(row.api_key_ciphertext),fetch_models,lease)
        selected=choose_model(provider,items,body.model)
    except ModelRouterError as exc:fail(exc)
    row=await model_metadata.source(db,wid,provider,who,expected,publication=True)
    row.model=selected
    row.model_count=len(items);row.last_checked_at=now();row.updated_at=now();await db.commit();return output(provider,row)

@router.post('/{provider}/default',response_model=ProviderOut)
async def set_default(provider:Provider,workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await access(db,workspace_id,who,True)
    row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==str(workspace_id),ModelProviderConnection.provider==provider).with_for_update())
    if not row or row.status!='connected':raise HTTPException(409,'Provider chưa được kết nối')
    await db.execute(update(ModelProviderConnection).where(ModelProviderConnection.workspace_id==str(workspace_id)).values(is_default=False))
    row.is_default=True;row.updated_at=now();await db.commit();return output(provider,row)

@router.post('/{provider}/test')
async def test(provider:Provider,workspace_id:UUID,request:Request,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    await access(db,workspace_id,who,True);await rate_limit(request.app.state.redis,'model-test',who.id,10,60)
    wid=str(workspace_id)
    await resources.lock(db,wid)
    await unregistered_probe(db,wid) # No implicit test-inference through registered grants.
    row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==wid,ModelProviderConnection.provider==provider).with_for_update(read=True))
    if not row:raise HTTPException(409,'Provider chưa được kết nối')
    pinned={'connection_id':row.id,'provider':provider,'model':row.model,'status':row.status,
        'credential_binding':hashlib.sha256(row.api_key_ciphertext.encode()).hexdigest(),
        'management_probe':True,'actor_id':who.id}
    try:await model_fence.check_source(db,wid,pinned)
    except EngineFailure:
        await db.rollback();raise HTTPException(403,'model_probe_authority_changed') from None
    try:
        lease=await resources.admit(db,wid,who.id,'management_probe',uuid4().hex,96)
        await db.flush()
    except EngineFailure as exc:
        await db.rollback();raise HTTPException(429,exc.code) from None
    admitted=False
    try:
        gateway=model_fence.ModelFenceGateway(cloud_gateway(provider,decrypt_key(row.api_key_ciphertext),row.model),wid,source_pin=pinned)
        await db.commit() # Source lock covers validation->key resolution, NOT network.
        admitted=True
        text=''
        source=gateway.stream([{'role':'user','content':'Reply with exactly: PAO OK'}],max_tokens=16)
        try:
            async with asyncio.timeout(resources.CALL_TIMEOUT):
                async for chunk in source:
                    text+=chunk.text
                    if len(text.encode())>64:raise ModelRouterError('provider_unavailable')
        finally:
            async with asyncio.timeout(resources.CLOSE_TIMEOUT):await source.aclose()
        if not text.strip():raise ModelRouterError('provider_unavailable')
        await unregistered_probe(db,wid)
        row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.id==pinned['connection_id'],ModelProviderConnection.workspace_id==wid).with_for_update().execution_options(populate_existing=True))
        await model_fence.check_source(db,wid,pinned)
        row.status='connected';row.last_checked_at=now();row.last_error=None;await db.commit();return {'ok':True,'provider':provider,'model':row.model}
    except (HTTPException,EngineFailure):
        await db.rollback();raise HTTPException(403,'model_probe_authority_changed') from None
    except Exception:
        await db.rollback()
        await unregistered_probe(db,wid)
        row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.id==pinned['connection_id'],ModelProviderConnection.workspace_id==wid).with_for_update().execution_options(populate_existing=True))
        try:await model_fence.check_source(db,wid,pinned)
        except EngineFailure:raise HTTPException(403,'model_probe_authority_changed') from None
        row.status='error';row.last_checked_at=now();row.last_error='test_failed';await db.commit();raise HTTPException(503,'Provider không hoàn tất được lượt kiểm tra')
    finally:
        if admitted:
            async with Session.begin() as cleanup:
                await resources.lock(cleanup,wid)
                await resources.release(cleanup,wid,lease=lease.id)

@router.delete('/{provider}',status_code=204)
async def disconnect(provider:Provider,workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await access(db,workspace_id,who,True)
    row=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==str(workspace_id),ModelProviderConnection.provider==provider).with_for_update())
    if row:await db.delete(row);await db.commit()
