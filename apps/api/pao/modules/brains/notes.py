import hashlib
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter,Depends,Header,HTTPException,Response,Path
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal
from ...db import database
from ...models import BrainNote,BrainNoteVersion,now
from .access import require_brain
from .api import clean_name
from .files import quota,validate_bytes

router=APIRouter(prefix='/v1/brains',tags=['brain-notes'])
class BrainNoteInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=120)
    content:str=Field(max_length=65536)
class BrainNoteOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str
    brain_id:str
    title:str
    revision:int
    content_version:int
    trashed_at:datetime|None
    created_at:datetime
class BrainNoteDetail(BrainNoteOut):
    content:str
    sha256:str

def etag(row):return f'"note-{row.id}-r{row.revision}"'
def match(row,value):
    if value is None:raise HTTPException(428,'Cần If-Match ETag từ bản đang đọc')
    if value!=etag(row):raise HTTPException(412,'Note đã thay đổi; tải lại, không tự ghi đè')
async def note_row(db,who,brain_id,note_id,write=False):
    brain=await require_brain(db,who,brain_id,write,allow_archived=not write,lock=write)
    row=await db.scalar(select(BrainNote).where(BrainNote.id==str(note_id),BrainNote.brain_id==brain.id))
    if not row:raise HTTPException(404,'Không tìm thấy note')
    return brain,row
async def detail(db,row,version=None):
    value=await db.get(BrainNoteVersion,(row.id,version if version is not None else row.content_version))
    if not value:raise HTTPException(404,'Không tìm thấy note version')
    if value.sha256!=hashlib.sha256(value.content.encode()).hexdigest():raise HTTPException(409,'Note không qua kiểm tra toàn vẹn')
    return {**BrainNoteOut.model_validate(row).model_dump(),'content':value.content,'sha256':value.sha256}
async def add_version(db,row,who,content):
    try:raw=content.encode('utf-8')
    except UnicodeError:raise HTTPException(422,'Nội dung Unicode không hợp lệ')
    validate_bytes(raw)
    if len(raw)>262144:raise HTTPException(413,'Note vượt giới hạn')
    await quota(db,row.brain_id,len(raw),count=0)
    value=BrainNoteVersion(note_id=row.id,version=row.content_version,created_by=who.id,
        content=content,sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
    db.add(value);await db.flush()
async def add_note(db,brain,who,title,content):
    if await db.scalar(select(func.count()).select_from(BrainNote).where(BrainNote.brain_id==brain.id))>=1000:
        raise HTTPException(409,'Brain đạt giới hạn notes')
    row=BrainNote(brain_id=brain.id,workspace_id=brain.workspace_id,title=clean_name(title))
    db.add(row);await db.flush();await add_version(db,row,who,content)
    brain.revision+=1;return row

@router.get('/{brain_id}/notes',response_model=list[BrainNoteOut])
async def list_notes(brain_id:UUID,trash:bool=False,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,allow_archived=True)
    query=select(BrainNote).where(BrainNote.brain_id==brain.id)
    if not trash:query=query.where(BrainNote.trashed_at.is_(None))
    return list(await db.scalars(query.order_by(BrainNote.created_at,BrainNote.id).limit(1000)))
@router.post('/{brain_id}/notes',response_model=BrainNoteDetail,status_code=201)
async def create_note(brain_id:UUID,body:BrainNoteInput,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,True,lock=True)
    row=await add_note(db,brain,who,body.title,body.content)
    value=await detail(db,row);response.headers['ETag']=etag(row)
    await db.commit();return value
@router.get('/{brain_id}/notes/{note_id}',response_model=BrainNoteDetail)
async def get_note(brain_id:UUID,note_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await note_row(db,who,brain_id,note_id)
    response.headers['ETag']=etag(row);response.headers['Cache-Control']='no-store'
    return await detail(db,row)
@router.patch('/{brain_id}/notes/{note_id}',response_model=BrainNoteDetail)
async def edit_note(brain_id:UUID,note_id:UUID,body:BrainNoteInput,response:Response,if_match:str|None=Header(default=None,alias='If-Match'),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,row=await note_row(db,who,brain_id,note_id,True);match(row,if_match)
    if row.trashed_at:raise HTTPException(409,'Note ở trash')
    row.title=clean_name(body.title);row.revision+=1;row.content_version+=1
    await add_version(db,row,who,body.content);brain.revision+=1
    value=await detail(db,row);response.headers['ETag']=etag(row)
    await db.commit();return value
async def trash_note(db,brain,row,value,trashed):
    match(row,value);row.trashed_at=now() if trashed else None;row.revision+=1;brain.revision+=1
    await db.commit();return row
@router.delete('/{brain_id}/notes/{note_id}',response_model=BrainNoteOut)
async def trash(brain_id:UUID,note_id:UUID,if_match:str|None=Header(default=None,alias='If-Match'),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,row=await note_row(db,who,brain_id,note_id,True);return await trash_note(db,brain,row,if_match,True)
@router.post('/{brain_id}/notes/{note_id}/restore',response_model=BrainNoteOut)
async def restore(brain_id:UUID,note_id:UUID,if_match:str|None=Header(default=None,alias='If-Match'),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,row=await note_row(db,who,brain_id,note_id,True);return await trash_note(db,brain,row,if_match,False)
@router.get('/{brain_id}/notes/{note_id}/versions/{version}')
async def version(brain_id:UUID,note_id:UUID,version:int=Path(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await note_row(db,who,brain_id,note_id)
    return {**await detail(db,row,version),'requested_version':version}
