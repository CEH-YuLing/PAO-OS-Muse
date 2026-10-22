"""Local-first channel contract; durable receipts, no implicit remote authority."""
import hashlib,hmac
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID,uuid5
from fastapi import HTTPException
from sqlalchemy import select,or_,cast,String,literal,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.auth import Principal,rate_limit
from pao.models import ChannelBinding,ChannelInbound,ChannelOutbox,ChannelAudit,ChatSession,Run,Member,User,TelegramPeer,now
from pao.db import Session
from pao.schemas import RunCreate
from pao.modules.studio.contracts import digest
from pao.modules.conversations.requests import admit_run
from pao.modules.conversations.state import finish,TERMINAL
from pao.modules.chat.commands import parse

def enabled():
    if not settings().channels_enabled:raise HTTPException(409,'channels_disabled')

def identity(channel,external,connection_id=None):
    key=settings().channel_identity_key or settings().jwt_secret
    if len(key)<32:raise HTTPException(503,'channel_identity_key_invalid')
    namespace=channel if connection_id is None else channel+':connection:'+str(UUID(str(connection_id)))
    return hmac.new(key.encode(),(namespace+':'+external).encode(),hashlib.sha256).hexdigest()

async def actor(db,binding):
    user=await db.get(User,binding.actor_id);member=await db.get(Member,(binding.workspace_id,binding.actor_id))
    if not binding.enabled or not user or not user.active or not member or member.role=='viewer':raise HTTPException(403,'channel_actor_unavailable')
    if binding.kind=='customer' and member.role!='operator':raise HTTPException(403,'customer_actor_must_be_operator')
    if binding.channel=='telegram':
        if getattr(binding,'connection_id',None) is not None:
            if not settings().telegram_scoped_runtime_enabled:
                raise HTTPException(503,'telegram_connection_transport_pending')
            from .telegram_scoped import context as scoped_context
            from .telegram_runtime import TelegramRuntimeError
            try:await scoped_context(db,binding)
            except TelegramRuntimeError:raise HTTPException(403,'telegram_channel_unavailable') from None
        else:
            from .telegram_helpers import legacy_blocked
            if await legacy_blocked(db):raise HTTPException(403,'telegram_legacy_mapped')
            peer=await db.get(TelegramPeer,binding.peer_id,populate_existing=True) if binding.peer_id else None
            if (not peer or not peer.enabled or peer.connection_id is not None or peer.user_id!=binding.actor_id or peer.workspace_id!=binding.workspace_id or
                binding.identity_hash!=identity('telegram',peer.telegram_user_id+':'+peer.chat_id)):
                raise HTTPException(403,'channel_peer_changed')
    who=Principal(binding.actor_id,0)
    if binding.brain_id:
        from pao.modules.brains.access import require_brain
        brain=await require_brain(db,who,binding.brain_id,True)
        if brain.workspace_id!=binding.workspace_id or (binding.kind=='customer' and brain.legacy_default):raise HTTPException(403,'customer_brain_scope_invalid')
    elif binding.kind=='customer':raise HTTPException(403,'customer_brain_required')
    return who

async def check_run(db,run):
    context=run.channel_context
    if not context:return
    binding=await db.get(ChannelBinding,context.get('binding_id'),populate_existing=True)
    if (not settings().channels_enabled or not binding or binding.workspace_id!=run.workspace_id or binding.session_id!=run.session_id or
        binding.version!=context.get('version') or binding.mode!='auto'):
        raise PermissionError('channel_scope_revoked')
    try:await actor(db,binding)
    except HTTPException:raise PermissionError('channel_actor_revoked') from None
    if binding.connection_id is not None:
        from .telegram_scoped import context as scoped_context
        from .telegram_runtime import TelegramRuntimeError
        pinned=context.get('telegram')
        if type(pinned) is not dict or type(pinned.get('generation')) is not int:raise PermissionError('channel_pin_missing')
        try:current=await scoped_context(db,binding)
        except (TelegramRuntimeError,HTTPException):raise PermissionError('channel_scope_revoked') from None
        if current!=pinned:raise PermissionError('channel_pin_revoked')
        admitted=await db.scalar(select(ChannelInbound).where(ChannelInbound.run_id==run.id))
        if admitted and admitted.telegram_context!=pinned:raise PermissionError('channel_admission_pin_changed')
    if binding.kind=='customer' and (not settings().channel_autoreply_enabled or run.brain_id!=binding.brain_id or not (run.brain_context or {}).get('knowledge')):
        raise PermissionError('customer_grounding_required')

async def queue(db,binding,key,body,kind='auto'):
    if binding.channel=='telegram' and len(body.encode('utf-16-le'))//2>3500:
        # Each part has a durable receipt: never truncate or replay already sent parts.
        parts=[];current='';units=0
        for char in body:
            width=len(char.encode('utf-16-le'))//2
            if units+width>3500:parts.append(current);current='';units=0
            current+=char;units+=width
        if current:parts.append(current)
        first=None
        for index,part in enumerate(parts):
            item=await queue(db,binding,key+':p:'+str(index),part,kind)
            if first is None:first=item
        return first
    fingerprint=digest({'body':body,'kind':kind})
    execution=None
    if binding.connection_id is not None and settings().telegram_scoped_runtime_enabled:
        from .telegram_scoped import context as scoped_context
        execution=await scoped_context(db,binding)
    saved=await db.scalar(select(ChannelOutbox).where(ChannelOutbox.binding_id==binding.id,ChannelOutbox.request_key==key))
    if saved:
        if saved.content_hash!=fingerprint:raise HTTPException(409,'channel_delivery_key_conflict')
        if execution is not None and saved.telegram_context!=execution:raise HTTPException(409,'channel_delivery_scope_stale')
        return saved
    saved=ChannelOutbox(id=str(uuid5(UUID(binding.id),'delivery:'+key)),workspace_id=binding.workspace_id,binding_id=binding.id,connection_id=getattr(binding,'connection_id',None),
        request_key=key,content_hash=fingerprint,body=body,kind=kind,telegram_context=execution)
    db.add(saved);await db.flush();return saved

async def ensure_session(db,binding):
    if not binding.session_id:
        chat=ChatSession(workspace_id=binding.workspace_id,user_id=binding.actor_id,title='Channel '+binding.channel,memory_enabled=False,
            brain_id=binding.brain_id,knowledge_enabled=binding.kind=='customer')
        db.add(chat);await db.flush();binding.session_id=chat.id;await db.flush()


async def ingest(db,binding,key,body,redis):
    enabled();who=await actor(db,binding)
    fingerprint=digest({'body':body})
    external=digest(key)
    existing=await db.scalar(select(ChannelInbound).where(ChannelInbound.binding_id==binding.id,ChannelInbound.external_key==external))
    if existing:
        if existing.content_hash!=fingerprint:raise HTTPException(409,'channel_inbound_key_conflict')
        return existing
    await rate_limit(redis,'channel-inbound',binding.id,20,60)
    execution=None
    if binding.connection_id is not None:
        if binding.mode=='auto' and not body.strip().startswith('/') and (binding.kind!='customer' or settings().channel_autoreply_enabled):
            await ensure_session(db,binding)
        from .telegram_scoped import context as scoped_context
        execution=await scoped_context(db,binding)
    row=ChannelInbound(workspace_id=binding.workspace_id,binding_id=binding.id,connection_id=getattr(binding,'connection_id',None),external_key=external,content_hash=fingerprint,body=body,status='quiet',telegram_context=execution)
    db.add(row);await db.flush()
    if binding.mode!='auto':return row
    if binding.kind=='customer' and not settings().channel_autoreply_enabled:row.status='blocked';return row
    parsed=parse(body.strip())
    if body.strip().startswith('/'):
        name,args=parsed or ('unknown',[])
        row.status='command'
        if name=='stop' and not args and binding.session_id:
            active=await db.scalar(select(Run).where(Run.session_id==binding.session_id,Run.status.in_(('queued','running'))).with_for_update())
            if active:
                active.cancel_requested=True
                if active.status=='queued':await finish(db,active,'cancelled')
            await queue(db,binding,'command:'+row.id,'Đã yêu cầu dừng lượt hiện tại.')
        elif name=='status' and not args:
            run=await db.scalar(select(Run).where(Run.session_id==binding.session_id).order_by(Run.created_at.desc()).limit(1)) if binding.session_id else None
            await queue(db,binding,'command:'+row.id,'Trạng thái: '+(run.status if run else 'chưa có lượt'))
        elif name=='help' and not args:await queue(db,binding,'command:'+row.id,'PAO: văn bản, /help, /status, /stop. Không tự duyệt hoặc chạy terminal.')
        else:await queue(db,binding,'command:'+row.id,'Lệnh không được phép qua kênh này; dùng dashboard có xác thực.')
        return row
    await ensure_session(db,binding)
    active=await db.scalar(select(Run.id).where(Run.session_id==binding.session_id,Run.status.in_(('queued','running'))))
    if active:row.status='busy';return row
    request=SimpleNamespace(state=SimpleNamespace(pao_retry_parent=None),app=SimpleNamespace(state=SimpleNamespace(redis=redis)))
    value=await admit_run(RunCreate(session_id=binding.session_id,request_key='channel-'+row.id,message=body),request,who,db,commit=False)
    # Single admission boundary owns Run pins, including native Telegram scope.
    row.status='accepted';row.run_id=value.id
    return row

async def control(db,binding,who,body):
    data=body.model_dump(mode='json');key=str(body.request_key);fingerprint=digest(data)
    saved=await db.scalar(select(ChannelAudit).where(ChannelAudit.binding_id==binding.id,ChannelAudit.request_key==key))
    if saved:
        if saved.content_hash!=fingerprint:raise HTTPException(409,'channel_control_key_conflict')
        return binding
    if body.version!=binding.version:raise HTTPException(409,'channel_version_conflict')
    if body.action in ('auto','human','quiet'):binding.mode=body.action
    elif body.action=='disable':binding.enabled=False
    elif body.action=='enable':await actor(db,SimpleNamespace(**{**binding.__dict__,'enabled':True}));binding.enabled=True
    elif body.action=='allow_outbound':
        if not body.confirm_destination or binding.channel!='telegram' or not binding.peer_id:raise HTTPException(422,'destination_confirmation_required')
        peer=await db.get(TelegramPeer,binding.peer_id)
        if not peer or not peer.enabled or peer.user_id!=binding.actor_id or peer.workspace_id!=binding.workspace_id:raise HTTPException(409,'channel_peer_changed')
        binding.outbound_confirmed=True
    elif body.action=='deny_outbound':binding.outbound_confirmed=False
    binding.version+=1
    active=list(await db.scalars(select(Run).where(Run.session_id==binding.session_id,Run.status.in_(('queued','running'))).with_for_update()))
    for run in active:
        run.cancel_requested=True
        if run.status=='queued':await finish(db,run,'cancelled')
    for row in await db.scalars(select(ChannelOutbox).where(ChannelOutbox.binding_id==binding.id,ChannelOutbox.status.in_(('queued','failed'))).with_for_update()):
        if row.kind=='auto' or not binding.enabled or not binding.outbound_confirmed:row.status='cancelled'
    db.add(ChannelAudit(workspace_id=binding.workspace_id,binding_id=binding.id,connection_id=getattr(binding,'connection_id',None),actor_id=who.id,request_key=key,content_hash=fingerprint,
        data={'action':body.action,'version':binding.version,'mode':binding.mode,'enabled':binding.enabled,'outbound_confirmed':binding.outbound_confirmed}))
    return binding

async def collect():
    if not settings().channels_enabled:
        await purge_expired();return {'processed':0}
    count=0
    async with Session.begin() as db:
        from .telegram_helpers import legacy_blocked
        retired_telegram=await legacy_blocked(db)
        key=literal('result:')+cast(ChannelInbound.run_id,String)
        delivered=select(ChannelOutbox.id).where(ChannelOutbox.binding_id==ChannelInbound.binding_id,
            or_(ChannelOutbox.request_key==key,ChannelOutbox.request_key==key+literal(':p:0'))).exists()
        rows=list(await db.scalars(select(ChannelInbound).join(Run,Run.id==ChannelInbound.run_id).where(
            ChannelInbound.connection_id.is_(None),ChannelInbound.status=='accepted',ChannelInbound.purged_at.is_(None),Run.status.in_(TERMINAL),~delivered).order_by(ChannelInbound.created_at,ChannelInbound.id).limit(100)))
        for row in rows:
            binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.id==row.binding_id).with_for_update(skip_locked=True))
            if not binding:continue
            if retired_telegram and binding.channel=='telegram' and binding.connection_id is None:continue
            row=await db.get(ChannelInbound,row.id,with_for_update=True,populate_existing=True)
            if row.purged_at or row.status!='accepted':continue
            run=await db.get(Run,row.run_id)
            try:await check_run(db,run)
            except PermissionError:row.status='blocked';continue
            from pao.modules.knowledge.conversations import run_visible
            if not await run_visible(db,run,Principal(binding.actor_id,0)):row.status='blocked';continue
            await queue(db,binding,'result:'+run.id,run.response or 'Lượt đã kết thúc: '+run.status);count+=1
    await purge_expired()
    return {'processed':count}

async def purge_expired(only_binding=None):
    """Configured retention removes message bodies, not dedup/control metadata."""
    if not settings().channel_retention_enabled:
        return {'purged': 0}
    count=0
    async with Session.begin() as db:
        cutoff=func.now()-ChannelBinding.retention_days*text("INTERVAL '1 day'")
        expired_in=select(ChannelInbound.id).outerjoin(Run,Run.id==ChannelInbound.run_id).where(ChannelInbound.binding_id==ChannelBinding.id,
            ChannelInbound.created_at<cutoff,ChannelInbound.purged_at.is_(None),or_(ChannelInbound.run_id.is_(None),Run.status.in_(TERMINAL))).exists()
        expired_out=select(ChannelOutbox.id).where(ChannelOutbox.binding_id==ChannelBinding.id,ChannelOutbox.created_at<cutoff,
            ChannelOutbox.body.is_not(None),ChannelOutbox.status!='sending').exists()
        query=select(ChannelBinding).where(ChannelBinding.kind=='customer',or_(expired_in,expired_out)).order_by(ChannelBinding.id)
        if only_binding:query=query.where(ChannelBinding.id==only_binding)
        for binding in await db.scalars(query.with_for_update(skip_locked=True).limit(100)):
            cutoff=now()-timedelta(days=binding.retention_days)
            for row in await db.scalars(select(ChannelInbound).where(ChannelInbound.binding_id==binding.id,ChannelInbound.created_at<cutoff,ChannelInbound.purged_at.is_(None)).with_for_update().limit(100)):
                try:
                    async with db.begin_nested():
                        run=await db.get(Run,row.run_id,with_for_update={'nowait':True} if binding.connection_id else True) if row.run_id else None
                except DBAPIError as error:
                    if binding.connection_id and getattr(error.orig,'sqlstate',None)=='55P03':continue
                    raise
                if run and run.status not in TERMINAL:continue
                row.body=None;row.purged_at=now();count+=1
                if run:
                    from pao.models import Message,RunEvent,AgentRun
                    run.prompt='[retention purged]';run.response='[retention purged]'
                    for message in await db.scalars(select(Message).where(Message.run_id==run.id)):message.content='[retention purged]'
                    for event in await db.scalars(select(RunEvent).where(RunEvent.run_id==run.id)):event.data={'retention_purged':True}
                    for agent in await db.scalars(select(AgentRun).where(AgentRun.run_id==run.id)):
                        agent.task='[retention purged]';agent.output='[retention purged]'
                    # RunKnowledge stores immutable source references (no quote,
                    # customer transcript or score). Keep its audit provenance.
            for row in await db.scalars(select(ChannelOutbox).where(ChannelOutbox.binding_id==binding.id,ChannelOutbox.created_at<cutoff,ChannelOutbox.body.is_not(None)).with_for_update().limit(100)):
                if row.status=='sending':continue
                row.body=None
                if row.status in ('queued','failed'):row.status='cancelled';row.error_code='retention_expired'
    return {'purged':count}

class RetryableDelivery(Exception):
    """Transport positively confirmed no send (e.g. HTTP429); safe backoff only."""

async def result_visible(db,binding,row,who,delivery=False):
    """Revalidate cached results against current scope and source visibility."""
    if row.request_key.startswith('ads-report:') and binding.connection_id is not None:
        from .telegram_reports import visible
        if who.id!=binding.actor_id:return False
        return await visible(db,binding,row)
    if not row.request_key.startswith('result:'):return True
    try:
        suffix=row.request_key.removeprefix('result:');ident,separator,part=suffix.partition(':p:')
        ident=str(UUID(ident))
        if separator and (not part.isdigit() or str(int(part))!=part):return False
    except ValueError:return False
    run=await db.get(Run,ident,populate_existing=True)
    if (not run or run.workspace_id!=binding.workspace_id or run.session_id!=binding.session_id or
        (run.channel_context or {}).get('binding_id')!=binding.id):return False
    from pao.modules.knowledge.conversations import run_visible
    if not await run_visible(db,run,who):return False
    if delivery:
        try:await check_run(db,run)
        except PermissionError:return False
    body=run.response or 'Lượt đã kết thúc: '+run.status
    if body=='[retention purged]':return False
    parts=[];current='';units=0
    if binding.channel=='telegram' and len(body.encode('utf-16-le'))//2>3500:
        for char in body:
            width=len(char.encode('utf-16-le'))//2
            if units+width>3500:parts.append(current);current='';units=0
            current+=char;units+=width
        if current:parts.append(current)
    else:parts=[body]
    index=int(part) if separator else 0
    return index<len(parts) and (separator or len(parts)==1) and row.body==parts[index]

async def send_one(send,channel='telegram'):
    if not settings().channels_enabled or (channel=='telegram' and not settings().telegram_enabled):return
    # Persist claim before provider invocation; a crash after claim is unknown,
    # not an invitation to send the same message again.
    async with Session.begin() as db:
        if channel=='telegram':
            from .telegram_helpers import legacy_blocked
            if await legacy_blocked(db):return
        candidate=await db.scalar(select(ChannelOutbox).join(ChannelBinding,ChannelBinding.id==ChannelOutbox.binding_id).where(
            ChannelBinding.channel==channel,ChannelBinding.connection_id.is_(None),ChannelOutbox.status=='queued',ChannelOutbox.available_at<=now()).order_by(ChannelOutbox.created_at).limit(1))
        if not candidate:return
        binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.id==candidate.binding_id).with_for_update())
        row=await db.get(ChannelOutbox,candidate.id,with_for_update=True,populate_existing=True)
        if row.status!='queued':return
        try:
            await actor(db,binding)
            if not await result_visible(db,binding,row,Principal(binding.actor_id,0),True):raise HTTPException(403,'channel_result_revoked')
            if row.kind=='auto' and binding.mode!='auto':raise HTTPException(403,'channel_quiet')
            if channel=='telegram' and not binding.outbound_confirmed:raise HTTPException(403,'destination_not_confirmed')
        except HTTPException:row.status='cancelled';return
        if row.attempts>=3:row.status='failed';row.error_code='attempts_exhausted';return
        row.status='sending';row.attempts+=1;row.updated_at=now();ident=row.id
    async with Session.begin() as db:
        binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.id==candidate.binding_id).with_for_update())
        row=await db.get(ChannelOutbox,ident,with_for_update=True)
        try:
            await actor(db,binding)
            if not await result_visible(db,binding,row,Principal(binding.actor_id,0),True):raise HTTPException(403,'channel_result_revoked')
            if row.kind=='auto' and binding.mode!='auto':raise HTTPException(403,'channel_quiet')
            if channel=='telegram':
                if not settings().telegram_enabled or not binding.outbound_confirmed:raise HTTPException(403,'destination_not_confirmed')
                peer=await db.get(TelegramPeer,binding.peer_id)
                if not peer or not peer.enabled or peer.user_id!=binding.actor_id or peer.workspace_id!=binding.workspace_id:raise HTTPException(403,'channel_peer_changed')
                payload={'chat_id':peer.chat_id,'text':row.body or '', 'link_preview_options':{'is_disabled':True}}
            else:payload={'text':row.body}
        except HTTPException:row.status='cancelled';return
        import asyncio
        try:
            result=await asyncio.wait_for(send(payload),10)
            remote=str(result['message_id'])
            if not remote or len(remote)>64:raise ValueError('invalid receipt')
            row.status='sent';row.remote_id=remote;row.error_code=None
        except RetryableDelivery:
            row.status='queued' if row.attempts<3 else 'failed';row.error_code='provider_retryable'
            row.available_at=now()+timedelta(seconds=2**row.attempts)
        except Exception:row.status='unknown';row.error_code='provider_delivery_uncertain'
        row.updated_at=now()

async def reconcile_stale(connection_id=None):
    async with Session.begin() as db:
        query=select(ChannelOutbox).where(ChannelOutbox.status=='sending',ChannelOutbox.updated_at<now()-timedelta(minutes=2))
        if connection_id is not None:query=query.where(ChannelOutbox.connection_id==connection_id)
        for row in await db.scalars(query.with_for_update(skip_locked=True).limit(100)):
            row.status='unknown';row.error_code='claim_interrupted';row.updated_at=now()

async def telegram_ingest(update,redis):
    callback=update.get('callback_query')
    if callback is not None and not isinstance(callback,dict):return False
    message=update.get('message') or (callback or {}).get('message') or {}
    if not isinstance(message,dict):return False
    sender=(callback or {}).get('from') or message.get('from') or {}
    chat=message.get('chat') or {}
    if not isinstance(sender,dict) or not isinstance(chat,dict):return False
    if chat.get('type')!='private' or sender.get('is_bot'):return False
    external=str(sender.get('id'))+':'+str(chat.get('id'))
    async with Session.begin() as db:
        binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.channel=='telegram',ChannelBinding.connection_id.is_(None),ChannelBinding.identity_hash==identity('telegram',external)).with_for_update())
        if not binding:
            # A rotated HMAC key must not route a bound peer into legacy authority.
            previous=await db.scalar(select(ChannelBinding.id).join(TelegramPeer,TelegramPeer.id==ChannelBinding.peer_id).where(
                ChannelBinding.channel=='telegram',ChannelBinding.connection_id.is_(None),TelegramPeer.connection_id.is_(None),TelegramPeer.telegram_user_id==str(sender.get('id')),TelegramPeer.chat_id==str(chat.get('id'))))
            return bool(previous)
        if not settings().channels_enabled:return True  # No fallback into legacy authority.
        if update.get('callback_query'):return binding.kind=='customer' or binding.mode!='auto' or not binding.enabled
        text=message.get('text')
        if not isinstance(text,str) or not text.strip() or len(text)>2000:return True
        try:await ingest(db,binding,str(update['update_id']),text,redis)
        except HTTPException as exc:
            if exc.status_code not in (403,409,429,503):raise
            # Revocation/quiet/grounding gates must never fall back to legacy.
            # A partially admitted receipt remains a non-executable inbox item.
            row=await db.scalar(select(ChannelInbound).where(ChannelInbound.binding_id==binding.id,ChannelInbound.external_key==digest(str(update['update_id']))))
            if row and not row.run_id:row.status='blocked'
        return True
