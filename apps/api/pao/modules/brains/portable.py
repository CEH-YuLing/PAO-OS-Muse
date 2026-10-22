"""Bounded snapshot ZIP. Never extract paths or execute imported content."""
import hashlib,io,json,re,stat,zipfile,struct
from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from sqlalchemy import select,func,delete
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal
from ...db import database
from ...models import BrainFile,BrainNote,BrainNoteVersion,BrainImportPlan,User,now
from .access import require_brain
from .api import clean_name
from .files import add_file,checked_content,read_upload,validate_name,validate_bytes,quota
from .notes import add_note,detail

MAX_ARCHIVE=12_582_912
MAX_EXPANDED=10_485_760
MAX_ENTRIES=2001
FORMAT='pao-brain-snapshot-v1'
router=APIRouter(prefix='/v1/brains',tags=['brain-portable'])
class BrainImportConfirm(BaseModel):
    model_config=ConfigDict(extra='forbid')
    sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    brain_revision:int=Field(ge=1)
    confirmed:Literal[True]

def strict_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result

def read_archive(raw):
    if len(raw)>MAX_ARCHIVE:raise HTTPException(413,'ZIP quá lớn')
    try:
        if not raw.startswith(b'PK\x03\x04'):raise ValueError('Not a snapshot ZIP')
        end=raw.rfind(b'PK\x05\x06')
        if end<0 or len(raw)-end<22:raise ValueError('Missing ZIP directory')
        _,disk,start_disk,on_disk,count,central_size,central_offset,comment_size=struct.unpack_from('<4s4H2IH',raw,end)
        if disk or start_disk or count!=on_disk or count>MAX_ENTRIES or count==65535 or end+22+comment_size!=len(raw):raise ValueError('Directory bounds')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries=archive.infolist();names=[entry.filename for entry in entries]
            if len(entries)>MAX_ENTRIES or len(names)!=len(set(names)) or 'manifest.json' not in names:
                raise ValueError('Invalid entry set')
            total=0
            for entry in entries:
                if entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16) or entry.flag_bits&1 or entry.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
                    raise ValueError('Unsafe entry')
                if entry.filename!='manifest.json' and not re.fullmatch(r'(files|notes)/[0-9a-f-]{36}\.(txt|md)',entry.filename):
                    raise ValueError('Unsafe path')
                if entry.file_size>1_048_576 or entry.file_size>100*max(1,entry.compress_size):
                    raise ValueError('Expansion limit')
                total+=entry.file_size
            if total>MAX_EXPANDED+524288:raise ValueError('Total expansion limit')
            manifest_info=archive.getinfo('manifest.json')
            if manifest_info.file_size>524288:raise ValueError('Manifest limit')
            manifest=json.loads(archive.read('manifest.json').decode('utf-8'),object_pairs_hook=strict_object)
            if set(manifest)!={'format','name','items'} or manifest['format']!=FORMAT or not isinstance(manifest['name'],str) or len(manifest['name'])>120:
                raise ValueError('Invalid manifest')
            items=manifest['items']
            if not isinstance(items,list) or len(items)>MAX_ENTRIES-1:raise ValueError('Item limit')
            expected={'manifest.json'};values=[];content_total=0
            for item in items:
                if not isinstance(item,dict) or item.get('kind') not in ('file','note'):raise ValueError('Invalid item')
                kind=item['kind'];label='name' if kind=='file' else 'title'
                if set(item)!={'kind','path',label,'mime','size','sha256'}:raise ValueError('Unknown fields')
                path=item['path']
                if not isinstance(path,str) or path not in names or path in expected:raise ValueError('Path mismatch')
                folder,filename=path.split('/')
                if folder!=('files' if kind=='file' else 'notes') or str(UUID(filename.rsplit('.',1)[0]))!=filename.rsplit('.',1)[0]:raise ValueError('Invalid identity path')
                if not isinstance(item[label],str):raise ValueError('Invalid label')
                if kind=='file':validate_name(item[label],item['mime'])
                elif item['mime']!='text/markdown' or not path.endswith('.md') or len(item[label])>120:raise ValueError('Invalid note')
                else:clean_name(item[label])
                content=archive.read(path);validate_bytes(content)
                if kind=='note' and len(content)>262144:raise ValueError('Note limit')
                if type(item['size']) is not int or item['size']!=len(content) or item['sha256']!=hashlib.sha256(content).hexdigest():raise ValueError('Hash/size mismatch')
                if kind=='file' and not path.endswith('.'+item[label].rsplit('.',1)[-1].lower()):raise ValueError('Extension mismatch')
                content_total+=len(content);expected.add(path);values.append((item,content))
            if set(names)!=expected or content_total>MAX_EXPANDED:raise ValueError('Unlisted entries')
            return values
    except HTTPException:raise
    except (ValueError,KeyError,TypeError,UnicodeError,zipfile.BadZipFile,RuntimeError,NotImplementedError,OverflowError,struct.error):
        raise HTTPException(422,'ZIP/manifest không an toàn hoặc sai hash; không import')

async def export_bytes(db,brain):
    output=io.BytesIO();manifest={'format':FORMAT,'name':brain.name,'items':[]}
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:
        rows=list(await db.scalars(select(BrainFile).where(BrainFile.brain_id==brain.id,BrainFile.trashed_at.is_(None)).order_by(BrainFile.id)))
        for row in rows:
            content=checked_content(row);path=f"files/{row.id}."+row.name.rsplit('.',1)[-1].lower()
            archive.writestr(path,content);manifest['items'].append({'kind':'file','path':path,'name':row.name,'mime':row.mime,'size':len(content),'sha256':row.sha256})
        for row in await db.scalars(select(BrainNote).where(BrainNote.brain_id==brain.id,BrainNote.trashed_at.is_(None)).order_by(BrainNote.id)):
            value=await detail(db,row);content=value['content'].encode();path=f'notes/{row.id}.md'
            archive.writestr(path,content);manifest['items'].append({'kind':'note','path':path,'title':row.title,'mime':'text/markdown','size':len(content),'sha256':value['sha256']})
        archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,separators=(',',':')).encode())
    raw=output.getvalue();read_archive(raw) # Export must satisfy the same import limits.
    return raw

async def diff(db,brain,values):
    known_files={(row.name,row.mime,row.sha256) for row in await db.scalars(select(BrainFile).where(BrainFile.brain_id==brain.id,BrainFile.trashed_at.is_(None)))}
    known_notes=set()
    for row,version in await db.execute(select(BrainNote,BrainNoteVersion).join(BrainNoteVersion,(BrainNoteVersion.note_id==BrainNote.id)&(BrainNoteVersion.version==BrainNote.content_version)).where(BrainNote.brain_id==brain.id,BrainNote.trashed_at.is_(None))):
        known_notes.add((row.title,version.sha256))
    changes=[];skipped=[]
    for item,content in values:
        if item['kind']=='file':
            key=(item['name'],item['mime'],item['sha256']);known=known_files
        else:key=(item['title'],item['sha256']);known=known_notes
        if key in known:skipped.append(item['path'])
        else:changes.append((item,content));known.add(key)
    return changes,skipped

@router.get('/{brain_id}/export')
async def export(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,allow_archived=True,lock=True)
    raw=await export_bytes(db,brain)
    return Response(raw,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="brain-snapshot.zip"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Archive-SHA256':hashlib.sha256(raw).hexdigest()})

@router.post('/{brain_id}/imports/preview')
async def preview(brain_id:UUID,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await require_brain(db,who,brain_id,True)
    if request.headers.get('content-type','').split(';')[0]!='application/zip':raise HTTPException(415,'Cần ZIP snapshot')
    await db.rollback();raw=await read_upload(request,MAX_ARCHIVE);values=read_archive(raw)
    await db.execute(select(User.id).where(User.id==who.id).with_for_update())
    await db.execute(delete(BrainImportPlan).where(BrainImportPlan.actor_id==who.id,BrainImportPlan.expires_at<now()))
    if await db.scalar(select(func.count()).select_from(BrainImportPlan).where(BrainImportPlan.actor_id==who.id,BrainImportPlan.consumed_at.is_(None)))>=3:
        raise HTTPException(409,'Đã có 3 dry-run chưa xác nhận; chờ hết hạn10phút')
    brain=await require_brain(db,who,brain_id,True,lock=True);changes,skipped=await diff(db,brain,values)
    await quota(db,brain.id,sum(len(content) for _,content in changes),sum(item['kind']=='file' for item,_ in changes))
    note_count=await db.scalar(select(func.count()).select_from(BrainNote).where(BrainNote.brain_id==brain.id))
    if note_count+sum(item['kind']=='note' for item,_ in changes)>1000:raise HTTPException(409,'Notes vượt giới hạn')
    plan=BrainImportPlan(brain_id=brain.id,workspace_id=brain.workspace_id,actor_id=who.id,brain_revision=brain.revision,
        archive=raw,sha256=hashlib.sha256(raw).hexdigest(),expires_at=now()+timedelta(minutes=10))
    db.add(plan);await db.commit()
    return {'plan_id':plan.id,'sha256':plan.sha256,'brain_revision':plan.brain_revision,'expires_at':plan.expires_at,
        'add':[item for item,_ in changes],'skip':skipped,'overwrite':False,'confirmation_required':True}

@router.post('/{brain_id}/imports/{plan_id}/confirm')
async def confirm(brain_id:UUID,plan_id:UUID,body:BrainImportConfirm,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await require_brain(db,who,brain_id,True,lock=True)
    plan=await db.scalar(select(BrainImportPlan).where(BrainImportPlan.id==str(plan_id),BrainImportPlan.brain_id==brain.id,BrainImportPlan.actor_id==who.id).with_for_update())
    if not plan:raise HTTPException(404,'Không tìm thấy dry-run của người dùng')
    if plan.consumed_at or plan.expires_at<=now():raise HTTPException(409,'Dry-run đã dùng hoặc hết hạn')
    if body.sha256!=plan.sha256 or body.sha256!=hashlib.sha256(plan.archive).hexdigest() or body.brain_revision!=plan.brain_revision or brain.revision!=plan.brain_revision:
        raise HTTPException(409,'Brain/ZIP đã đổi; chạy lại dry-run')
    changes,skipped=await diff(db,brain,read_archive(plan.archive));files=[];notes=[]
    for item,content in changes:
        if item['kind']=='file':files.append((await add_file(db,brain,who,item['name'],item['mime'],content)).id)
        else:notes.append((await add_note(db,brain,who,item['title'],content.decode('utf-8'))).id)
    plan.consumed_at=now();await db.commit()
    return {'files':files,'notes':notes,'skipped':len(skipped),'revision':brain.revision,'overwrite':False}
