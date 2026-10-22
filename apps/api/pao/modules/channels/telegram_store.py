"""S3.2B durable disabled profiles and body-free quarantine. Internal only.

No router, worker wiring, activation, polling, pairing, delivery or global token.
Connection's existing unique immutable bot identity is the identity registry.
Legacy namespaces without a verified identity stay denied, never inferred.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict,dataclass
import hashlib,hmac,json
from uuid import UUID
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from pao.models import TelegramRuntimeProfile,TelegramRuntimeAudit,TelegramRuntimeReceipt
from . import telegram_runtime as rt

PURPOSE='pao.telegram.store.v1'
REASONS=frozenset(('unsupported','unlinked','malformed'))


def _integer(value,minimum=0):
    if type(value) is not int or not minimum<=value<2**63-1:
        raise rt.TelegramRuntimeError('telegram_store_input_invalid')
    return value


def _request_key(value):
    try:
        if type(value) is not str or str(UUID(value))!=value:raise ValueError()
        return value
    except Exception:raise rt.TelegramRuntimeError('telegram_store_input_invalid') from None


def _fingerprint(pin,action,expected,key,token=None):
    # Keyed content identity permits lost-response replay checks without storing
    # token plaintext or an unkeyed token hash in an audit or response.
    data={'pin':asdict(pin),'action':action,'expected':expected,'request_key':key,
        'token':token.get_secret_value() if token is not None else None}
    rt._cipher()  # Validate the server key before deriving a purpose-specific MAC.
    mac_key=hashlib.sha256((PURPOSE+':'+rt.settings().integration_encryption_key).encode()).digest()
    return hmac.new(mac_key,json.dumps(data,sort_keys=True).encode(),hashlib.sha256).hexdigest()


def _seal(pin,generation,token):
    capsule=rt.seal_credentials(pin,token)
    value={'purpose':PURPOSE,'pin':asdict(pin),'generation':generation,
        'capsule':capsule.ciphertext.get_secret_value()}
    return rt._cipher().encrypt(json.dumps(value,sort_keys=True).encode()).decode()


def _unseal(pin,generation,ciphertext):
    _integer(generation,1)
    try:
        if type(ciphertext) is not str or not 1<=len(ciphertext)<=16384:raise ValueError()
        data=json.loads(rt._cipher().decrypt(ciphertext.encode()))
        if (type(data) is not dict or set(data)!= {'purpose','pin','generation','capsule'} or
            data['purpose']!=PURPOSE or data['pin']!=asdict(pin) or rt.RuntimePin(**data['pin'])!=pin or
            type(data['generation']) is not int or data['generation']!=generation):raise ValueError()
        capsule=rt.SealedCredential(SecretStr(data['capsule']))
        rt._open_credentials(pin,capsule)
        return capsule
    except rt.TelegramRuntimeError:raise
    except Exception:raise rt.TelegramRuntimeError('telegram_store_credential_unreadable') from None


@dataclass(frozen=True,slots=True)
class ProfileView:
    connection_id:str
    generation:int
    status:str
    next_offset:int
    # Deliberately no configured/verified/healthy/accepted alias.


def _view(row):return ProfileView(row.connection_id,row.generation,row.status,row.next_offset)


@asynccontextmanager
async def _transaction(lease):
    rt._enabled();lease.require_active()
    # Owning lock context expects sequential bounded operations, never concurrent
    # sessions sharing one lease. Clear a previous metadata-only read transaction.
    if lease.connection.in_transaction():
        raise rt.TelegramRuntimeError('telegram_store_transaction_busy')
    try:
        async with asyncio.timeout(20),AsyncSession(bind=lease.connection,expire_on_commit=False) as db:
            async with db.begin():
                await rt._require_lease(db,lease);await rt._scope(db,lease.pin)
                yield db
                rt._enabled();await rt._require_lease(db,lease)
    except (TimeoutError,SQLAlchemyError):
        # No raw SQL/bind parameters or encrypted credential in public errors.
        raise rt.TelegramRuntimeError('telegram_store_unavailable') from None


async def _profile(db,pin,expected=None):
    row=await db.scalar(select(TelegramRuntimeProfile).where(
        TelegramRuntimeProfile.connection_id==pin.connection_id,
        TelegramRuntimeProfile.workspace_id==pin.workspace_id).with_for_update().execution_options(populate_existing=True))
    if row and row.connection_version!=pin.connection_version:
        raise rt.TelegramRuntimeError('telegram_store_scope_changed')
    if expected is not None and (row.generation if row else 0)!=expected:
        raise rt.TelegramRuntimeError('telegram_store_generation_stale')
    return row


async def _saved(db,pin,key,fingerprint):
    event=await db.scalar(select(TelegramRuntimeAudit).where(TelegramRuntimeAudit.workspace_id==pin.workspace_id,
        TelegramRuntimeAudit.actor_id==pin.owner_id,TelegramRuntimeAudit.request_key==key))
    if event and (event.connection_id!=pin.connection_id or not hmac.compare_digest(event.content_hash,fingerprint)):
        raise rt.TelegramRuntimeError('telegram_store_request_conflict')
    return event


async def _audit(db,pin,row,key,fingerprint,action):
    await db.flush()
    db.add(TelegramRuntimeAudit(workspace_id=pin.workspace_id,connection_id=pin.connection_id,
        actor_id=pin.owner_id,request_key=key,generation=row.generation,action=action,content_hash=fingerprint))
    await db.flush()


async def save_profile(lease,token:SecretStr,*,expected_generation,request_key,consent=False):
    """Store/rotate, still DISABLED and unverified. Requires fresh owner consent."""
    _integer(expected_generation);key=_request_key(request_key)
    if expected_generation>=2**31-1:raise rt.TelegramRuntimeError('telegram_store_input_invalid')
    if consent is not True:raise rt.TelegramRuntimeError('telegram_store_consent_required')
    if not isinstance(token,SecretStr) or not rt._token_ok(token.get_secret_value(),lease.pin):
        raise rt.TelegramRuntimeError('telegram_runtime_credential_invalid')
    fingerprint=_fingerprint(lease.pin,'save',expected_generation,key,token)
    async with _transaction(lease) as db:
        saved=await _saved(db,lease.pin,key,fingerprint)
        row=await _profile(db,lease.pin)
        if saved:
            if not row or row.generation!=saved.generation or row.status!='disabled':
                raise rt.TelegramRuntimeError('telegram_store_request_superseded')
            return _view(row)
        if (row.generation if row else 0)!=expected_generation:raise rt.TelegramRuntimeError('telegram_store_generation_stale')
        if row and row.status=='revoked':raise rt.TelegramRuntimeError('telegram_store_revoked')
        generation=expected_generation+1;sealed=_seal(lease.pin,generation,token)
        if row is None:
            row=TelegramRuntimeProfile(workspace_id=lease.pin.workspace_id,connection_id=lease.pin.connection_id,
                connection_version=lease.pin.connection_version,generation=generation,status='disabled',token_ciphertext=sealed,next_offset=0)
            db.add(row)
        else:row.generation=generation;row.token_ciphertext=sealed;row.status='disabled'
        await _audit(db,lease.pin,row,key,fingerprint,'stored' if generation==1 else 'rotated')
        return _view(row)


async def revoke_profile(lease,*,expected_generation,request_key,consent=False):
    _integer(expected_generation,1);key=_request_key(request_key)
    if expected_generation>=2**31-1:raise rt.TelegramRuntimeError('telegram_store_input_invalid')
    if consent is not True:raise rt.TelegramRuntimeError('telegram_store_consent_required')
    fingerprint=_fingerprint(lease.pin,'revoke',expected_generation,key)
    async with _transaction(lease) as db:
        saved=await _saved(db,lease.pin,key,fingerprint);row=await _profile(db,lease.pin)
        if saved:
            if row is None or row.generation!=saved.generation or row.status!='revoked':
                raise rt.TelegramRuntimeError('telegram_store_request_superseded')
            return _view(row)
        if row is None or row.generation!=expected_generation:raise rt.TelegramRuntimeError('telegram_store_generation_stale')
        if row.status=='revoked':raise rt.TelegramRuntimeError('telegram_store_revoked')
        row.generation+=1;row.status='revoked';row.token_ciphertext=None
        await _audit(db,lease.pin,row,key,fingerprint,'revoked');return _view(row)


def credential_loader(expected_generation):
    """Trusted metadata-loader factory. A generation change invalidates the pin.

    Returning a capsule is NOT a grant to poll or send; rt.probe remains read-only.
    """
    _integer(expected_generation,1)
    async def load(db,pin):
        row=await _profile(db,pin,expected_generation)
        if row is None or row.status not in ('disabled','enabled'):raise rt.TelegramRuntimeError('telegram_store_revoked')
        return _unseal(pin,expected_generation,row.token_ciphertext)
    return load


async def record_quarantine(lease,*,generation,expected_offset,updates,reason):
    """Durably quarantine unsupported/unlinked updates; atomic receipt + cursor.

    No body retention, run admission, peer creation or replay. No Telegram call.
    The future adapter must commit this before acknowledging a polling offset.
    """
    _integer(generation,1);_integer(expected_offset)
    if type(reason) is not str or reason not in REASONS or type(updates) is not list or not 1<=len(updates)<=100:
        raise rt.TelegramRuntimeError('telegram_store_input_invalid')
    parsed=[]
    try:
        raw=json.dumps(updates,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
        if len(raw)>rt.MAX_BYTES:raise ValueError()
        for item in updates:
            if type(item) is not dict:raise ValueError()
            update_id=_integer(item.get('update_id'))
            parsed.append((update_id,hashlib.sha256(json.dumps(item,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()))
    except Exception:raise rt.TelegramRuntimeError('telegram_store_input_invalid') from None
    async with _transaction(lease) as db:
        row=await _profile(db,lease.pin,generation)
        if row is None or row.status!='disabled':raise rt.TelegramRuntimeError('telegram_store_revoked')
        if row.next_offset!=expected_offset:raise rt.TelegramRuntimeError('telegram_store_cursor_stale')
        for update_id,fingerprint in parsed:
            saved=await db.scalar(select(TelegramRuntimeReceipt).where(
                TelegramRuntimeReceipt.connection_id==lease.pin.connection_id,TelegramRuntimeReceipt.cursor_epoch==row.cursor_epoch,
                TelegramRuntimeReceipt.update_id==update_id))
            if saved:
                if saved.content_hash!=fingerprint or saved.reason!=reason:raise rt.TelegramRuntimeError('telegram_store_update_conflict')
                continue
            # Unknown old updates must not be re-admitted after a rotation/reset.
            if update_id<expected_offset:raise rt.TelegramRuntimeError('telegram_store_update_behind_cursor')
            db.add(TelegramRuntimeReceipt(workspace_id=lease.pin.workspace_id,connection_id=lease.pin.connection_id,
                generation=generation,cursor_epoch=row.cursor_epoch,update_id=update_id,content_hash=fingerprint,reason=reason))
            await db.flush()
        row.next_offset=max(row.next_offset,max(item[0] for item in parsed)+1)
        from pao.models import now
        row.cursor_touched_at=now()
        await db.flush();return _view(row)
