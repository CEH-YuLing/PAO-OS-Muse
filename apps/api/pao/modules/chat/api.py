"""Additive owner-scoped chat management; existing DTOs/SSE remain unchanged."""
import re
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, literal_column
from sqlalchemy.ext.asyncio import AsyncSession
from ...access import owned_session, owned_run, membership
from ...auth import Principal, principal
from ...config import settings
from ...db import database
from ...models import ChatSession, Run, Message, LlmAttempt, ChatCompaction, Task, Memory, now
from .policy import policy_for
from . import compaction, commands

router = APIRouter(tags=['chat-management'])


def enabled():
    if not settings().chat_features_enabled or not settings().engine_contract_enabled:
        raise HTTPException(503, 'chat_features_disabled')


class Policy(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    privacy: Literal['local_only','cloud_allowed'] = 'local_only'
    cloud_references: bool = False
    token_mode: Literal['provider','bounded'] = 'bounded'  # Explicit numeric legacy clients keep their contract.
    context_tokens: int = Field(default=4096, ge=1024, le=32768)
    max_bytes: int = Field(default=16384, ge=1024, le=65536)
    max_output_tokens: int = Field(default=512, ge=16, le=2048)
    max_run_tokens: int = Field(default=32768, ge=1024, le=131072)
    max_calls: int = Field(default=8, ge=1, le=16)
    require_reported_usage: bool = False


class Pricing(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    input_per_million: str = Field(pattern=r'^\d{1,5}(\.\d{1,8})?$')
    output_per_million: str = Field(pattern=r'^\d{1,5}(\.\d{1,8})?$')
    version: str = Field(min_length=1,max_length=60,pattern=r'^[a-zA-Z0-9_.-]+$')


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: int = Field(ge=1)
    pinned: bool = False
    group: str = Field(default='', max_length=60, pattern=r'^[^\x00-\x1f\x7f]*$')
    policy: Policy
    pricing: Pricing | None = None


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    text: str = Field(min_length=1, max_length=512)


class Retry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    request_key: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')


def profile(chat):
    value = chat.chat_profile or {}
    return {'available':settings().chat_features_enabled and settings().engine_contract_enabled, 'version':chat.chat_revision,
        'pinned':value.get('pinned',False),'group':value.get('group',''),'policy':policy_for(chat)}


async def lock_chat(db, sid, who):
    from ..connections.enterprise_ai import chat_owned
    chat = await chat_owned(db, sid, who)
    return await db.scalar(select(ChatSession).where(ChatSession.id == chat.id).with_for_update().execution_options(populate_existing=True))


@router.get('/v1/sessions/{session_id}/chat')
async def get_profile(session_id:UUID, who:Principal=Depends(principal), db:AsyncSession=Depends(database)):
    return profile(await owned_session(db, session_id, who))


@router.put('/v1/sessions/{session_id}/chat')
async def put_profile(session_id:UUID, body:Profile, who:Principal=Depends(principal), db:AsyncSession=Depends(database)):
    enabled(); chat = await lock_chat(db, session_id, who)
    if chat.chat_revision != body.version: raise HTTPException(409,'chat_revision_conflict')
    if await db.scalar(select(Run.id).where(Run.session_id==chat.id,Run.status.in_(['queued','running']))):
        raise HTTPException(409,'chat_run_active')
    value=body.policy.model_dump()
    read_only = bool((chat.chat_profile or {}).get('enterprise_ai_read_only'))
    if read_only and (value['cloud_references'] or body.pricing):
        raise HTTPException(403, 'enterprise_ai_read_only_required')
    if value['token_mode']=='bounded' and (value['context_tokens'] > settings().context_tokens or value['max_output_tokens'] > settings().output_tokens):
        raise HTTPException(422,'chat_budget_exceeds_server')
    if value['token_mode']=='bounded' and value['max_output_tokens'] >= value['context_tokens']: raise HTTPException(422,'chat_budget_invalid')
    price={**body.pricing.model_dump(),'currency':'USD','configured_at':now().isoformat(),
        'kind':'owner_configured_estimate'} if body.pricing else None
    if price:
        from ..engines.service import default_config
        from ..engines.contract import EngineFailure
        try:selection=chat.engine_config or await default_config(db,chat.workspace_id,actor_id=who.id,brand_id=chat.brand_id)
        except EngineFailure as exc:raise HTTPException(409,exc.code) from None
        price.update(provider=selection['provider'],model=selection['model'])
    chat.chat_profile={'pinned':body.pinned,'group':body.group,'policy':{**value,'version':'p3-policy-v1','pricing':price},
        **({'enterprise_ai_read_only': True} if read_only else {})}
    chat.chat_revision+=1
    await db.commit(); return profile(chat)


@router.get('/v1/chat/sessions')
async def search(workspace_id:UUID, q:str=Query(default='',max_length=120), group:str=Query(default='',max_length=60),
    pinned:bool=False, who:Principal=Depends(principal), db:AsyncSession=Depends(database)):
    enabled(); await membership(db,str(workspace_id),who)
    chats=list(await db.scalars(select(ChatSession).where(ChatSession.workspace_id==str(workspace_id),ChatSession.user_id==who.id,
        ChatSession.archived_at.is_(None)).order_by(ChatSession.created_at.desc(),ChatSession.id).limit(100)))
    result=[]
    for chat in chats:
        value=profile(chat)
        if group and value['group']!=group or pinned and not value['pinned']:continue
        # ACL is evaluated BEFORE matching private message content/snippets.
        query=func.plainto_tsquery(literal_column("'simple'"),q)
        title_match=not q or bool(await db.scalar(select(ChatSession.id).where(ChatSession.id==chat.id,
            func.to_tsvector(literal_column("'simple'"),ChatSession.title).op('@@')(query))))
        content_match=False
        if q and not title_match:
            ids=[message.id for message,run in await compaction.original_messages(db,chat,who)]
            if ids:content_match=bool(await db.scalar(select(Message.id).where(Message.id.in_(ids),
                func.to_tsvector(literal_column("'simple'"),Message.content).op('@@')(query)).limit(1)))
        if title_match or content_match:result.append({'id':chat.id,'title':chat.title,'pinned':value['pinned'],'group':value['group']})
    return sorted(result,key=lambda row:not row['pinned'])


@router.get('/v1/sessions/{session_id}/export')
async def export(session_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();chat=await owned_session(db,session_id,who)
    rows=await compaction.original_messages(db,chat,who,5000)
    # Plain fenced Markdown download, not executable HTML. No filesystem paths.
    sections=['# PAO conversation\n']
    for message,run in rows:
        # Tilde fence wider than every source run avoids arbitrary embedded fences.
        fence='~'*max(3,1+max((len(x) for x in re.findall(r'~+',message.content)),default=0))
        sections.append(f'## {message.role} ({message.status})\n{fence}text\n{message.content}\n{fence}\n')
    raw='\n'.join(sections).encode()
    if len(raw)>2_097_152:raise HTTPException(413,'chat_export_limit')
    return Response(raw,media_type='text/markdown; charset=utf-8',headers={
        'Content-Disposition':f'attachment; filename="pao-{chat.id}.md"','X-Content-Type-Options':'nosniff'})


def compact_view(row):
    return {'id':row.id,'revision':row.revision,'version':row.version,'message_ids':row.message_ids,'source_hash':row.source_hash}


@router.get('/v1/sessions/{session_id}/compactions')
async def list_compactions(session_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();chat=await owned_session(db,session_id,who)
    if chat.brain_id:
        from ..brains.access import require_brain
        await require_brain(db,who,chat.brain_id)
    rows=await db.scalars(select(ChatCompaction).where(ChatCompaction.session_id==chat.id,ChatCompaction.brain_id==chat.brain_id)
        .order_by(ChatCompaction.revision.desc()).limit(20))
    return [compact_view(row) for row in rows]


@router.post('/v1/sessions/{session_id}/compactions',status_code=201)
async def create_compaction(session_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();chat=await lock_chat(db,session_id,who)
    row=await compaction.compact(db,chat,who);await db.commit();return compact_view(row)


def attempt_view(row):
    return {**{key:getattr(row,key) for key in ('id','run_id','task_attempt_id','brain_id','provider','model','source','status','usage_state',
        'estimated_input_tokens','reserved_output_tokens','estimated_output_tokens','input_tokens','output_tokens','ttft_ms','elapsed_ms')},
        'cost_estimate':str(row.cost_estimate) if row.cost_estimate is not None else None,'pricing':row.pricing}


@router.get('/v1/chat/usage')
async def usage(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();await membership(db,str(workspace_id),who)
    rows=await db.scalars(select(LlmAttempt).join(ChatSession,ChatSession.id==LlmAttempt.session_id).where(
        LlmAttempt.workspace_id==str(workspace_id),LlmAttempt.user_id==who.id,ChatSession.archived_at.is_(None))
        .order_by(LlmAttempt.created_at.desc()).limit(100))
    safe=[]
    for row in rows:
        run=await db.get(Run,row.run_id)
        if await compaction.visible(db,run,who):safe.append(attempt_view(row))
    return {'attempts':safe,'cost':None,'cost_status':'see_per_attempt_estimates_unknown_is_not_zero',
        'notice':'Reported counts and estimates differ; this is not an invoice or subscription quota.'}


@router.get('/v1/runs/{run_id}/usage')
async def run_usage(run_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();run=await owned_run(db,run_id,who)
    if not await compaction.visible(db,run,who):raise HTTPException(404,'chat_source_unavailable')
    return [attempt_view(row) for row in await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run.id).order_by(LlmAttempt.created_at))]


@router.get('/v1/runs/{run_id}/context')
async def context_trace(run_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();run=await owned_run(db,run_id,who)
    if not await compaction.visible(db,run,who):raise HTTPException(404,'chat_source_unavailable')
    return [{'attempt_id':row.id,'trace':row.trace} for row in await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run.id).order_by(LlmAttempt.created_at))]


@router.post('/v1/runs/{run_id}/retry',status_code=202)
async def retry(run_id:UUID,body:Retry,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();run=await owned_run(db,run_id,who,True)
    if run.status not in ('completed','failed','cancelled'):raise HTTPException(409,'chat_run_active')
    if not await compaction.visible(db,run,who):raise HTTPException(404,'chat_source_unavailable')
    from ...core_api import create_run
    from ...schemas import RunCreate,RunOut
    request.state.pao_retry_parent=run.id
    result=await create_run(RunCreate(session_id=run.session_id,message=run.prompt,request_key=body.request_key),request,who,db)
    return {**RunOut.model_validate(result).model_dump(mode='json'),'parent_run_id':result.parent_run_id}


@router.post('/v1/sessions/{session_id}/commands')
async def command(session_id:UUID,body:Command,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    enabled();chat=await owned_session(db,session_id,who,True)
    parsed=commands.parse(body.text)
    if not parsed:raise HTTPException(422,'chat_command_unknown')
    name,args=parsed
    if name=='goal':raise HTTPException(409,'goal_requires_P6')
    if name in ('invalid','unknown'):raise HTTPException(422,'chat_command_invalid')
    if name not in ('model','brain') and args:raise HTTPException(422,'chat_command_arguments')
    if name=='help':return {'commands':['/'+key for key in commands.COMMANDS],'goal':'blocked_until_P6'}
    if name=='status':return {'profile':profile(chat),'active':list(await db.scalars(select(Run.id).where(Run.session_id==chat.id,Run.status.in_(['queued','running']))))}
    if name=='brain':
        from ..brains.api import session_brain,switch_brain,SessionBrain
        if not args:return await session_brain(session_id,who,db)
        if len(args)!=1:raise HTTPException(422,'Usage: /brain UUID')
        try:choice=SessionBrain(brain_id=UUID(args[0]),version=chat.brain_version)
        except ValueError:raise HTTPException(422,'chat_command_brain_invalid') from None
        return await switch_brain(session_id,choice,who,db)
    if name=='tasks':return {'tasks':[{'id':row.id,'title':row.title,'status':row.status,'progress':row.progress} for row in
        await db.scalars(select(Task).where(Task.workspace_id==chat.workspace_id,Task.created_by==who.id).order_by(Task.updated_at.desc()).limit(100))]}
    if name=='memory':
        if chat.brain_id:
            from ..brains.access import legacy_facts
            rows=await legacy_facts(db,who,chat.brain_id)
        else:
            from ...memory import scope
            rows=list(await db.scalars(select(Memory).where(*scope(chat.workspace_id,who.id,chat.brand_id),Memory.status=='active')
                .order_by(Memory.updated_at.desc()).limit(20)))
        return {'enabled':chat.memory_enabled,'brain_id':chat.brain_id,'facts':[{'id':row.id,'key':row.key,'value':row.value} for row in rows[:20]],
            'notice':'Private legacy facts only, no provider call. Custom Brain knowledge is managed in the Knowledge panel.'}
    if name=='model':
        from ..engines.api import get_selection,set_selection,EngineChoice
        if not args:return await get_selection(session_id,who,db)
        if len(args)!=2:raise HTTPException(422,'Usage: /model provider model')
        try:choice=EngineChoice(provider=args[0],model=args[1],version=chat.engine_version)
        except ValueError:raise HTTPException(422,'chat_command_model_invalid') from None
        return await set_selection(session_id,choice,who,db)
    if name=='usage':return await usage(UUID(chat.workspace_id),who,db)
    if name=='compact':return await create_compaction(session_id,who,db)
    if name=='export':return {'download':f'/v1/sessions/{chat.id}/export'}
    if name=='stop':
        from ...core_api import cancel
        active=await db.scalar(select(Run.id).where(Run.session_id==chat.id,Run.status.in_(['queued','running'])))
        if active:await cancel(UUID(active),who,db)
        return {'cancel_requested':bool(active)}
