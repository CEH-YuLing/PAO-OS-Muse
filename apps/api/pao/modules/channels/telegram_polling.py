"""Bounded S3.2C polling adapter. Internal infrastructure, not a public API.

No daemon/import side effects, host credential, send method or implicit enable.
Each turn owns the actual bot's PG lease; the durable cursor is the only ACK.
Worker scheduling, webhook ingress and outbound integration are separate gates.
"""
import asyncio
from dataclasses import dataclass
import json
from datetime import timedelta
import httpx
from pao.models import now
from pao.credential_guard import require_clean_payload
from . import telegram_runtime as rt,telegram_store as store,telegram_identity as identities,telegram_scoped as scoped

BATCH_LIMIT=5
TURN_SECONDS=30
POLL_SECONDS=5
MAX_POLL_BYTES=2*1024*1024


@dataclass(frozen=True,slots=True)
class PollResult:
    processed:int
    next_offset:int


async def _updates(pin,capsule,offset,transport):
    """Only getUpdates, fixed origin/body, bounded response and no retry.

    Caller holds the real PG bot lease plus fresh scope/profile locks. Raw
    updates never escape to a router, logging, task result or exception.
    """
    secret=None
    try:
        rt._enabled()
        secret=rt._open_credentials(pin,capsule)
        inner=transport if transport is not None else httpx.AsyncHTTPTransport(retries=0,trust_env=False)
        wrapper=rt._TokenTransport(secret.get_secret_value(),inner)
        with rt._private_io():
            async with httpx.AsyncClient(transport=wrapper,timeout=10,trust_env=False,follow_redirects=False) as client:
                async with client.stream('POST','https://api.telegram.org/bot-redacted/getUpdates',json={
                    'offset':offset,'timeout':POLL_SECONDS,'limit':BATCH_LIMIT,'allowed_updates':['message','callback_query']}) as response:
                    if (response.status_code!=200 or
                        response.headers.get('content-type','').split(';')[0].strip().lower()!='application/json'):
                        raise rt.TelegramRuntimeError('telegram_poll_provider_unavailable')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        raw.extend(chunk)
                        if len(raw)>MAX_POLL_BYTES:raise rt.TelegramRuntimeError('telegram_poll_response_limit')
                    data=json.loads(raw);require_clean_payload(data,secret.get_secret_value())
                    if type(data) is not dict or data.get('ok') is not True:raise ValueError()
                    updates=data.get('result')
                    if type(updates) is not list or len(updates)>BATCH_LIMIT:raise ValueError()
                    previous=offset-1
                    # Reject a malformed batch before admitting any of its items.
                    for update in updates:
                        if type(update) is not dict:raise ValueError()
                        ident=store._integer(update.get('update_id'))
                        if ident<=previous:raise ValueError()
                        previous=ident
                    return updates
    except asyncio.CancelledError:raise
    except rt.TelegramRuntimeError:raise
    except Exception:raise rt.TelegramRuntimeError('telegram_poll_provider_invalid') from None
    finally:secret=None


async def _fetch(lease,transport,expected_generation=None):
    async with store._transaction(lease) as db:
        await identities.resolve_identity(db,lease.pin)
        profile=await store._profile(db,lease.pin,expected_generation)
        if not profile or profile.status!='enabled':raise rt.TelegramRuntimeError('telegram_channel_disabled')
        if profile.transport_mode!='polling':raise rt.TelegramRuntimeError('telegram_poll_mode_conflict')
        # Telegram may randomize IDs after a quiet week. Offset zero never drops
        # pending updates; a durable new epoch separates reused IDs. Provider
        # retains updates <=24h, well below this seven-day receipt horizon.
        if profile.cursor_touched_at<=now()-timedelta(days=7):
            profile.cursor_epoch+=1;profile.next_offset=0;profile.cursor_touched_at=now()
            await db.flush()
        capsule=store._unseal(lease.pin,profile.generation,profile.token_ciphertext)
        info=await rt._metadata(lease.pin,capsule,'getWebhookInfo',transport)
        if info.webhook_present:raise rt.TelegramRuntimeError('telegram_poll_webhook_conflict')
        rt._enabled();await rt._require_lease(db,lease);await rt._scope(db,lease.pin)
        updates=await _updates(lease.pin,capsule,profile.next_offset,transport)
        return profile.generation,profile.next_offset,updates


async def poll_once(pin,redis,*,transport=None):
    """At most five updates/30s/one DB slot; caller yields before another turn.

    No caller-supplied offset/generation/token/mode. Native profile resolves all
    of them. Only the next turn's getUpdates ACKs committed receipts. A crash,
    cancelled turn or rejected admission cannot advance an in-memory cursor.
    Control/revocation can interleave between fetch and individual admissions;
    every admission rechecks authority and generation in the existing service.
    The injected HTTP transport is trusted test infrastructure, not user input.
    """
    rt._enabled()
    if redis is None:raise rt.TelegramRuntimeError('telegram_poll_queue_unavailable')
    try:
        async with asyncio.timeout(TURN_SECONDS),rt.own_bot(pin) as lease:
            return await _poll_owned(lease,redis,transport=transport)
    except TimeoutError:raise rt.TelegramRuntimeError('telegram_poll_turn_timeout') from None


async def _poll_owned(lease,redis,*,expected_generation=None,transport=None,checkpoint=None):
    """Worker keeps one actual-bot lease across polling/collection/sending."""
    async with asyncio.timeout(TURN_SECONDS):
        if checkpoint:await checkpoint()
        generation,offset,updates=await _fetch(lease,transport,expected_generation)
        for update in updates:
            if checkpoint:await checkpoint()
            result=await scoped.ingest_update(lease,generation=generation,expected_offset=offset,update=update,redis=redis)
            offset=result.next_offset
        return PollResult(len(updates),offset)
