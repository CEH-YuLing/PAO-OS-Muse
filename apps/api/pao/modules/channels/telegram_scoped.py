"""S3.2B scoped admission/outbox primitives. No router, polling or HTTP sends.

Internal callers must supply updates from the verified bot adapter, never a web
body claiming a Telegram identity. C owns transport/epoch wiring; S3.3 owns setup.
"""
from dataclasses import asdict,dataclass
from datetime import timedelta
import hashlib,json,re
from fastapi import HTTPException
from sqlalchemy import select,or_,cast,String,literal,text
from pao.auth import Principal
from pao.models import (TelegramConnection,TelegramPeer,Member,User,ChatSession,Brain,BrainMember,
    ChannelBinding,ChannelInbound,ChannelOutbox,TelegramRuntimeReceipt,Run,now)
from . import telegram_runtime as rt,telegram_store as store,telegram_identity as identities


async def control_profile(lease,*,generation,request_key,action,consent=False,transport=None):
    """Explicit internal enable/disable, fresh getMe on enable, no transport start."""
    store._integer(generation,1);key=store._request_key(request_key)
    if generation>=2**31-1 or action not in ('enable','disable'):raise rt.TelegramRuntimeError('telegram_control_invalid')
    if consent is not True:raise rt.TelegramRuntimeError('telegram_control_consent_required')
    fingerprint=store._fingerprint(lease.pin,action,generation,key)
    target='enabled' if action=='enable' else 'disabled'
    async with store._transaction(lease) as db:
        await identities.resolve_identity(db,lease.pin)
        saved=await store._saved(db,lease.pin,key,fingerprint);row=await store._profile(db,lease.pin)
        if saved:
            if row is None or row.generation!=saved.generation or row.status!=target:
                raise rt.TelegramRuntimeError('telegram_store_request_superseded')
            return store._view(row)
        if row is None or row.generation!=generation:raise rt.TelegramRuntimeError('telegram_store_generation_stale')
        if row.status=='revoked' or row.status==target:raise rt.TelegramRuntimeError('telegram_control_state_invalid')
        capsule=store._unseal(lease.pin,generation,row.token_ciphertext)
        if action=='enable':await rt._metadata(lease.pin,capsule,'getMe',transport)
        await rt._require_lease(db,lease);await rt._scope(db,lease.pin)
        token=rt._open_credentials(lease.pin,capsule)
        row.generation+=1;row.status=target;row.token_ciphertext=store._seal(lease.pin,row.generation,token)
        await store._audit(db,lease.pin,row,key,fingerprint,target)
        return store._view(row)


async def context(db,binding):
    """Fresh canonical scope. Bot owner authority does not replace actor rights."""
    rt._enabled()
    connection=await db.get(TelegramConnection,binding.connection_id,populate_existing=True)
    if not connection or connection.workspace_id!=binding.workspace_id:
        raise rt.TelegramRuntimeError('telegram_channel_scope_changed')
    identity=await db.scalar(select(identities.TelegramBotIdentity).where(
        identities.TelegramBotIdentity.connection_id==connection.id))
    if not identity:raise rt.TelegramRuntimeError('telegram_identity_unverified')
    pin=rt.RuntimePin(connection.workspace_id,connection.id,connection.owner_id,connection.version,identity.bot_user_id)
    await identities.resolve_identity(db,pin)
    # Shared profile locks serialize admission against generation changes. Do not
    # take binding/session locks here: native HTTP admission locks session first.
    row=await db.scalar(select(store.TelegramRuntimeProfile).where(store.TelegramRuntimeProfile.connection_id==connection.id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    if not row or row.status!='enabled':raise rt.TelegramRuntimeError('telegram_channel_disabled')
    member=await db.get(Member,(binding.workspace_id,binding.actor_id),with_for_update={'read':True},populate_existing=True)
    user=await db.get(User,binding.actor_id,with_for_update={'read':True},populate_existing=True)
    current=await db.get(ChannelBinding,binding.id,populate_existing=True)
    peer=await db.get(TelegramPeer,binding.peer_id,populate_existing=True) if binding.peer_id else None
    from .service import identity as identity_hash
    if (not current or not current.enabled or not member or member.role=='viewer' or not user or not user.active or
        member.user_id!=current.actor_id or member.workspace_id!=pin.workspace_id or user.id!=current.actor_id or
        current.workspace_id!=pin.workspace_id or current.connection_id!=pin.connection_id or current.channel!='telegram' or
        not peer or not peer.enabled or peer.connection_id!=pin.connection_id or peer.workspace_id!=pin.workspace_id or
        peer.user_id!=current.actor_id or current.identity_hash!=identity_hash('telegram',peer.telegram_user_id+':'+peer.chat_id,pin.connection_id)):
        raise rt.TelegramRuntimeError('telegram_channel_actor_revoked')
    if not re.fullmatch(r'[1-9][0-9]{0,15}',peer.telegram_user_id) or peer.chat_id!=peer.telegram_user_id:
        raise rt.TelegramRuntimeError('telegram_private_destination_required')
    if current.kind=='customer' and member.role!='operator':raise rt.TelegramRuntimeError('telegram_customer_role_invalid')
    revision=None
    if current.brain_id:
        # Refresh grants as well as Brain: a cached grant is not current access.
        await db.get(Brain,current.brain_id,populate_existing=True)
        await db.get(BrainMember,(current.brain_id,current.actor_id),populate_existing=True)
        from pao.modules.brains.access import require_brain
        brain=await require_brain(db,Principal(current.actor_id,0),current.brain_id,True)
        if brain.workspace_id!=pin.workspace_id or (current.kind=='customer' and brain.legacy_default):
            raise rt.TelegramRuntimeError('telegram_channel_brain_revoked')
        revision=brain.revision
    elif current.kind=='customer':raise rt.TelegramRuntimeError('telegram_channel_brain_required')
    session=None
    if current.session_id:
        session=await db.get(ChatSession,current.session_id,populate_existing=True)
        if (not session or session.workspace_id!=pin.workspace_id or session.user_id!=current.actor_id or session.brain_id!=current.brain_id):
            raise rt.TelegramRuntimeError('telegram_channel_session_changed')
    return {**asdict(pin),'schema':1,'generation':row.generation,'binding_id':current.id,
        'binding_version':current.version,'actor_id':current.actor_id,'kind':current.kind,
        'peer_id':peer.id,'telegram_user_id':peer.telegram_user_id,'chat_id':peer.chat_id,
        'brain_id':current.brain_id,'brain_revision':revision,'session_id':current.session_id,
        'session_policy':None if not session else hashlib.sha256(json.dumps({
            'memory':session.memory_enabled,'knowledge':session.knowledge_enabled,'scope':session.knowledge_scope},sort_keys=True).encode()).hexdigest()}


@dataclass(frozen=True,slots=True)
class IngressResult:
    disposition:str
    next_offset:int
    run_id:str | None=None


async def ingest_update(lease,*,generation,expected_offset,update,redis,webhook=False):
    """Atomic existing Channels admission + receipt + cursor; no eager enqueue."""
    store._integer(generation,1);store._integer(expected_offset)
    try:
        raw=json.dumps(update,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
        if type(update) is not dict or len(raw)>2*1024*1024:raise ValueError()
        update_id=store._integer(update.get('update_id'))
        fingerprint=hashlib.sha256(raw).hexdigest()
        oversized=len(raw)>rt.MAX_BYTES
    except Exception:raise rt.TelegramRuntimeError('telegram_update_invalid') from None
    async with store._transaction(lease) as db:
        # Transient control/worker contention rolls back admission and cursor;
        # it must not become a permanently blocked receipt or a lock cycle.
        await db.execute(text("SET LOCAL lock_timeout='200ms'"))
        await identities.resolve_identity(db,lease.pin)
        profile=await store._profile(db,lease.pin,generation)
        if not profile or profile.status!='enabled':raise rt.TelegramRuntimeError('telegram_channel_disabled')
        if profile.next_offset!=expected_offset:raise rt.TelegramRuntimeError('telegram_store_cursor_stale')
        if webhook and profile.cursor_touched_at<=now()-timedelta(days=7):
            profile.cursor_epoch+=1;profile.next_offset=0;profile.cursor_touched_at=now()
            await db.flush()
        previous=await db.scalar(select(TelegramRuntimeReceipt).where(
            TelegramRuntimeReceipt.connection_id==lease.pin.connection_id,TelegramRuntimeReceipt.cursor_epoch==profile.cursor_epoch,
            TelegramRuntimeReceipt.update_id==update_id))
        if previous:
            if previous.content_hash!=fingerprint:raise rt.TelegramRuntimeError('telegram_store_update_conflict')
            return IngressResult('duplicate',profile.next_offset)
        if update_id<expected_offset and not webhook:raise rt.TelegramRuntimeError('telegram_store_update_behind_cursor')
        message=None if oversized else update.get('message');reason='malformed' if oversized else 'unsupported';incoming=None
        if type(message) is dict and not any(k in update for k in ('callback_query','edited_message','channel_post')):
            sender=message.get('from');chat=message.get('chat');body=message.get('text')
            if (type(sender) is dict and type(chat) is dict and chat.get('type')=='private' and sender.get('is_bot') is False and
                type(sender.get('id')) is int and type(chat.get('id')) is int and
                0<sender['id']<2**53 and chat['id']==sender['id']):
                if type(body) is str and body.strip() and len(body)<=2000:
                    from . import service
                    from .telegram_setup import observe_pairing
                    pairing=await observe_pairing(db,lease.pin,profile,body,str(sender['id']),redis)
                    binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.connection_id==lease.pin.connection_id,
                        ChannelBinding.workspace_id==lease.pin.workspace_id,ChannelBinding.channel=='telegram',
                        ChannelBinding.identity_hash==service.identity('telegram',str(sender['id'])+':'+str(chat['id']),lease.pin.connection_id))
                        .with_for_update())
                    reason='unlinked'
                    if binding and not pairing:
                        try:
                            external=str(update_id) if profile.cursor_epoch==0 else str(profile.cursor_epoch)+':'+str(update_id)
                            async with db.begin_nested():incoming=await service.ingest(db,binding,external,body,redis)
                            reason='inbound'
                        except (HTTPException,rt.TelegramRuntimeError):reason='blocked'
                else:reason='malformed'
        db.add(TelegramRuntimeReceipt(workspace_id=lease.pin.workspace_id,connection_id=lease.pin.connection_id,
            generation=generation,cursor_epoch=profile.cursor_epoch,update_id=update_id,content_hash=fingerprint,reason=reason,inbound_id=incoming.id if incoming else None))
        await db.flush();profile.next_offset=max(profile.next_offset,update_id+1);profile.cursor_touched_at=now();await db.flush()
        return IngressResult(incoming.status if incoming else reason,profile.next_offset,incoming.run_id if incoming else None)


async def collect_results(lease,*,generation):
    """Bounded scoped result collection using existing visibility and outbox."""
    from . import service
    from pao.modules.conversations.state import TERMINAL
    async with store._transaction(lease) as db:
        await db.execute(text("SET LOCAL lock_timeout='200ms'"))
        profile=await store._profile(db,lease.pin,generation)
        if not profile or profile.status!='enabled':raise rt.TelegramRuntimeError('telegram_channel_disabled')
        result_key=literal('result:')+cast(ChannelInbound.run_id,String)
        delivered=select(ChannelOutbox.id).where(ChannelOutbox.binding_id==ChannelInbound.binding_id,
            or_(ChannelOutbox.request_key==result_key,ChannelOutbox.request_key==result_key+literal(':p:0'))).exists()
        rows=list(await db.scalars(select(ChannelInbound).join(Run,Run.id==ChannelInbound.run_id).where(
            ChannelInbound.connection_id==lease.pin.connection_id,ChannelInbound.status=='accepted',
            ChannelInbound.purged_at.is_(None),Run.status.in_(TERMINAL),~delivered).order_by(ChannelInbound.created_at,ChannelInbound.id).limit(100)))
        count=0
        for incoming in rows:
            key='result:'+incoming.run_id
            exists=await db.scalar(select(ChannelOutbox.id).where(ChannelOutbox.binding_id==incoming.binding_id,
                ChannelOutbox.request_key.in_((key,key+':p:0'))).limit(1))
            if exists:continue
            binding=await db.get(ChannelBinding,incoming.binding_id);run=await db.get(Run,incoming.run_id)
            try:
                await service.check_run(db,run)
                from pao.modules.knowledge.conversations import run_visible
                if not await run_visible(db,run,Principal(binding.actor_id,0)):raise PermissionError()
                await service.queue(db,binding,key,run.response or 'Lượt đã kết thúc: '+run.status)
                count+=1
            except (PermissionError,HTTPException,rt.TelegramRuntimeError):incoming.status='blocked'
        return count


@dataclass(frozen=True,slots=True)
class DeliveryClaim:
    outbox_id:str
    attempt:int
    connection_id:str


async def _delivery(db,lease,claim_or_id):
    ident=claim_or_id.outbox_id if isinstance(claim_or_id,DeliveryClaim) else claim_or_id
    row=await db.scalar(select(ChannelOutbox).where(ChannelOutbox.id==ident,
        ChannelOutbox.workspace_id==lease.pin.workspace_id,ChannelOutbox.connection_id==lease.pin.connection_id).with_for_update())
    if not row:raise rt.TelegramRuntimeError('telegram_delivery_not_found')
    return row


async def _check_delivery(db,lease,row,generation):
    from . import service
    profile=await store._profile(db,lease.pin,generation)
    if not profile or profile.status!='enabled':raise rt.TelegramRuntimeError('telegram_channel_disabled')
    binding=await db.get(ChannelBinding,row.binding_id,populate_existing=True)
    expected=await context(db,binding)
    if not row.telegram_context or row.telegram_context!=expected or not binding.outbound_confirmed:
        raise rt.TelegramRuntimeError('telegram_delivery_scope_changed')
    if row.kind=='auto' and binding.mode!='auto':raise rt.TelegramRuntimeError('telegram_delivery_quiet')
    if row.body is None or row.content_hash!=service.digest({'body':row.body,'kind':row.kind}):
        raise rt.TelegramRuntimeError('telegram_delivery_content_changed')
    if not await service.result_visible(db,binding,row,Principal(binding.actor_id,0),True):
        raise rt.TelegramRuntimeError('telegram_delivery_result_revoked')
    return profile


async def claim_delivery(lease,*,generation,outbox_id):
    """Persist sending before C may invoke provider. Never select legacy queues."""
    async with store._transaction(lease) as db:
        row=await _delivery(db,lease,outbox_id)
        return await _claim_delivery_row(db,lease,row,generation)


async def _claim_delivery_row(db,lease,row,generation):
    """One claim writer; C first acquires its nonblocking authority fence."""
    if row.workspace_id!=lease.pin.workspace_id or row.connection_id!=lease.pin.connection_id:
        raise rt.TelegramRuntimeError('telegram_delivery_not_found')
    if row.status!='queued' or row.available_at>now():return None
    try:profile=await _check_delivery(db,lease,row,generation)
    except (rt.TelegramRuntimeError,HTTPException):row.status='cancelled';row.error_code='scope_revoked';return None
    if profile.cooldown_until and profile.cooldown_until>now():return None
    if row.attempts>=3:row.status='failed';row.error_code='attempts_exhausted';return None
    row.status='sending';row.attempts+=1;row.updated_at=now()
    return DeliveryClaim(row.id,row.attempts,lease.pin.connection_id)


async def preflight_delivery(lease,*,generation,claim):
    """Recheck after durable claim. Returns payload only to trusted C adapter."""
    if not isinstance(claim,DeliveryClaim) or claim.connection_id!=lease.pin.connection_id:
        raise rt.TelegramRuntimeError('telegram_delivery_claim_invalid')
    async with store._transaction(lease) as db:
        row=await _delivery(db,lease,claim)
        if row.status!='sending' or row.attempts!=claim.attempt:raise rt.TelegramRuntimeError('telegram_delivery_claim_stale')
        try:profile=await _check_delivery(db,lease,row,generation)
        except (rt.TelegramRuntimeError,HTTPException):row.status='cancelled';row.error_code='scope_revoked';return None
        if profile.cooldown_until and profile.cooldown_until>now():
            row.status='queued';row.available_at=profile.cooldown_until;row.error_code='bot_cooldown';return None
        return {'chat_id':row.telegram_context['chat_id'],'text':row.body,'link_preview_options':{'is_disabled':True}}


async def finish_delivery(lease,*,claim,outcome,remote_id=None,retry_after=0):
    """Trusted transport outcome, not a public acknowledgement endpoint.

    Only confirmed no-send may retry. Uncertain outcomes are terminal unknown.
    """
    if not isinstance(claim,DeliveryClaim) or claim.connection_id!=lease.pin.connection_id:
        raise rt.TelegramRuntimeError('telegram_delivery_outcome_invalid')
    async with store._transaction(lease) as db:
        row=await _delivery(db,lease,claim)
        await _apply_delivery_outcome(db,lease,row,claim=claim,outcome=outcome,remote_id=remote_id,retry_after=retry_after)


async def _apply_delivery_outcome(db,lease,row,*,claim,outcome,remote_id=None,retry_after=0):
    """Single outcome writer, also used with C's authority/HTTP transaction held."""
    if (not isinstance(claim,DeliveryClaim) or claim.connection_id!=lease.pin.connection_id or
        row.id!=claim.outbox_id or row.connection_id!=claim.connection_id or row.workspace_id!=lease.pin.workspace_id or
        outcome not in ('sent','unknown','retryable','rejected')):
        raise rt.TelegramRuntimeError('telegram_delivery_outcome_invalid')
    if outcome=='sent' and (type(remote_id) is not str or not re.fullmatch(r'[1-9][0-9]{0,19}',remote_id)):
        raise rt.TelegramRuntimeError('telegram_delivery_outcome_invalid')
    if outcome=='retryable' and (type(retry_after) is not int or not 1<=retry_after<=3600):
        raise rt.TelegramRuntimeError('telegram_delivery_outcome_invalid')
    if row.status!='sending' or row.attempts!=claim.attempt:raise rt.TelegramRuntimeError('telegram_delivery_claim_stale')
    row.updated_at=now()
    if outcome=='sent':row.status='sent';row.remote_id=remote_id;row.error_code=None
    elif outcome=='unknown':row.status='unknown';row.error_code='provider_delivery_uncertain'
    elif outcome=='rejected':row.status='failed';row.error_code='provider_rejected'
    else:
        row.status='queued' if row.attempts<3 else 'failed';row.error_code='provider_retryable'
        row.available_at=now()+timedelta(seconds=retry_after)
        profile=await store._profile(db,lease.pin)
        if profile:profile.cooldown_until=max(profile.cooldown_until or row.available_at,row.available_at)
