"""Owner/admin per-SME model caps; no credentials, provider probes or billing."""
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal
from ...db import database
from ...models import TenantResourcePolicy,TenantReadPolicy,TenantMetadataPolicy,Member,User,now
from .inventory import manager
from . import resources
from . import read_resources
from . import metadata_resources

router=APIRouter(prefix='/v1/workspaces/{workspace_id}/resources',tags=['tenant-resources'])


class ModelLimits(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0,strict=True)
    daily_model_calls:int=Field(ge=1,le=10000,strict=True)
    daily_model_tokens:int=Field(ge=1,le=10000000,strict=True)
    concurrent_models:int=Field(ge=1,le=8,strict=True)


async def snapshot(db,wid):
    return {'model_policy':await resources.policy(db,wid),'host_ceilings':resources.CEILINGS,
        'usage':await resources.usage(db,wid),'accounting':'conservative_UTC_reservations_not_billing',
        'coverage':['accounted_llm_invocations','native_model_inference_probe','unaccounted_legacy_denied','memory_embeddings','knowledge_embeddings'],
        'pending_coverage':[],
        'grants_authorized':False}


async def authorize(db,wid,who):
    role=await db.scalar(select(Member.role).join(User,User.id==Member.user_id).where(
        Member.workspace_id==wid,Member.user_id==who.id,User.active.is_(True)).with_for_update(read=True))
    if role not in ('owner','admin'):raise HTTPException(403,'tenant_resource_manager_required')


@router.get('/models')
async def read(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await manager(db,wid,who)
    await resources.lock(db,wid)
    await authorize(db,wid,who)
    return await snapshot(db,wid)


@router.put('/models')
async def write(workspace_id:UUID,body:ModelLimits,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await manager(db,wid,who)
    await resources.lock(db,wid)
    await authorize(db,wid,who)
    row=await db.get(TenantResourcePolicy,wid,populate_existing=True)
    if (row.version if row else 0)!=body.expected_version:raise HTTPException(409,'tenant_resource_policy_version_conflict')
    values=body.model_dump(exclude={'expected_version'})
    if row:
        for key,value in values.items():setattr(row,key,value)
        row.version+=1;row.updated_by=who.id;row.updated_at=now()
    else:db.add(TenantResourcePolicy(workspace_id=wid,version=1,updated_by=who.id,**values))
    await db.flush();result=await snapshot(db,wid);await db.commit();return result


class ReadLimits(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0,strict=True)
    daily_read_jobs:int=Field(ge=1,le=10000,strict=True)
    queued_read_jobs:int=Field(ge=1,le=100,strict=True)
    concurrent_reads:int=Field(ge=1,le=8,strict=True)


async def read_snapshot(db,wid):
    return {'workspace_id':wid,'read_policy':await read_resources.policy(db,wid),
        'host_ceilings':read_resources.CEILINGS,'usage':await read_resources.usage(db,wid),
        'coverage':['native_mcp_calls','meta_sync_jobs','google_ads_sync_jobs'],
        'pending_coverage':['global_host_scheduling'],
        'accounting':'PAO_admitted_jobs_not_provider_HTTP_operations',
        'provider_remaining_quota':None,'grants_authorized':False}


@router.get('/reads')
async def read_reads(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await manager(db,wid,who);await read_resources.lock(db,wid);await authorize(db,wid,who)
    return await read_snapshot(db,wid)


@router.put('/reads')
async def write_reads(workspace_id:UUID,body:ReadLimits,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await manager(db,wid,who);await read_resources.lock(db,wid);await authorize(db,wid,who)
    row=await db.get(TenantReadPolicy,wid,populate_existing=True)
    if (row.version if row else 0)!=body.expected_version:raise HTTPException(409,'tenant_read_policy_version_conflict')
    values=body.model_dump(exclude={'expected_version'})
    if row:
        for key,value in values.items():setattr(row,key,value)
        row.version+=1;row.updated_by=who.id;row.updated_at=now()
    else:db.add(TenantReadPolicy(workspace_id=wid,version=1,updated_by=who.id,**values))
    await db.flush();result=await read_snapshot(db,wid);await db.commit();return result


class MetadataLimits(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_version:int=Field(ge=0,strict=True)
    daily_metadata_requests:int=Field(ge=1,le=1000,strict=True)
    concurrent_metadata:int=Field(ge=1,le=8,strict=True)


async def metadata_snapshot(db,wid):
    return {'workspace_id':wid,'metadata_policy':await metadata_resources.policy(db,wid),
        'host_ceilings':metadata_resources.CEILINGS,'usage':await metadata_resources.usage(db,wid),
        'accounting':'PAO_metadata_admissions_not_provider_HTTP_or_billing',
        'coverage':['native_model_connect','native_model_catalogue','native_model_selection','native_mcp_discovery','local_model_catalogue','local_model_selection'],
        'pending_coverage':['global_host_scheduling'],
        'grants_authorized':False}


@router.get('/metadata')
async def read_metadata(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await manager(db,wid,who);await metadata_resources.lock(db,wid);await authorize(db,wid,who)
    return await metadata_snapshot(db,wid)


@router.put('/metadata')
async def write_metadata(workspace_id:UUID,body:MetadataLimits,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';wid=str(workspace_id)
    await manager(db,wid,who);await metadata_resources.lock(db,wid);await authorize(db,wid,who)
    row=await db.get(TenantMetadataPolicy,wid,populate_existing=True)
    if (row.version if row else 0)!=body.expected_version:raise HTTPException(409,'tenant_metadata_policy_version_conflict')
    values=body.model_dump(exclude={'expected_version'})
    if row:
        for key,value in values.items():setattr(row,key,value)
        row.version+=1;row.updated_by=who.id;row.updated_at=now()
    else:db.add(TenantMetadataPolicy(workspace_id=wid,version=1,updated_by=who.id,**values))
    await db.flush();result=await metadata_snapshot(db,wid);await db.commit();return result
