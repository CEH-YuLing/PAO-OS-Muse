"""No user-controlled filesystem paths. Source bytes and metadata commit together."""
import asyncio,hashlib,re,unicodedata
from urllib.parse import quote
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal
from ...db import database
from ...models import BrainFile,BrainNote,BrainNoteVersion,now
from .access import require_brain

MAX_FILE_BYTES=1_048_576
BRAIN_QUOTA_BYTES=10_485_760
MAX_ITEMS=1000
router=APIRouter(prefix='/v1/brains',tags=['brain-files'])

class BrainFileOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str
    brain_id:str
    name:str
    mime:str
    size:int
    sha256:str
    revision:int
    trashed_at:datetime|None
    created_at:datetime

def validate_name(name,mime):
    value=unicodedata.normalize('NFKC',name)
    if value!=name or not value or len(value)>160 or value!=value.strip() or value.endswith('.') or any(unicodedata.category(c).startswith('C') for c in value) or re.search(r'[\\/:<>"|?*\x00-\x1f\x7f]',value):
        raise HTTPException(422,'Tên file không an toàn')
    if value.split('.')[0].rstrip(' .').upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))}:
        raise HTTPException(422,'Tên file dành riêng cho hệ thống')
    extension=value.rsplit('.',1)[-1].lower() if '.' in value else ''
    if (mime,extension) not in {('text/plain','txt'),('text/markdown','md')}:
        raise HTTPException(415,'Chỉ hỗ trợ UTF-8 .txt và .md với MIME tương ứng')
    return value

def validate_bytes(content):
    if len(content)>MAX_FILE_BYTES:
        raise HTTPException(413,'File vượt giới hạn 1MiB')
    try:
        value=content.decode('utf-8-sig')
    except UnicodeError:
        raise HTTPException(415,'File không phải UTF-8 text')
    if any(unicodedata.category(c)=='Cc' and c not in '\t\r\n' for c in value):
        raise HTTPException(415,'File chứa dữ liệu binary/control không hỗ trợ')
    return value

async def read_upload(request,limit=MAX_FILE_BYTES):
    declared=request.headers.get('content-length')
    if declared:
        try:
            if int(declared)<0:raise ValueError()
        except ValueError:
            raise HTTPException(422,'Content-Length không hợp lệ')
        if int(declared)>limit:
            raise HTTPException(413,'Upload vượt giới hạn')
    chunks=[]; total=0
    try:
        async with asyncio.timeout(30):
            async for chunk in request.stream():
                total+=len(chunk)
                if total>limit:raise HTTPException(413,'Upload vượt giới hạn')
                chunks.append(chunk)
    except TimeoutError:
        raise HTTPException(408,'Upload quá thời gian')
    return b''.join(chunks)

async def storage_used(db,brain_id):
    file_bytes=await db.scalar(select(func.coalesce(func.sum(BrainFile.size),0)).where(BrainFile.brain_id==brain_id))
    note_bytes=await db.scalar(select(func.coalesce(func.sum(BrainNoteVersion.size),0)).join(BrainNote,BrainNote.id==BrainNoteVersion.note_id).where(BrainNote.brain_id==brain_id))
    return file_bytes+note_bytes

async def quota(db,brain_id,extra,count=1):
    if await storage_used(db,brain_id)+extra>BRAIN_QUOTA_BYTES:
        raise HTTPException(409,'Brain vượt quota 10MiB; trash vẫn chiếm quota')
    if await db.scalar(select(func.count()).select_from(BrainFile).where(BrainFile.brain_id==brain_id))+count>MAX_ITEMS:
        raise HTTPException(409,'Brain vượt giới hạn file')

async def add_file(db,brain,who,name,mime,content):
    validate_name(name,mime);validate_bytes(content)
    await quota(db,brain.id,len(content))
    row=BrainFile(brain_id=brain.id,workspace_id=brain.workspace_id,created_by=who.id,
        name=name,mime=mime,size=len(content),sha256=hashlib.sha256(content).hexdigest(),content=content)
    db.add(row);brain.revision+=1;await db.flush();return row

async def file_row(db,who,brain_id,file_id,write=False):
    brain=await require_brain(db,who,brain_id,write,allow_archived=not write,lock=write)
    row=await db.scalar(select(BrainFile).where(BrainFile.id==str(file_id),BrainFile.brain_id==brain.id))
    if not row:raise HTTPException(404,'Không tìm thấy file')
    return brain,row

def checked_content(row):
    if row.trashed_at:raise HTTPException(409,'File đang ở trash; phục hồi trước khi đọc')
    if row.sha256!=hashlib.sha256(row.content).hexdigest() or row.size!=len(row.content):
        raise HTTPException(409,'File không qua kiểm tra toàn vẹn')
    validate_bytes(row.content)
    return row.content

@router.get('/{brain_id}/files',response_model=list[BrainFileOut])
async def list_files(brain_id:UUID,trash:bool=False,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,allow_archived=True)
    query=select(BrainFile).where(BrainFile.brain_id==brain.id)
    if not trash:query=query.where(BrainFile.trashed_at.is_(None))
    return list(await db.scalars(query.order_by(BrainFile.created_at,BrainFile.id).limit(MAX_ITEMS)))

@router.post('/{brain_id}/files',response_model=BrainFileOut,status_code=201)
async def upload(brain_id:UUID,request:Request,name:str=Query(min_length=1,max_length=160),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await require_brain(db,who,brain_id,True)
    mime=request.headers.get('content-type','').split(';')[0].strip().lower()
    validate_name(name,mime)
    await db.rollback() # No DB connection held through a streaming upload.
    content=await read_upload(request);validate_bytes(content)
    brain=await require_brain(db,who,brain_id,True,lock=True)
    row=await add_file(db,brain,who,name,mime,content)
    await db.commit();return row

@router.get('/{brain_id}/files/{file_id}/download')
async def download(brain_id:UUID,file_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await file_row(db,who,brain_id,file_id)
    return Response(checked_content(row),media_type='text/plain; charset=utf-8',headers={
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.name,safe=''),
        'X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox",
        'Cache-Control':'no-store','ETag':'"'+row.sha256+'"'})

@router.get('/{brain_id}/files/{file_id}/preview')
async def preview(brain_id:UUID,file_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await file_row(db,who,brain_id,file_id)
    return {'format':'plain_text','content':checked_content(row).decode('utf-8-sig'),'sha256':row.sha256}

async def trash_file(db,brain,row,revision,trashed):
    if row.revision!=revision:raise HTTPException(409,'File đã thay đổi')
    row.trashed_at=now() if trashed else None;row.revision+=1;brain.revision+=1
    await db.commit();return row

@router.delete('/{brain_id}/files/{file_id}',response_model=BrainFileOut)
async def trash(brain_id:UUID,file_id:UUID,revision:int=Query(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,row=await file_row(db,who,brain_id,file_id,True)
    return await trash_file(db,brain,row,revision,True)

@router.post('/{brain_id}/files/{file_id}/restore',response_model=BrainFileOut)
async def restore(brain_id:UUID,file_id:UUID,revision:int=Query(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,row=await file_row(db,who,brain_id,file_id,True)
    return await trash_file(db,brain,row,revision,False)
