"""S3.2B internal getMe-verified identity journal. No activation or team grant."""
import asyncio
from dataclasses import dataclass
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from pao.models import TelegramConnection,TelegramBotIdentity,TelegramLegacyMapping
from . import telegram_runtime as rt,telegram_store as store


@dataclass(frozen=True,slots=True)
class IdentityView:
    workspace_id:str
    connection_id:str
    bot_user_id:str
    connection_version:int


def _view(row):
    return IdentityView(row.workspace_id,row.connection_id,row.bot_user_id,row.connection_version)


async def _candidate(db,pin):
    row=await rt._owner_connection(db,pin)
    if row.kind=='native':
        if row.bot_user_id!=pin.bot_user_id:raise rt.TelegramRuntimeError('telegram_identity_scope_changed')
    elif row.kind=='legacy' and row.bot_user_id is None:
        mapped=await db.scalar(select(TelegramLegacyMapping.id).where(
            TelegramLegacyMapping.connection_id==pin.connection_id,
            TelegramLegacyMapping.workspace_id==pin.workspace_id,
            TelegramLegacyMapping.owner_id==pin.owner_id))
        if not mapped:raise rt.TelegramRuntimeError('telegram_identity_mapping_required')
    else:raise rt.TelegramRuntimeError('telegram_identity_scope_changed')
    claimed=await db.scalar(select(TelegramConnection.id).where(
        TelegramConnection.bot_user_id==pin.bot_user_id,TelegramConnection.id!=pin.connection_id).limit(1))
    claimed_identity=await db.scalar(select(TelegramBotIdentity.id).where(
        TelegramBotIdentity.bot_user_id==pin.bot_user_id,TelegramBotIdentity.connection_id!=pin.connection_id).limit(1))
    if claimed or claimed_identity:raise rt.TelegramRuntimeError('telegram_identity_claimed')


async def verify_identity(lease,token:SecretStr,*,request_key,consent=False,transport=None):
    """One explicit, fresh-authority getMe; journal its identity, not its token.

    Retries of the exact request return the journal without another provider call.
    Native/legacy share the registry. DB guard reserves identities against future
    namespace inserts even after disconnect. Caller cannot supply a 'verified' flag.
    """
    key=store._request_key(request_key)
    if consent is not True:raise rt.TelegramRuntimeError('telegram_identity_consent_required')
    capsule=rt.seal_credentials(lease.pin,token)
    fingerprint=store._fingerprint(lease.pin,'verify_identity',0,key,token)
    rt._enabled();lease.require_active()
    if lease.connection.in_transaction():raise rt.TelegramRuntimeError('telegram_store_transaction_busy')
    try:
        async with asyncio.timeout(20),AsyncSession(bind=lease.connection,expire_on_commit=False) as db:
            async with db.begin():
                await rt._require_lease(db,lease);await _candidate(db,lease.pin)
                saved=await db.scalar(select(TelegramBotIdentity).where(
                    TelegramBotIdentity.workspace_id==lease.pin.workspace_id,
                    TelegramBotIdentity.owner_id==lease.pin.owner_id,TelegramBotIdentity.request_key==key))
                if saved:
                    if (saved.connection_id!=lease.pin.connection_id or saved.bot_user_id!=lease.pin.bot_user_id or
                        saved.connection_version!=lease.pin.connection_version or saved.content_hash!=fingerprint):
                        raise rt.TelegramRuntimeError('telegram_identity_request_conflict')
                    return _view(saved)
                bound=await db.scalar(select(TelegramBotIdentity.id).where(TelegramBotIdentity.connection_id==lease.pin.connection_id))
                if bound:raise rt.TelegramRuntimeError('telegram_identity_already_bound')
                result=await rt._metadata(lease.pin,capsule,'getMe',transport)
                rt._enabled();await rt._require_lease(db,lease);await _candidate(db,lease.pin)
                if result.bot_user_id!=lease.pin.bot_user_id:raise rt.TelegramRuntimeError('telegram_identity_scope_changed')
                row=TelegramBotIdentity(workspace_id=lease.pin.workspace_id,connection_id=lease.pin.connection_id,
                    owner_id=lease.pin.owner_id,connection_version=lease.pin.connection_version,
                    bot_user_id=result.bot_user_id,request_key=key,content_hash=fingerprint)
                db.add(row);await db.flush();return _view(row)
    except (TimeoutError,SQLAlchemyError):
        raise rt.TelegramRuntimeError('telegram_identity_unavailable') from None


async def resolve_identity(db,pin):
    """Fresh identity only, never a token, user membership grant or activation."""
    rt._enabled();await rt._scope(db,pin)
    row=await db.scalar(select(TelegramBotIdentity).where(
        TelegramBotIdentity.connection_id==pin.connection_id,
        TelegramBotIdentity.workspace_id==pin.workspace_id,
        TelegramBotIdentity.owner_id==pin.owner_id,
        TelegramBotIdentity.connection_version==pin.connection_version,
        TelegramBotIdentity.bot_user_id==pin.bot_user_id))
    if not row:raise rt.TelegramRuntimeError('telegram_identity_unverified')
    return _view(row)
