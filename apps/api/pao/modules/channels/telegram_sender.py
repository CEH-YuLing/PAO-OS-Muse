"""Internal bounded S3.2C sender; durable claim and fenced HTTP invocation.

No route/daemon, implicit activation, host credentials or caller-provided payload.
Only trusted infrastructure may inject an HTTP transport. No automatic resend.
"""
import asyncio,json
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from pao.models import (Member,User,TelegramPeer,ChannelBinding,ChannelOutbox,ChannelInbound,ChatSession,
    Brain,BrainMember,Run,RunKnowledge,KnowledgeChunk,KnowledgeVersion,KnowledgeSource,KnowledgeIngestion,
    BrainFile,BrainNote,BrainNoteVersion,now)
from pao.credential_guard import require_clean_payload
from . import telegram_runtime as rt,telegram_store as store,telegram_scoped as scoped,telegram_identity as identities


@dataclass(frozen=True,slots=True)
class SendResult:
    disposition:str


@dataclass(frozen=True,slots=True)
class _Outcome:
    kind:str
    remote_id:str|None=None
    retry_after:int=0


async def _locked(db,model,key,*,write=False,required=True):
    """No waiting after the owner boundary: contention cannot create a cycle.

    Revoke/retention/worker paths have different established lock orders. NOWAIT
    aborts this entire pre-HTTP transaction instead of holding half a fence while
    waiting on them. Owner scope is acquired first, with no delivery rows held.
    """
    try:
        row=await db.get(model,key,with_for_update={'read':not write,'nowait':True},populate_existing=True)
    except DBAPIError as error:
        if getattr(error.orig,'sqlstate',None)=='55P03':
            raise rt.TelegramRuntimeError('telegram_delivery_lock_busy') from None
        raise
    if required and row is None:raise rt.TelegramRuntimeError('telegram_delivery_scope_changed')
    return row


async def _evidence_fence(db,run):
    """Freeze mutable citation/ACL dependencies before existing visibility check."""
    if not (run.brain_context or {}).get('knowledge'):return
    record=await db.scalar(select(RunKnowledge).where(RunKnowledge.run_id==run.id))
    if not record:raise rt.TelegramRuntimeError('telegram_delivery_evidence_missing')
    record=await _locked(db,RunKnowledge,record.id)
    if type(record.evidence) is not list or len(record.evidence)>4:
        raise rt.TelegramRuntimeError('telegram_delivery_evidence_invalid')
    from pao.modules.knowledge.service import PARSER_VERSION
    for ref in record.evidence:
        if type(ref) is not dict:raise rt.TelegramRuntimeError('telegram_delivery_evidence_invalid')
        try:cid=str(UUID(ref['chunk_id']))
        except Exception:raise rt.TelegramRuntimeError('telegram_delivery_evidence_invalid') from None
        chunk=await _locked(db,KnowledgeChunk,cid)
        version=await _locked(db,KnowledgeVersion,chunk.version_id)
        source=await _locked(db,KnowledgeSource,version.source_id)
        if chunk.brain_id!=run.brain_id or source.brain_id!=run.brain_id:
            raise rt.TelegramRuntimeError('telegram_delivery_evidence_invalid')
        job=await db.scalar(select(KnowledgeIngestion).where(KnowledgeIngestion.version_id==version.id,
            KnowledgeIngestion.parser_version==PARSER_VERSION,KnowledgeIngestion.status=='completed'))
        if not job:raise rt.TelegramRuntimeError('telegram_delivery_evidence_missing')
        await _locked(db,KnowledgeIngestion,job.id)
        if source.file_id:await _locked(db,BrainFile,source.file_id)
        else:
            await _locked(db,BrainNote,source.note_id)
            await _locked(db,BrainNoteVersion,(source.note_id,version.origin_version))


async def _fence(db,row):
    binding=await _locked(db,ChannelBinding,row.binding_id)
    await _locked(db,Member,(binding.workspace_id,binding.actor_id))
    await _locked(db,User,binding.actor_id)
    if binding.peer_id:await _locked(db,TelegramPeer,binding.peer_id)
    if binding.session_id:
        session=await _locked(db,ChatSession,binding.session_id)
        if session.archived_at:raise rt.TelegramRuntimeError('telegram_delivery_scope_changed')
    if binding.brain_id:
        await _locked(db,Brain,binding.brain_id)
        await _locked(db,BrainMember,(binding.brain_id,binding.actor_id),required=False)
    if row.request_key.startswith('ads-report:'):
        from pao.models import AdReport,MetaConnection
        from .telegram_reports import report_id
        report=await _locked(db,AdReport,report_id(row.request_key))
        await _locked(db,MetaConnection,report.connection_id)
    if row.request_key.startswith('result:'):
        try:ident=str(UUID(row.request_key.removeprefix('result:').partition(':p:')[0]))
        except Exception:raise rt.TelegramRuntimeError('telegram_delivery_scope_changed') from None
        run=await _locked(db,Run,ident)
        from pao.modules.conversations.state import TERMINAL
        if run.status not in TERMINAL:raise rt.TelegramRuntimeError('telegram_delivery_scope_changed')
        incoming=await db.scalar(select(ChannelInbound).where(ChannelInbound.run_id==run.id))
        if incoming:await _locked(db,ChannelInbound,incoming.id)
        await _evidence_fence(db,run)
    return row


async def _profile(db,lease):
    ident=await db.scalar(select(store.TelegramRuntimeProfile.id).where(
        store.TelegramRuntimeProfile.connection_id==lease.pin.connection_id))
    if not ident:raise rt.TelegramRuntimeError('telegram_channel_disabled')
    return await _locked(db,store.TelegramRuntimeProfile,ident,write=True)


async def _row(db,lease,ident):
    row=await _locked(db,ChannelOutbox,ident,write=True)
    if row.workspace_id!=lease.pin.workspace_id or row.connection_id!=lease.pin.connection_id:
        raise rt.TelegramRuntimeError('telegram_delivery_not_found')
    return row


async def _claim(lease,generation,ident):
    async with store._transaction(lease) as db:
        await _profile(db,lease)
        row=await _row(db,lease,ident)
        if row.status!='queued' or row.available_at>now():return None
        try:await _fence(db,row)
        except (rt.TelegramRuntimeError,HTTPException) as error:
            if str(error)=='telegram_delivery_lock_busy':raise
            row.status='cancelled';row.error_code='scope_revoked';return None
        return await scoped._claim_delivery_row(db,lease,row,generation)


async def _send(pin,capsule,payload,transport):
    """Fixed sendMessage only; strict receipts, positive no-send or unknown.

    Raw provider errors/URLs/message bodies never leave this boundary. Even
    connect/5xx/parse failures are uncertain, never implicit retries.
    """
    secret=None
    try:
        rt._enabled()
        if not rt.settings().channels_enabled:return _Outcome('unknown')
        secret=rt._open_credentials(pin,capsule)
        require_clean_payload(payload,secret.get_secret_value())
        inner=transport if transport is not None else httpx.AsyncHTTPTransport(retries=0,trust_env=False)
        wrapper=rt._TokenTransport(secret.get_secret_value(),inner)
        with rt._private_io():
            async with httpx.AsyncClient(transport=wrapper,timeout=10,trust_env=False,follow_redirects=False) as client:
                async with client.stream('POST','https://api.telegram.org/bot-redacted/sendMessage',json=payload) as response:
                    if response.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':return _Outcome('unknown')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        raw.extend(chunk)
                        if len(raw)>rt.MAX_BYTES:return _Outcome('unknown')
                    data=json.loads(raw);require_clean_payload(data,secret.get_secret_value())
                    if type(data) is not dict:return _Outcome('unknown')
                    code=data.get('error_code')
                    if data.get('ok') is False and type(code) is int and code==response.status_code:
                        if code==429:
                            parameters=data.get('parameters');delay=parameters.get('retry_after') if type(parameters) is dict else None
                            if type(delay) is int and 1<=delay<=3600:return _Outcome('retryable',retry_after=delay)
                        elif code in (400,401,403,404):return _Outcome('rejected')
                    if response.status_code!=200 or data.get('ok') is not True:return _Outcome('unknown')
                    result=data.get('result')
                    if type(result) is not dict:return _Outcome('unknown')
                    mid=result.get('message_id');chat=result.get('chat');sender=result.get('from')
                    if (type(mid) is not int or not 0<mid<2**63 or type(chat) is not dict or
                        type(chat.get('id')) is not int or str(chat['id'])!=payload['chat_id'] or chat.get('type')!='private' or
                        type(sender) is not dict or type(sender.get('id')) is not int or str(sender['id'])!=pin.bot_user_id or
                        sender.get('is_bot') is not True or result.get('text')!=payload['text']):return _Outcome('unknown')
                    return _Outcome('sent',remote_id=str(mid))
    except asyncio.CancelledError:raise
    except Exception:return _Outcome('unknown')
    finally:secret=None


async def _invoke(lease,generation,claim,transport,*,checkpoint=None):
    async with store._transaction(lease) as db:
        # Owner -> profile first. Every additional row lock is NOWAIT. Existing
        # checks may read those rows again, but cannot add blocking lock edges.
        profile=await _profile(db,lease)
        row=await _row(db,lease,claim.outbox_id)
        if row.status!='sending' or row.attempts!=claim.attempt:
            raise rt.TelegramRuntimeError('telegram_delivery_claim_stale')
        try:
            await _fence(db,row)
            if not rt.settings().channels_enabled:raise rt.TelegramRuntimeError('telegram_delivery_channel_disabled')
            await scoped._check_delivery(db,lease,row,generation)
            if profile.cooldown_until and profile.cooldown_until>now():
                row.status='queued';row.available_at=profile.cooldown_until;row.error_code='bot_cooldown'
                return SendResult('deferred')
            capsule=store._unseal(lease.pin,generation,profile.token_ciphertext)
            payload={'chat_id':row.telegram_context['chat_id'],'text':row.body,'link_preview_options':{'is_disabled':True}}
            if not row.body or len(row.body.encode('utf-16-le'))//2>3500:
                raise rt.TelegramRuntimeError('telegram_delivery_content_changed')
        except (rt.TelegramRuntimeError,HTTPException) as error:
            if isinstance(error,rt.TelegramRuntimeError) and str(error)=='telegram_delivery_lock_busy':raise
            row.status='cancelled';row.error_code='scope_revoked';return SendResult('cancelled')
        rt._enabled();await rt._require_lease(db,lease)
        if checkpoint:await checkpoint()
        outcome=await _send(lease.pin,capsule,payload,transport)
        await scoped._apply_delivery_outcome(db,lease,row,claim=claim,outcome=outcome.kind,
            remote_id=outcome.remote_id,retry_after=outcome.retry_after)
        if outcome.kind in ('sent','unknown'):
            until=now()+timedelta(seconds=1)
            profile.cooldown_until=max(profile.cooldown_until or until,until)
        return SendResult(outcome.kind)


async def send_once(pin,outbox_id,*,transport=None):
    """One bounded delivery. Claim is durable BEFORE any provider invocation.

    Never adopt sending/unknown/staged rows, accept a payload/outcome from an API,
    or retry HTTP in this turn. A cancelled/failed post-claim transaction leaves
    sending; existing reconciliation changes it to unknown, not queued.
    """
    rt._enabled();store._request_key(outbox_id)
    if not rt.settings().channels_enabled:raise rt.TelegramRuntimeError('telegram_delivery_channel_disabled')
    try:
        async with asyncio.timeout(40),rt.own_bot(pin) as lease:
            return await _send_owned(lease,outbox_id,transport=transport)
    except TimeoutError:raise rt.TelegramRuntimeError('telegram_delivery_turn_timeout') from None


async def _send_owned(lease,outbox_id,*,expected_generation=None,transport=None,checkpoint=None):
    """Internal worker continuation; never acquires a second PG pool slot."""
    async with asyncio.timeout(40):
        try:
            async with store._transaction(lease) as db:
                await identities.resolve_identity(db,lease.pin)
                profile=await _profile(db,lease)
                if not profile or profile.status!='enabled':raise rt.TelegramRuntimeError('telegram_channel_disabled')
                if expected_generation is not None and profile.generation!=expected_generation:
                    raise rt.TelegramRuntimeError('telegram_store_generation_stale')
                generation=profile.generation
        except rt.TelegramRuntimeError as error:
            if str(error)!='telegram_delivery_lock_busy':raise
            return SendResult('deferred')
        try:claim=await _claim(lease,generation,outbox_id)
        except rt.TelegramRuntimeError as error:
            if str(error)!='telegram_delivery_lock_busy':raise
            return SendResult('deferred')
        if claim is None:return SendResult('noop')
        try:
            if checkpoint:return await _invoke(lease,generation,claim,transport,checkpoint=checkpoint)
            return await _invoke(lease,generation,claim,transport)
        except rt.TelegramRuntimeError as error:
            if str(error)!='telegram_delivery_lock_busy':raise
            # Only known pre-HTTP contention may retry via the shared writer.
            await scoped.finish_delivery(lease,claim=claim,outcome='retryable',retry_after=1)
            return SendResult('deferred')
