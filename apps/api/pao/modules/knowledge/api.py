import hashlib
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Path,Query,Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal
from ...db import database
from ...models import KnowledgeSource,KnowledgeVersion,KnowledgeIngestion,now
from ..brains.access import require_brain
from ...config import settings
from . import service
from .schemas import KnowledgeSourceInput,KnowledgeSourcePatch,KnowledgeSourceOut,SourceVersionOut,IngestionOut,SourcePreview

router=APIRouter(prefix='/v1/brains',tags=['knowledge-sources'])

@router.get('/{brain_id}/sources/status')
async def status(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await require_brain(db,who,brain_id,allow_archived=True)
    return {'enabled':settings().knowledge_sources_enabled,'parser_version':service.PARSER_VERSION,
        'supported':['text/plain','text/markdown'],'rag_enabled':settings().knowledge_enabled,
        'embedding_enabled':settings().knowledge_enabled and settings().knowledge_embeddings_enabled}

@router.get('/{brain_id}/sources',response_model=list[KnowledgeSourceOut])
async def list_sources(brain_id:UUID,archived:bool=False,limit:int=Query(default=100,ge=1,le=100),offset:int=Query(default=0,ge=0,le=1000),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await service.access(db,who,brain_id)
    query=select(KnowledgeSource).where(KnowledgeSource.brain_id==brain.id)
    if not archived:query=query.where(KnowledgeSource.archived_at.is_(None))
    rows=await db.scalars(query.order_by(KnowledgeSource.created_at,KnowledgeSource.id).offset(offset).limit(limit))
    return [await service.describe(db,row) for row in rows]

@router.post('/{brain_id}/sources',response_model=KnowledgeSourceOut)
async def create_source(brain_id:UUID,body:KnowledgeSourceInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await service.access(db,who,brain_id,True,True)
    source,_,_=await service.capture(db,brain,who,body.kind,body.origin_id)
    await db.commit();return await service.describe(db,source)

@router.post('/{brain_id}/sources/{source_id}/refresh',response_model=KnowledgeSourceOut)
async def refresh_source(brain_id:UUID,source_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,source=await service.source_row(db,who,brain_id,source_id,True,True)
    source,_,_=await service.capture(db,brain,who,service.source_kind(source),service.origin_id(source))
    await db.commit();return await service.describe(db,source)

@router.patch('/{brain_id}/sources/{source_id}',response_model=KnowledgeSourceOut)
async def archive_source(brain_id:UUID,source_id:UUID,body:KnowledgeSourcePatch,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,source=await service.source_row(db,who,brain_id,source_id,True,True)
    if source.revision!=body.revision:raise HTTPException(409,'Source đã thay đổi')
    source.archived_at=now() if body.archived else None;source.revision+=1
    await db.commit();return await service.describe(db,source)

@router.get('/{brain_id}/sources/{source_id}/versions',response_model=list[SourceVersionOut])
async def versions(brain_id:UUID,source_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,source=await service.source_row(db,who,brain_id,source_id)
    return list(await db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.source_id==source.id).order_by(KnowledgeVersion.number).limit(service.MAX_VERSIONS)))

@router.get('/{brain_id}/sources/{source_id}/versions/{version}',response_model=SourceVersionOut)
async def get_version(brain_id:UUID,source_id:UUID,version:int=Path(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,source=await service.source_row(db,who,brain_id,source_id)
    return await service.version_row(db,source,version)

@router.get('/{brain_id}/sources/{source_id}/versions/{version}/preview',response_model=SourcePreview)
async def preview(brain_id:UUID,source_id:UUID,response:Response,version:int=Path(ge=1),start_line:int=Query(default=1,ge=1),
                  lines:int=Query(default=100,ge=1,le=200),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,source=await service.source_row(db,who,brain_id,source_id)
    if source.archived_at:raise HTTPException(409,'Source đã archive')
    value=await service.version_row(db,source,version)
    await service.raw_version(db,source,value) # current trash/ACL and original hash; old version remains valid
    job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.version_id==value.id,KnowledgeIngestion.parser_version==service.PARSER_VERSION))
    if not job or job.status!='completed':raise HTTPException(409,'Source chưa parse thành công')
    if hashlib.sha256(job.parsed_text.encode('utf-8')).hexdigest()!=job.parsed_sha256:raise HTTPException(409,'Parsed text hash không khớp')
    values=job.parsed_text.split('\n')
    if start_line>len(values):raise HTTPException(416,'Line ngoài source')
    selected=[];size=0;truncated=False
    for line in values[start_line-1:start_line-1+lines]:
        extra=len(line.encode('utf-8'))+(1 if selected else 0)
        if size+extra>16384:
            truncated=True;break
        selected.append(line);size+=extra
    if not selected:raise HTTPException(413,'Line vượt preview16KiB; đọc origin bằng file service')
    response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
    return SourcePreview(source_id=source.id,version_id=value.id,version=value.number,source_sha256=value.source_sha256,
        parsed_sha256=job.parsed_sha256,parser_version=job.parser_version,start_line=start_line,
        end_line=start_line+len(selected)-1,content='\n'.join(selected),truncated=truncated or start_line+len(selected)-1<len(values))

@router.get('/{brain_id}/ingestion-jobs',response_model=list[IngestionOut])
async def jobs(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await service.access(db,who,brain_id)
    return list(await db.scalars(select(KnowledgeIngestion).where(KnowledgeIngestion.brain_id==brain.id).order_by(
        KnowledgeIngestion.created_at.desc(),KnowledgeIngestion.id).limit(100)))

async def job_row(db,who,brain_id,job_id,write=False):
    await service.access(db,who,brain_id,write,write)
    query=select(KnowledgeIngestion).where(KnowledgeIngestion.id==str(job_id),KnowledgeIngestion.brain_id==str(brain_id))
    if write:query=query.with_for_update().execution_options(populate_existing=True)
    job=await db.scalar(query)
    if not job:raise HTTPException(404,'Không tìm thấy ingestion job')
    return job

@router.get('/{brain_id}/ingestion-jobs/{job_id}',response_model=IngestionOut)
async def get_job(brain_id:UUID,job_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await job_row(db,who,brain_id,job_id)

@router.post('/{brain_id}/ingestion-jobs/{job_id}/retry',response_model=IngestionOut)
async def retry(brain_id:UUID,job_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    job=await job_row(db,who,brain_id,job_id,True)
    if job.status=='completed':return job
    if job.status!='failed' or job.attempts>=3:raise HTTPException(409,'Job chưa failed hoặc hết3attempts')
    value=await db.get(KnowledgeVersion,job.version_id);source=await db.get(KnowledgeSource,value.source_id)
    if source.archived_at:raise HTTPException(409,'Source archived')
    await service.raw_version(db,source,value)
    job.actor_id=who.id;job.status='queued';job.error_code=None;job.claim_id=None;job.locked_at=None;job.updated_at=now()
    await db.commit();return job
