"""Immutable origin references, current ACL and bounded, non-executable text parsing."""
import hashlib
from fastapi import HTTPException
from sqlalchemy import select,func
from ...config import settings
from ...models import BrainFile,BrainNote,BrainNoteVersion,KnowledgeSource,KnowledgeVersion,KnowledgeIngestion,now
from ..brains.access import require_brain
from ..brains.files import checked_content,validate_bytes,validate_name
from .schemas import KnowledgeSourceOut

PARSER_VERSION='utf8-lines-v1'
MAX_SOURCES=1000
MAX_VERSIONS=100

def enabled():
    if not settings().knowledge_sources_enabled:
        raise HTTPException(503,'Sources chưa được bật')

async def access(db,who,brain_id,write=False,lock=False):
    enabled()
    return await require_brain(db,who,brain_id,write,allow_archived=not write,lock=lock)

async def origin(db,brain_id,kind,origin_id,version=None):
    model=BrainFile if kind=='file' else BrainNote
    row=await db.scalar(select(model).where(model.id==str(origin_id),model.brain_id==brain_id).execution_options(populate_existing=True))
    if not row:raise HTTPException(404,'Không tìm thấy origin trong Brain')
    if row.trashed_at:raise HTTPException(409,'Origin đang ở trash')
    if kind=='file':
        validate_name(row.name,row.mime)
        return row.name,1,checked_content(row),row.sha256
    number=version if version is not None else row.content_version
    value=await db.get(BrainNoteVersion,(row.id,number))
    if not value:raise HTTPException(404,'Không tìm thấy origin version')
    raw=value.content.encode('utf-8')
    if len(raw)!=value.size or hashlib.sha256(raw).hexdigest()!=value.sha256:
        raise HTTPException(409,'Origin không qua kiểm tra toàn vẹn')
    validate_bytes(raw)
    return row.title,number,raw,value.sha256

async def source_row(db,who,brain_id,source_id,write=False,lock=False):
    brain=await access(db,who,brain_id,write,lock)
    row=await db.scalar(select(KnowledgeSource).where(KnowledgeSource.id==str(source_id),KnowledgeSource.brain_id==brain.id).execution_options(populate_existing=True))
    if not row:raise HTTPException(404,'Không tìm thấy source')
    return brain,row

def source_kind(row):return 'file' if row.file_id else 'note'
def origin_id(row):return row.file_id or row.note_id

async def capture(db,brain,who,kind,oid):
    title,number,raw,sha=await origin(db,brain.id,kind,oid)
    column=KnowledgeSource.file_id if kind=='file' else KnowledgeSource.note_id
    row=await db.scalar(select(KnowledgeSource).where(KnowledgeSource.brain_id==brain.id,column==str(oid)))
    if row and row.archived_at:raise HTTPException(409,'Source đã archive; phục hồi trước')
    if not row:
        if await db.scalar(select(func.count()).select_from(KnowledgeSource).where(KnowledgeSource.brain_id==brain.id))>=MAX_SOURCES:
            raise HTTPException(409,'Brain đạt giới hạn1000sources')
        row=KnowledgeSource(brain_id=brain.id,workspace_id=brain.workspace_id,created_by=who.id,title=title,
            file_id=str(oid) if kind=='file' else None,note_id=str(oid) if kind=='note' else None)
        db.add(row);await db.flush()
    value=await db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.source_id==row.id,KnowledgeVersion.source_sha256==sha))
    if not value:
        count=await db.scalar(select(func.count()).select_from(KnowledgeVersion).where(KnowledgeVersion.source_id==row.id))
        if count>=MAX_VERSIONS:raise HTTPException(409,'Source đạt giới hạn100versions')
        value=KnowledgeVersion(source_id=row.id,brain_id=brain.id,workspace_id=brain.workspace_id,
            number=count+1,origin_version=number,source_sha256=sha,source_size=len(raw),title=title,created_by=who.id)
        db.add(value);await db.flush()
    if row.current_version!=value.number or row.title!=title:
        row.current_version=value.number;row.title=title;row.revision+=1
    job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.version_id==value.id,KnowledgeIngestion.parser_version==PARSER_VERSION))
    if not job:
        job=KnowledgeIngestion(version_id=value.id,brain_id=brain.id,workspace_id=brain.workspace_id,
            actor_id=who.id,parser_version=PARSER_VERSION)
        db.add(job);await db.flush()
    return row,value,job

async def describe(db,row):
    value=await db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.source_id==row.id,KnowledgeVersion.number==row.current_version))
    job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.version_id==value.id,KnowledgeIngestion.parser_version==PARSER_VERSION))
    model=BrainFile if row.file_id else BrainNote
    current=await db.get(model,origin_id(row))
    trashed=not current or bool(current.trashed_at)
    if current and row.note_id:
        current_value=await db.get(BrainNoteVersion,(current.id,current.content_version))
        sha=current_value.sha256 if current_value else None
    else:sha=current.sha256 if current else None
    return KnowledgeSourceOut(id=row.id,brain_id=row.brain_id,kind=source_kind(row),origin_id=origin_id(row),title=row.title,
        current_version=row.current_version,revision=row.revision,archived_at=row.archived_at,
        stale=sha!=value.source_sha256,origin_trashed=trashed,version_id=value.id,source_sha256=value.source_sha256,
        parser_version=job.parser_version,job_id=job.id,parse_status=job.status)

def parse_text(raw):
    # No Markdown/HTML execution, URL fetch, shell or model calls.
    value=validate_bytes(raw).replace('\r\n','\n').replace('\r','\n')
    return value,hashlib.sha256(value.encode('utf-8')).hexdigest(),value.count('\n')+1

async def version_row(db,source,number):
    value=await db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.source_id==source.id,KnowledgeVersion.number==number))
    if not value:raise HTTPException(404,'Không tìm thấy source version')
    return value

async def raw_version(db,source,value):
    _,_,raw,sha=await origin(db,source.brain_id,source_kind(source),origin_id(source),value.origin_version)
    if sha!=value.source_sha256 or len(raw)!=value.source_size:
        raise HTTPException(409,'Source hash không khớp origin')
    return raw
