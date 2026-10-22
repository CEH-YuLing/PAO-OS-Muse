import difflib,hashlib,json,re
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from pydantic import BaseModel,ConfigDict,Field,field_validator
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal,principal,rate_limit
from ...db import database
from ...models import KnowledgeSource,KnowledgeVersion,KnowledgeChunk,KnowledgeIndexJob,KnowledgeWiki,KnowledgeWikiVersion,KnowledgeWikiEvent,BrainNote,BrainNoteVersion,now
from ..brains.api import clean_name
from ..brains.files import validate_bytes
from . import service,index,retrieval

router=APIRouter(prefix='/v1/brains',tags=['knowledge-workspace'])
class KnowledgeQuery(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query:str=Field(min_length=1,max_length=1000)
    top_k:int=Field(default=4,ge=1,le=8)
    brand_id:UUID|None=None
class KnowledgeConfirm(BaseModel):
    model_config=ConfigDict(extra='forbid')
    confirmed:Literal[True]
    @field_validator('confirmed',mode='before')
    @classmethod
    def explicit_true(cls,value):
        if value is not True:raise ValueError('Explicit true required')
        return value
class WikiDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=120)
    chunk_ids:list[UUID]=Field(min_length=1,max_length=8)
class WikiEdit(WikiDraft):
    revision:int=Field(ge=1)
    content:str=Field(max_length=16384)
class WikiPublish(KnowledgeConfirm):
    revision:int=Field(ge=1)
    version:int=Field(ge=1)
class WikiArchive(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    archived:bool

def index_out(row):
    return {key:getattr(row,key) for key in ('id','version_id','chunker_version','embedding_model','status','embedding_status','attempts','error_code','updated_at')}

@router.get('/{brain_id}/knowledge/status')
async def status(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await service.access(db,who,brain_id)
    return {'enabled':index.settings().knowledge_enabled,'embeddings_enabled':index.settings().knowledge_embeddings_enabled,
        'chunker_version':index.CHUNKER,'rag_mode':'grounded_excerpts','max_evidence_bytes':8192,
        'cloud_sources_sent':False,'supported':['text/plain','text/markdown']}

@router.get('/{brain_id}/index-jobs')
async def jobs(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await index.access(db,who,brain_id)
    return [index_out(row) for row in await db.scalars(select(KnowledgeIndexJob).where(KnowledgeIndexJob.brain_id==str(brain_id)).order_by(KnowledgeIndexJob.created_at.desc()).limit(100))]

@router.post('/{brain_id}/sources/{source_id}/index')
async def rebuild(brain_id:UUID,source_id:UUID,body:KnowledgeConfirm,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await index.access(db,who,brain_id,True,True)
    _,source=await service.source_row(db,who,brain_id,source_id,True)
    if source.archived_at:raise HTTPException(409,'Source archived')
    value=await service.version_row(db,source,source.current_version)
    await service.raw_version(db,source,value);await index.parsed(db,value)
    description=await service.describe(db,source)
    if description.stale:raise HTTPException(409,'Refresh source trước reindex')
    job=await index.ensure_job(db,value,who.id)
    if job.status=='running':raise HTTPException(409,'Index đang running')
    job.embedding_generation+=1;job.embedding_engine=index.embedding_pin()
    job.status='queued';job.attempts=0;job.actor_id=who.id;job.embedding_status='pending';job.error_code=None;job.claim_id=None;job.locked_at=None;job.updated_at=now()
    await db.commit();return index_out(job)

@router.get('/{brain_id}/sources/{source_id}/versions/{version}/chunks')
async def chunks(brain_id:UUID,source_id:UUID,version:int,offset:int=Query(default=0,ge=0),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await index.access(db,who,brain_id)
    _,source=await service.source_row(db,who,brain_id,source_id)
    if source.archived_at:raise HTTPException(409,'Source archived')
    value=await service.version_row(db,source,version);await service.raw_version(db,source,value)
    rows=await db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.version_id==value.id,KnowledgeChunk.chunker_version==index.CHUNKER).order_by(KnowledgeChunk.ordinal).offset(offset).limit(100))
    return [retrieval.citation(row,value,source,False) for row in rows]

@router.get('/{brain_id}/chunks/{chunk_id}')
async def chunk(brain_id:UUID,chunk_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store';return await retrieval.resolve(db,who,brain_id,chunk_id)

@router.post('/{brain_id}/retrieval')
async def retrieve(brain_id:UUID,body:KnowledgeQuery,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await index.access(db,who,brain_id)
    if body.brand_id and str(body.brand_id)!=brain.brand_id:raise HTTPException(409,'Brand không thuộc Brain')
    await rate_limit(request.app.state.redis,'knowledge-query',who.id,30,60)
    await db.rollback() # no request transaction through local model I/O
    return await retrieval.retrieve(db,who,brain_id,body.query,body.top_k)

async def wiki_row(db,who,bid,wid,write=False):
    brain=await index.access(db,who,bid,write,write)
    row=await db.scalar(select(KnowledgeWiki).where(KnowledgeWiki.id==str(wid),KnowledgeWiki.brain_id==brain.id).execution_options(populate_existing=True))
    if not row:raise HTTPException(404,'Không tìm thấy Wiki')
    return brain,row

async def refs(db,who,bid,ids):
    if len(set(map(str,ids)))!=len(ids):raise HTTPException(422,'Citation bị trùng')
    return [await retrieval.resolve(db,who,bid,cid,True) for cid in ids]

async def stale(db,who,row,version):
    try:
        for ref in version.citations:await retrieval.resolve(db,who,row.brain_id,ref['chunk_id'],True)
        return False
    except HTTPException:return True

async def wiki_out(db,who,row,number=None,content=False):
    version=await db.get(KnowledgeWikiVersion,(row.id,number or row.current_version))
    if not version:raise HTTPException(404,'Wiki version không có')
    if hashlib.sha256(version.content.encode()).hexdigest()!=version.sha256:raise HTTPException(409,'Wiki integrity failed')
    result={'id':row.id,'title':version.title,'version':version.number,'current_version':row.current_version,
        'published_version':row.published_version,'revision':row.revision,'archived_at':row.archived_at,
        'stale':await stale(db,who,row,version),'sha256':version.sha256,'citations':version.citations}
    if content:result['content']=version.content
    return result

async def add_wiki_version(db,brain,row,who,title,content,citations):
    try:raw=content.encode()
    except UnicodeError:raise HTTPException(422,'Wiki Unicode không hợp lệ')
    validate_bytes(raw)
    if len(raw)>65536:raise HTTPException(413,'Wiki vượt64KiB')
    used=await db.scalar(select(func.coalesce(func.sum(func.octet_length(KnowledgeWikiVersion.content)),0)).where(KnowledgeWikiVersion.brain_id==brain.id))
    if used+len(raw)>10485760:raise HTTPException(409,'Wiki history đạt quota10MiB/Brain')
    if row.current_version>50:raise HTTPException(409,'Wiki đạt50versions')
    db.add(KnowledgeWikiVersion(wiki_id=row.id,number=row.current_version,brain_id=brain.id,workspace_id=brain.workspace_id,
        title=clean_name(title),content=content,citations=[{k:v for k,v in ref.items() if k!='quote'} for ref in citations],
        sha256=hashlib.sha256(raw).hexdigest(),created_by=who.id));await db.flush()

def event(db,row,who,action,previous,target):
    db.add(KnowledgeWikiEvent(wiki_id=row.id,brain_id=row.brain_id,workspace_id=row.workspace_id,
        actor_id=who.id,action=action,from_version=previous,to_version=target))

@router.get('/{brain_id}/wiki')
async def wikis(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await index.access(db,who,brain_id)
    return [await wiki_out(db,who,row) for row in await db.scalars(select(KnowledgeWiki).where(KnowledgeWiki.brain_id==str(brain_id)).order_by(KnowledgeWiki.created_at).limit(100))]

@router.post('/{brain_id}/wiki',status_code=201)
async def draft(brain_id:UUID,body:WikiDraft,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain=await index.access(db,who,brain_id,True,True)
    if await db.scalar(select(func.count()).select_from(KnowledgeWiki).where(KnowledgeWiki.brain_id==brain.id))>=100:raise HTTPException(409,'Brain đạt100Wiki')
    citations=await refs(db,who,brain.id,body.chunk_ids)
    content='\n\n'.join(f"Nguồn {i}: {ref['title']} v{ref['version']} lines {ref['start_line']}-{ref['end_line']}\n"+ref['quote'] for i,ref in enumerate(citations,1))
    row=KnowledgeWiki(brain_id=brain.id,workspace_id=brain.workspace_id,created_by=who.id);db.add(row);await db.flush()
    await add_wiki_version(db,brain,row,who,body.title,content,citations);event(db,row,who,'draft',None,1)
    await db.commit();return await wiki_out(db,who,row,content=True)

@router.get('/{brain_id}/wiki/{wiki_id}')
async def get_wiki(brain_id:UUID,wiki_id:UUID,version:int|None=Query(default=None,ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await wiki_row(db,who,brain_id,wiki_id);return await wiki_out(db,who,row,version,True)

@router.patch('/{brain_id}/wiki/{wiki_id}')
async def edit_wiki(brain_id:UUID,wiki_id:UUID,body:WikiEdit,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    brain,row=await wiki_row(db,who,brain_id,wiki_id,True)
    if row.revision!=body.revision or row.archived_at:raise HTTPException(409,'Wiki đổi revision/archived')
    citations=await refs(db,who,brain.id,body.chunk_ids);previous=row.current_version;row.current_version+=1;row.revision+=1
    await add_wiki_version(db,brain,row,who,body.title,body.content,citations);event(db,row,who,'edit',previous,row.current_version)
    await db.commit();return await wiki_out(db,who,row,content=True)

@router.get('/{brain_id}/wiki/{wiki_id}/diff')
async def diff(brain_id:UUID,wiki_id:UUID,from_version:int=Query(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await wiki_row(db,who,brain_id,wiki_id)
    old=await db.get(KnowledgeWikiVersion,(row.id,from_version));new=await db.get(KnowledgeWikiVersion,(row.id,row.current_version))
    if not old:raise HTTPException(404,'Wiki version không có')
    text=''.join(difflib.unified_diff(old.content.splitlines(True),new.content.splitlines(True),fromfile=f'v{old.number}',tofile=f'v{new.number}'))
    return {'from_version':from_version,'to_version':new.number,'diff':text[:16384],'truncated':len(text)>16384}

async def promote(db,who,bid,wid,body,action):
    _,row=await wiki_row(db,who,bid,wid,True)
    if row.revision!=body.revision or row.archived_at:raise HTTPException(409,'Wiki đổi revision/archived')
    if action=='publish' and body.version!=row.current_version:raise HTTPException(409,'Review bản draft mới nhất trước publish')
    if action=='revert' and not await db.scalar(select(KnowledgeWikiEvent.id).where(KnowledgeWikiEvent.wiki_id==row.id,
        KnowledgeWikiEvent.to_version==body.version,KnowledgeWikiEvent.action.in_(['publish','revert'])).limit(1)):
        raise HTTPException(409,'Chỉ revert bản đã được publish trước')
    version=await db.get(KnowledgeWikiVersion,(row.id,body.version))
    if not version:raise HTTPException(404,'Wiki version không có')
    if await stale(db,who,row,version):raise HTTPException(409,'Wiki stale, không promote')
    previous=row.published_version;row.published_version=body.version;row.revision+=1
    event(db,row,who,action,previous,body.version);await db.commit();return await wiki_out(db,who,row,body.version,True)

@router.post('/{brain_id}/wiki/{wiki_id}/publish')
async def publish(brain_id:UUID,wiki_id:UUID,body:WikiPublish,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await promote(db,who,brain_id,wiki_id,body,'publish')

@router.post('/{brain_id}/wiki/{wiki_id}/revert')
async def revert(brain_id:UUID,wiki_id:UUID,body:WikiPublish,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await promote(db,who,brain_id,wiki_id,body,'revert')

@router.post('/{brain_id}/wiki/{wiki_id}/archive')
async def archive(brain_id:UUID,wiki_id:UUID,body:WikiArchive,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    _,row=await wiki_row(db,who,brain_id,wiki_id,True)
    if row.revision!=body.revision:raise HTTPException(409,'Wiki đổi revision')
    row.archived_at=now() if body.archived else None;row.revision+=1;await db.commit();return await wiki_out(db,who,row)

async def graph_view(db,who,bid):
    await index.access(db,who,bid)
    nodes=[]
    for note in await db.scalars(select(BrainNote).where(BrainNote.brain_id==str(bid),BrainNote.trashed_at.is_(None)).order_by(BrainNote.id).limit(100)):
        value=await db.get(BrainNoteVersion,(note.id,note.content_version))
        nodes.append({'id':'note:'+note.id,'kind':'note','title':note.title,'content':value.content})
    for row in await db.scalars(select(KnowledgeWiki).where(KnowledgeWiki.brain_id==str(bid),KnowledgeWiki.archived_at.is_(None),KnowledgeWiki.published_version.is_not(None)).order_by(KnowledgeWiki.id).limit(100)):
        version=await db.get(KnowledgeWikiVersion,(row.id,row.published_version))
        if not await stale(db,who,row,version):nodes.append({'id':'wiki:'+row.id,'kind':'published_wiki','title':version.title,'content':version.content})
    by_title={}
    for node in nodes:by_title.setdefault(node['title'].casefold(),[]).append(node['id'])
    edges=[];unresolved=[];truncated=False
    for node in nodes:
        for label in sorted(set(re.findall(r'\[\[([^\[\]\n]{1,120})\]\]',node.pop('content'))))[:50]:
            matches=by_title.get(label.casefold(),[])
            if len(edges)+len(unresolved)>=500:truncated=True;continue
            if len(matches)==1:edges.append({'from':node['id'],'to':matches[0]})
            else:unresolved.append({'from':node['id'],'label':label,'reason':'missing_or_ambiguous'})
    result={'nodes':nodes,'edges':edges,'unresolved':unresolved,'derived':True,'limit':200,'truncated':truncated}
    result['sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False).encode()).hexdigest();return result

@router.get('/{brain_id}/graph')
async def graph(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await graph_view(db,who,brain_id)

@router.post('/{brain_id}/graph/rebuild')
async def graph_rebuild(brain_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await index.access(db,who,brain_id,True);return await graph_view(db,who,brain_id)
