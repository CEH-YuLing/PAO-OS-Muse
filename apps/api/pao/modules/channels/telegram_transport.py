"""Explicit transport changes; no automatic provider mutation or fallback."""
import asyncio,hashlib,hmac,json,re,secrets
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter,HTTPException,Request
from sqlalchemy import select
from pao.db import Session
from pao.models import TelegramConnection,TelegramBotIdentity,TelegramRuntimeProfile
from pao.credential_guard import require_clean_payload
from . import telegram_runtime as rt,telegram_store as store,telegram_scoped as scoped

router=APIRouter(prefix='/v1/telegram/scoped',tags=['telegram-scoped'])


def hook_url(pin):
    base=rt.settings().telegram_public_base_url.rstrip('/')
    url=urlsplit(base)
    if (url.scheme!='https' or not url.hostname or url.username or url.password or
        url.query or url.fragment or url.path or url.port not in (None,443)):
        raise rt.TelegramRuntimeError('telegram_webhook_https_required')
    return base+'/v1/telegram/scoped/'+pin.connection_id+'/webhook'


async def _change(pin,capsule,mode,secret,transport=None):
    token=rt._open_credentials(pin,capsule)
    method='setWebhook' if mode=='webhook' else 'deleteWebhook'
    payload={'drop_pending_updates':False}
    if mode=='webhook':payload.update(url=hook_url(pin),secret_token=secret,max_connections=1,allowed_updates=['message','callback_query'])
    try:
        inner=transport if transport is not None else httpx.AsyncHTTPTransport(retries=0,trust_env=False)
        with rt._private_io():
            async with httpx.AsyncClient(transport=rt._TokenTransport(token.get_secret_value(),inner),timeout=10,trust_env=False,follow_redirects=False) as client:
                async with client.stream('POST','https://api.telegram.org/bot-redacted/'+method,json=payload) as response:
                    raw=bytearray()
                    async for part in response.aiter_bytes(chunk_size=8192):
                        raw.extend(part)
                        if len(raw)>rt.MAX_BYTES:raise ValueError()
                    data=json.loads(raw);require_clean_payload(data,token.get_secret_value())
                    if response.status_code!=200 or type(data) is not dict or data.get('ok') is not True or data.get('result') is not True:raise ValueError()
    except asyncio.CancelledError:raise
    except Exception:raise rt.TelegramRuntimeError('telegram_transport_change_uncertain') from None


async def configure(lease,*,generation,request_key,mode,consent=False,transport=None):
    """Reserve disabled generation BEFORE remote I/O. Uncertain remote stays off.

    Retrying requires a fresh explicit consent/key. Never erase pending updates.
    No private token/header is returned, persisted plaintext or emitted in errors.
    """
    if mode not in ('polling','webhook') or consent is not True:raise rt.TelegramRuntimeError('telegram_transport_consent_required')
    key=store._request_key(request_key);store._integer(generation,1)
    secret=secrets.token_urlsafe(48) if mode=='webhook' else None
    if mode=='webhook':hook_url(lease.pin)
    async with store._transaction(lease) as db:
        row=await store._profile(db,lease.pin,generation)
        if not row or row.status!='disabled':raise rt.TelegramRuntimeError('telegram_transport_disable_first')
        capsule=store._unseal(lease.pin,generation,row.token_ciphertext)
        token=rt._open_credentials(lease.pin,capsule)
        row.generation+=1;row.token_ciphertext=store._seal(lease.pin,row.generation,token)
        row.transport_mode=mode;row.webhook_hash=hashlib.sha256(secret.encode()).hexdigest() if secret else None
        await store._audit(db,lease.pin,row,key,store._fingerprint(lease.pin,'transport:'+mode,generation,key),'rotated')
        view=store._view(row)
    # Lease remains owned; recheck scope/generation and hold authority over HTTP.
    async with store._transaction(lease) as db:
        row=await store._profile(db,lease.pin,view.generation)
        if row.status!='disabled':raise rt.TelegramRuntimeError('telegram_transport_disable_first')
        await _change(lease.pin,store._unseal(lease.pin,row.generation,row.token_ciphertext),mode,secret,transport)
    return view


@router.post('/{connection_id}/webhook')
async def ingress(connection_id:str,request:Request):
    # No JWT authority is derived from the body. Secret belongs to this exact
    # connection and disabled/rotated tokens cannot receive requests.
    try:
        store._request_key(connection_id);rt._enabled()
        headers=request.headers.getlist('x-telegram-bot-api-secret-token')
        if len(headers)!=1 or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}',headers[0]):raise ValueError()
        async with Session() as db:
            connection=await db.get(TelegramConnection,connection_id)
            identity=await db.scalar(select(TelegramBotIdentity).where(TelegramBotIdentity.connection_id==connection_id))
            if not connection or not identity:raise ValueError()
            pin=rt.RuntimePin(connection.workspace_id,connection.id,connection.owner_id,connection.version,identity.bot_user_id)
        async with asyncio.timeout(25),rt.own_bot(pin) as lease:
            async with store._transaction(lease) as db:
                row=await store._profile(db,pin)
                if (not row or row.status!='enabled' or row.transport_mode!='webhook' or not row.webhook_hash or
                    not hmac.compare_digest(row.webhook_hash,hashlib.sha256(headers[0].encode()).hexdigest())):raise ValueError()
                generation,offset=row.generation,row.next_offset
            if request.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':raise ValueError()
            raw=bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw)>2*1024*1024:raise HTTPException(413,'telegram_webhook_body_limit')
            update=json.loads(raw)
            await scoped.ingest_update(lease,generation=generation,expected_offset=offset,update=update,redis=request.app.state.redis,webhook=True)
        return {'ok':True}
    except HTTPException:raise
    except asyncio.CancelledError:raise
    except Exception:raise HTTPException(503,'telegram_webhook_not_accepted') from None
