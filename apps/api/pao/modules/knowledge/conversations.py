"""Opt-in grounded chat and file-service attachments; no source sent to cloud/LLM."""
import json
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from pydantic import BaseModel,ConfigDict
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from ...access import owned_session,owned_run
from ...auth import Principal,principal
from ...db import database,Session
from ...models import ChatSession,SessionAttachment,BrainFile,Run,RunKnowledge,Brain,now
from ..brains.files import validate_name,validate_bytes,read_upload,add_file,checked_content
from . import index,service,retrieval

router=APIRouter(prefix='/v1',tags=['knowledge-conversations'])
class SessionKnowledgeInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled:bool
    scope:Literal['brain','attachments']='brain'
class AttachFileInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    file_id:UUID

async def session_brain(db,who,sid,write=False):
    chat=await owned_session(db,sid,who,write)
    if write:
        chat=await db.scalar(select(ChatSession).where(ChatSession.id==chat.id).with_for_update().execution_options(populate_existing=True))
        if await db.scalar(select(Run.id).where(Run.session_id==chat.id,Run.status.in_(['queued','running'])).limit(1)):
            raise HTTPException(409,'Hội thoại đang chạy; không đổi context')
    if not chat.brain_id:raise HTTPException(409,'Chọn Brain trước')
    brain=await index.access(db,who,chat.brain_id,write,write)
    if brain.workspace_id!=chat.workspace_id or brain.brand_id!=chat.brand_id:raise HTTPException(409,'Session Brain scope sai')
    return chat,brain

@router.get('/sessions/{session_id}/knowledge')
async def config(session_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    chat=await owned_session(db,session_id,who)
    # Status endpoint is available while feature is disabled, but reveals no Brain content.
    return {'available':index.settings().knowledge_enabled and index.settings().knowledge_sources_enabled and index.settings().brain_manager_enabled,
        'enabled':chat.knowledge_enabled,'scope':chat.knowledge_scope,'brain_id':chat.brain_id,'mode':'grounded_excerpts'}

@router.put('/sessions/{session_id}/knowledge')
async def configure(session_id:UUID,body:SessionKnowledgeInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    chat,brain=await session_brain(db,who,session_id,True)
    chat.knowledge_enabled=body.enabled;chat.knowledge_scope=body.scope
    await db.commit();return {'available':True,'enabled':chat.knowledge_enabled,'scope':chat.knowledge_scope,'brain_id':brain.id,'mode':'grounded_excerpts'}

async def attach(db,who,chat,brain,file):
    checked_content(file)
    row=await db.scalar(select(SessionAttachment).where(SessionAttachment.session_id==chat.id,SessionAttachment.brain_id==brain.id,SessionAttachment.file_id==file.id))
    if not row or row.removed_at is not None:
        count=await db.scalar(select(func.count()).select_from(SessionAttachment).where(SessionAttachment.session_id==chat.id,SessionAttachment.removed_at.is_(None)))
        if count>=10:raise HTTPException(409,'Session tối đa10attachments')
    if not row:
        row=SessionAttachment(session_id=chat.id,brain_id=brain.id,workspace_id=brain.workspace_id,file_id=file.id,added_by=who.id);db.add(row)
    row.removed_at=None
    await service.capture(db,brain,who,'file',file.id);await db.flush();return row

@router.get('/sessions/{session_id}/attachments')
async def attachments(session_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    chat,brain=await session_brain(db,who,session_id)
    rows=await db.execute(select(SessionAttachment,BrainFile).join(BrainFile,BrainFile.id==SessionAttachment.file_id).where(
        SessionAttachment.session_id==chat.id,SessionAttachment.brain_id==brain.id,SessionAttachment.removed_at.is_(None)))
    return [{'id':row.id,'file_id':file.id,'name':file.name,'size':file.size,'sha256':file.sha256,'trashed':bool(file.trashed_at),
        'download':f'/v1/brains/{brain.id}/files/{file.id}/download'} for row,file in rows]

@router.post('/sessions/{session_id}/attachments',status_code=201)
async def add_attachment(session_id:UUID,body:AttachFileInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    chat,brain=await session_brain(db,who,session_id,True)
    file=await db.scalar(select(BrainFile).where(BrainFile.id==str(body.file_id),BrainFile.brain_id==brain.id))
    if not file:raise HTTPException(404,'File không trong Brain')
    row=await attach(db,who,chat,brain,file);await db.commit();return {'id':row.id,'file_id':file.id,'brain_id':brain.id}

@router.post('/sessions/{session_id}/attachments/upload',status_code=201)
async def upload_attachment(session_id:UUID,request:Request,name:str=Query(min_length=1,max_length=160),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    chat,brain=await session_brain(db,who,session_id)
    old_brain,old_version=brain.id,chat.brain_version
    mime=request.headers.get('content-type','').split(';')[0].strip().lower();validate_name(name,mime)
    await db.rollback();raw=await read_upload(request);validate_bytes(raw)
    chat,brain=await session_brain(db,who,session_id,True)
    if brain.id!=old_brain or chat.brain_version!=old_version:raise HTTPException(409,'Brain đã đổi trong upload; thử lại')
    file=await add_file(db,brain,who,name,mime,raw);row=await attach(db,who,chat,brain,file)
    await db.commit();return {'id':row.id,'file_id':file.id,'brain_id':brain.id,'sha256':file.sha256}

@router.delete('/sessions/{session_id}/attachments/{attachment_id}',status_code=204)
async def remove_attachment(session_id:UUID,attachment_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    chat,brain=await session_brain(db,who,session_id,True)
    row=await db.scalar(select(SessionAttachment).where(SessionAttachment.id==str(attachment_id),SessionAttachment.session_id==chat.id,SessionAttachment.brain_id==brain.id))
    if not row:raise HTTPException(404,'Không tìm thấy attachment')
    row.removed_at=now();await db.commit();return None

async def snapshot_attachments(db,chat):
    return list(await db.scalars(select(SessionAttachment.file_id).where(SessionAttachment.session_id==chat.id,
        SessionAttachment.brain_id==chat.brain_id,SessionAttachment.removed_at.is_(None)).order_by(SessionAttachment.id).limit(10)))

async def run_visible(db,run,who):
    if not (run.brain_context or {}).get('knowledge'):return True
    try:
        await index.access(db,who,run.brain_id)
        record=await db.scalar(select(RunKnowledge).where(RunKnowledge.run_id==run.id))
        if record:
            for ref in record.evidence:await retrieval.resolve(db,who,run.brain_id,ref['chunk_id'])
        return True
    except HTTPException:return False

async def answer_run(ctx,run,chat):
    who=Principal(chat.user_id,0)
    async with Session() as db:
        from ...models import User
        owner=await db.get(User,who.id)
        if not owner or not owner.active:raise PermissionError('access_revoked')
        await index.access(db,who,run.brain_id,True)
        files=(run.brain_context or {}).get('attachment_files',[]) if (run.brain_context or {}).get('knowledge_scope')=='attachments' else None
        async def current_run(fresh):
            from ..brains.context import check_run_brain
            from ..channels.service import check_run
            current=await fresh.get(Run,run.id);current_chat=await fresh.get(ChatSession,current.session_id)
            if current.status!='running' or current.cancel_requested:raise PermissionError('knowledge_run_not_active')
            await check_run_brain(fresh,current,current_chat);await check_run(fresh,current)
        result=await retrieval.retrieve(db,who,run.brain_id,run.prompt,file_ids=files,gateway=ctx.get('knowledge_gateway'),
            engine_pin=(run.engine_snapshot or {}).get('embedding_engine'),require_pin=True,
            request_key='knowledge-query:'+run.id,check=current_run)
    # Revalidate every citation under Brain lock before persisting any output.
    async with Session.begin() as db:
        await index.access(db,who,run.brain_id,True,True)
        for ref in result['items']:await retrieval.resolve(db,who,run.brain_id,ref['chunk_id'],True)
        current=await db.scalar(select(Run).where(Run.id==run.id).with_for_update())
        from ..channels.service import check_run
        await check_run(db,current)
        if current.cancel_requested:return
        if current.cancel_requested or current.status!='running':return
        evidence=[{k:v for k,v in ref.items() if k not in ('quote','score')} for ref in result['items']]
        db.add(RunKnowledge(run_id=run.id,brain_id=run.brain_id,workspace_id=run.workspace_id,evidence=evidence,status=result['status'],mode=result['mode']))
        current.response=retrieval.grounded_answer(result)
        from ..conversations.state import emit
        # Keep the existing SSE enum/wire schema. This is an evidence plan,
        # not a new event kind or a claim that tools/LLM were executed.
        metadata={'kind':'knowledge_retrieval','count':len(evidence),'status':result['status'],'mode':result['mode'],'degraded':result['degraded']}
        current.execution_plan={**(current.execution_plan or {}),'knowledge_retrieval':metadata}
        emit(db,current,'plan.created',current.execution_plan)
        emit(db,current,'core.speaking');emit(db,current,'response.delta',{'text':current.response})

@router.get('/runs/{run_id}/knowledge')
async def evidence(run_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    run=await owned_run(db,run_id,who)
    if not await run_visible(db,run,who):raise HTTPException(404,'Nguồn không còn được phép truy cập')
    record=await db.scalar(select(RunKnowledge).where(RunKnowledge.run_id==run.id))
    if not record:raise HTTPException(404,'Run chưa có evidence')
    items=[await retrieval.resolve(db,who,run.brain_id,ref['chunk_id']) for ref in record.evidence]
    return {'run_id':run.id,'brain_id':run.brain_id,'status':record.status,'mode':record.mode,'items':items}

@router.get('/runs/{run_id}/knowledge/download')
async def artifact(run_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    data=await evidence(run_id,who,db)
    return Response(json.dumps(data,ensure_ascii=False),media_type='application/json',headers={
        'Content-Disposition':f'attachment; filename="knowledge-{run_id}.json"','Cache-Control':'no-store',
        'X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"})
