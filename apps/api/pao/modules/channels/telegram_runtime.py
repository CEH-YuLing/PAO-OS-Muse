"""S3.2A metadata transport boundary. No polling, sends, public API or token store.

Native namespace + fresh owner authority, sealed credential scope and a PostgreSQL
session lock for the actual bot (not tenant/token). Legacy/global fallbacks denied.
Only getMe/getWebhookInfo are admitted here; delivery admission belongs to S3.2B.
"""
import asyncio
from contextlib import asynccontextmanager,contextmanager
from contextvars import ContextVar
from dataclasses import dataclass,field,asdict
import json
import logging
import re
from uuid import UUID
from cryptography.fernet import Fernet
import httpx
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select,text
from sqlalchemy.ext.asyncio import AsyncSession
from pao.config import settings
from pao.db import engine
from pao.models import TelegramConnection,TelegramBotIdentity,TelegramLegacyMapping,User,Member
from pao.credential_guard import require_clean_payload

PURPOSE='pao.telegram.runtime.v1'
MAX_BYTES=65536
READ_METHODS=frozenset(('getMe','getWebhookInfo'))
_PRIVATE_IO=ContextVar('pao_telegram_private_io',default=False)

class _PrivateIOFilter(logging.Filter):
    _pao_telegram=True
    def filter(self,record):return not _PRIVATE_IO.get()

@contextmanager
def _private_io():
    # Exact logger names used by the locked HTTPX/HTTPCore runtime. Suppression
    # is coroutine-local, not a global level change that affects other tenants.
    for name in ('httpx','httpcore.connection','httpcore.http11','httpcore.http2','httpcore.proxy','httpcore.socks'):
        logger=logging.getLogger(name)
        if not any(getattr(f,'_pao_telegram',False) for f in logger.filters):logger.addFilter(_PrivateIOFilter())
    ticket=_PRIVATE_IO.set(True)
    try:yield
    finally:_PRIVATE_IO.reset(ticket)

class TelegramRuntimeError(RuntimeError):
    """Stable codes only; never attach credentials, payloads or provider errors."""

@dataclass(frozen=True,slots=True)
class RuntimePin:
    workspace_id:str
    connection_id:str
    owner_id:str
    connection_version:int
    bot_user_id:str

    def __post_init__(self):
        try:
            for ident in (self.workspace_id,self.connection_id,self.owner_id):
                if type(ident) is not str or str(UUID(ident))!=ident:raise ValueError()
            if type(self.connection_version) is not int or self.connection_version<1:raise ValueError()
            if type(self.bot_user_id) is not str or not re.fullmatch(r'[1-9][0-9]{0,15}',self.bot_user_id):raise ValueError()
        except Exception:raise TelegramRuntimeError('telegram_runtime_pin_invalid') from None

@dataclass(frozen=True,slots=True)
class SealedCredential:
    ciphertext:SecretStr=field(repr=False)

def _cipher():
    try:return Fernet(settings().integration_encryption_key.encode())
    except Exception:raise TelegramRuntimeError('telegram_runtime_encryption_unavailable') from None

def _token_ok(token,pin):
    return type(token) is str and 30<=len(token)<=512 and token.startswith(pin.bot_user_id+':') and bool(re.fullmatch(r'[1-9][0-9]{0,15}:[A-Za-z0-9_-]+',token))

def seal_credentials(pin:RuntimePin,token:SecretStr):
    """Internal capsule for a future store, NOT getMe verification or activation.

    Authenticated scope prevents moving ciphertext between namespaces/versions.
    Never persist a capsule through a route that does not verify owner consent.
    """
    try:
        raw=token.get_secret_value()
        if not _token_ok(raw,pin):raise ValueError()
        payload={'purpose':PURPOSE,'pin':asdict(pin),'token':raw}
        return SealedCredential(SecretStr(_cipher().encrypt(json.dumps(payload,sort_keys=True).encode()).decode()))
    except TelegramRuntimeError:raise
    except Exception:raise TelegramRuntimeError('telegram_runtime_credential_invalid') from None

def _open_credentials(pin,capsule):
    try:
        if not isinstance(capsule,SealedCredential):raise ValueError()
        sealed=capsule.ciphertext.get_secret_value()
        if type(sealed) is not str or len(sealed)>8192:raise ValueError()
        payload=json.loads(_cipher().decrypt(sealed.encode()))
        if (type(payload) is not dict or set(payload)!= {'purpose','pin','token'} or
            payload['purpose']!=PURPOSE or payload['pin']!=asdict(pin) or not _token_ok(payload['token'],pin)):raise ValueError()
        # bool==1 in Python must not make a malformed version into a valid pin.
        if RuntimePin(**payload['pin'])!=pin:raise ValueError()
        return SecretStr(payload['token'])
    except TelegramRuntimeError:raise
    except Exception:raise TelegramRuntimeError('telegram_runtime_credential_unreadable') from None

@dataclass(frozen=True,slots=True)
class BotLease:
    pin:RuntimePin
    connection:object=field(repr=False)
    backend_pid:int
    active:bool=True

    def require_active(self):
        if not self.active or self.connection.closed or self.connection.invalidated:
            raise TelegramRuntimeError('telegram_runtime_lease_lost')

@asynccontextmanager
async def own_bot(pin:RuntimePin):
    """One checked-out PG session per bounded operation; crash releases its lock."""
    if not isinstance(pin,RuntimePin):raise TelegramRuntimeError('telegram_runtime_pin_invalid')
    connection=None;acquired=False;lease=None
    key='pao-telegram-bot-v1:'+pin.bot_user_id
    try:
        async with asyncio.timeout(5):
            connection=await engine.connect()
            acquired=bool(await connection.scalar(text('SELECT pg_try_advisory_lock(hashtextextended(:key,0))'),{'key':key}))
            if not acquired:raise TelegramRuntimeError('telegram_runtime_bot_busy')
            pid=await connection.scalar(text('SELECT pg_backend_pid()'));await connection.commit()
        lease=BotLease(pin,connection,pid);yield lease
    except TelegramRuntimeError:raise
    except HTTPException:raise  # Deliberate domain denial; never provider errors.
    except asyncio.CancelledError:raise
    except Exception:raise TelegramRuntimeError('telegram_runtime_unavailable') from None
    finally:
        if lease:object.__setattr__(lease,'active',False)
        if connection is not None:
            try:
                async with asyncio.timeout(5):
                    if acquired and not connection.closed and not connection.invalidated:
                        await connection.rollback()
                        if not await connection.scalar(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),{'key':key}):
                            await connection.invalidate()
                        else:await connection.commit()
            except BaseException:
                # Never return a session with an uncertain advisory lock to pool.
                await connection.invalidate()
            finally:await connection.close()

def _enabled():
    if not settings().telegram_scoped_runtime_enabled:raise TelegramRuntimeError('telegram_runtime_disabled')
    if settings().telegram_enabled:raise TelegramRuntimeError('telegram_runtime_legacy_conflict')

async def _owner_connection(db,pin):
    # Shared row locks serialize an already admitted request against revocation.
    # Match owner-control ordering: member -> user -> connection. Taking the
    # user/connection first can deadlock a revoke that already owns member.
    member=await db.get(Member,(pin.workspace_id,pin.owner_id),with_for_update={'read':True},populate_existing=True)
    user=await db.get(User,pin.owner_id,with_for_update={'read':True},populate_existing=True)
    if not user or not user.active or not member or member.role not in ('owner','admin'):
        raise TelegramRuntimeError('telegram_runtime_owner_unavailable')
    row=await db.scalar(select(TelegramConnection).where(TelegramConnection.id==pin.connection_id,
        TelegramConnection.workspace_id==pin.workspace_id,TelegramConnection.owner_id==pin.owner_id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    if not row or row.version!=pin.connection_version or row.status!='staged':
        raise TelegramRuntimeError('telegram_runtime_scope_changed')
    return row


async def _scope(db,pin):
    row=await _owner_connection(db,pin)
    if row.kind=='native' and row.bot_user_id==pin.bot_user_id:return
    if row.kind=='legacy' and row.bot_user_id is None:
        # New immutable journal supplies verified identity without repinning the
        # old namespace or copying host credentials/history. No journal -> deny.
        identity=await db.scalar(select(TelegramBotIdentity).where(
            TelegramBotIdentity.connection_id==pin.connection_id,
            TelegramBotIdentity.workspace_id==pin.workspace_id,
            TelegramBotIdentity.owner_id==pin.owner_id,
            TelegramBotIdentity.connection_version==pin.connection_version,
            TelegramBotIdentity.bot_user_id==pin.bot_user_id))
        mapped=await db.scalar(select(TelegramLegacyMapping.id).where(
            TelegramLegacyMapping.connection_id==pin.connection_id,
            TelegramLegacyMapping.workspace_id==pin.workspace_id,
            TelegramLegacyMapping.owner_id==pin.owner_id))
        if identity and mapped:return
    raise TelegramRuntimeError('telegram_runtime_scope_changed')

async def _require_lease(db,lease):
    lease.require_active()
    # Validate the server's lock, not just an in-memory lease object. Bigint
    # advisory keys are exposed as two unsigned32 OIDs in pg_locks (subid1).
    held=await db.scalar(text("""SELECT pg_backend_pid()=:pid AND EXISTS(
        SELECT 1 FROM pg_locks WHERE locktype='advisory' AND granted
        AND pid=pg_backend_pid() AND mode='ExclusiveLock' AND objsubid=1
        AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
        AND classid=((hashtextextended(:key,0)>>32)&4294967295)::oid
        AND objid=(hashtextextended(:key,0)&4294967295)::oid)"""),
        {'pid':lease.backend_pid,'key':'pao-telegram-bot-v1:'+lease.pin.bot_user_id})
    if not held:raise TelegramRuntimeError('telegram_runtime_lease_lost')

class _TokenTransport(httpx.AsyncBaseTransport):
    """Keep token URL out of HTTPX client logs and attached error requests.

    Only the low-level transport receives it; no auth header, redirect or proxy.
    The injected transport is trusted infrastructure, never model/plugin input.
    """
    def __init__(self,token,inner):self._token=token;self._inner=inner
    async def handle_async_request(self,request):
        method=request.url.path.rsplit('/',1)[-1]
        actual=httpx.Request('POST','https://api.telegram.org/bot'+self._token+'/'+method,
            headers=request.headers,content=await request.aread(),extensions=request.extensions)
        try:return await self._inner.handle_async_request(actual)
        finally:actual.url=request.url
    async def aclose(self):
        self._token='';await self._inner.aclose()

@dataclass(frozen=True,slots=True)
class ProbeResult:
    method:str
    bot_user_id:str
    username:str|None=None
    webhook_present:bool|None=None
    pending_update_count:int|None=None
    webhook_matches:bool|None=None

def _project(method,result,pin):
    if type(result) is not dict:raise ValueError()
    if method=='getMe':
        if type(result.get('id')) is not int or str(result['id'])!=pin.bot_user_id or result.get('is_bot') is not True:raise ValueError()
        username=result.get('username')
        if username is not None and (type(username) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}',username)):raise ValueError()
        return ProbeResult(method,pin.bot_user_id,username=username)
    url=result.get('url');count=result.get('pending_update_count')
    if type(url) is not str or len(url)>4096 or type(count) is not int or not 0<=count<2**63:raise ValueError()
    # Do not return provider URL/error text: URLs can themselves contain secrets.
    matches=None
    if settings().telegram_public_base_url:
        from .telegram_transport import hook_url
        try:matches=url==hook_url(pin)
        except TelegramRuntimeError:matches=False
    return ProbeResult(method,pin.bot_user_id,webhook_present=bool(url),pending_update_count=count,webhook_matches=matches)

async def probe(lease:BotLease,loader=None,*,method='getMe',transport=None):
    """Metadata only. No fallback, retry, implicit activation or raw provider data.

    Loader(db,pin) must be the future authoritative server-side store. Missing
    loader is denied even if a global host token happens to be configured.
    """
    _enabled();lease.require_active()
    if method not in READ_METHODS:raise TelegramRuntimeError('telegram_runtime_method_denied')
    if loader is None:raise TelegramRuntimeError('telegram_runtime_store_pending')
    try:
        async with asyncio.timeout(20),AsyncSession(bind=lease.connection,expire_on_commit=False) as db:
            await _require_lease(db,lease)
            await _scope(db,lease.pin)
            capsule=await loader(db,lease.pin)
            _enabled();await _require_lease(db,lease);await _scope(db,lease.pin)
            return await _metadata(lease.pin,capsule,method,transport)
    except TelegramRuntimeError:raise
    except asyncio.CancelledError:raise
    except Exception:raise TelegramRuntimeError('telegram_runtime_provider_invalid') from None


async def _metadata(pin,capsule,method,transport):
    """Shared bounded HTTP primitive; caller MUST hold fresh scope/PG lease.

    Internal infrastructure only. Exposes neither URL injection nor send/poll.
    Registry enrollment uses this exact adapter after its candidate-scope check.
    """
    _enabled()
    if method not in READ_METHODS:raise TelegramRuntimeError('telegram_runtime_method_denied')
    secret=None
    try:
        secret=_open_credentials(pin,capsule)
        inner=transport if transport is not None else httpx.AsyncHTTPTransport(retries=0,trust_env=False)
        wrapper=_TokenTransport(secret.get_secret_value(),inner)
        with _private_io():
          async with httpx.AsyncClient(transport=wrapper,timeout=10,trust_env=False,follow_redirects=False) as client:
            async with client.stream('POST','https://api.telegram.org/bot-redacted/'+method,json={}) as response:
                if response.status_code!=200 or response.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':
                    raise TelegramRuntimeError('telegram_runtime_provider_unavailable')
                raw=bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    raw.extend(chunk)
                    if len(raw)>MAX_BYTES:raise TelegramRuntimeError('telegram_runtime_response_limit')
                data=json.loads(raw);require_clean_payload(data,secret.get_secret_value())
                if type(data) is not dict or data.get('ok') is not True:raise ValueError()
                return _project(method,data.get('result'),pin)
    except TelegramRuntimeError:raise
    except asyncio.CancelledError:raise
    except Exception:raise TelegramRuntimeError('telegram_runtime_provider_invalid') from None
    finally:secret=None
