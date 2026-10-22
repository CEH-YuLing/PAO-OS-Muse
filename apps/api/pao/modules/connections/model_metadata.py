"""Short source/actor transactions around metadata I/O; no inferred authority.

Shared durable metadata admission precedes key resolution; no connection/grant
is activated by catalogue discovery.
"""
import asyncio
import hashlib
import time
from fastapi import HTTPException
from sqlalchemy import select
from ...models import Member, ModelProviderConnection, User
from ..engines.contract import EngineFailure
from . import resources
from . import metadata_resources
from ...credential_guard import require_clean_payload, CredentialPayloadError
from ...model_router import ModelRouterError

TIMEOUT=30


async def manager(db,wid,who):
    from ...auth import check_session
    # Fresh values, not identity-map copies loaded by principal before slow I/O.
    user=await db.scalar(select(User).where(User.id==who.id).with_for_update(read=True)
        .execution_options(populate_existing=True))
    member=await db.scalar(select(Member).where(Member.workspace_id==wid,Member.user_id==who.id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    if not user or not user.active or not member or member.role not in ('owner','admin') or who.expires<=time.time():
        raise HTTPException(403,'model_metadata_authority_changed')
    await check_session(db, who)


def stamp(row):
    if row is None:return None
    # Ciphertext hash only in memory, never in response/log; timestamp prevents
    # same-value reconfiguration from silently reviving an earlier request.
    return (row.id,row.provider,row.model,row.status,row.is_default,
        hashlib.sha256(row.api_key_ciphertext.encode()).hexdigest(),row.updated_at)


async def source(db,wid,provider,who,expected=None,*,publication=False):
    try:await resources.lock(db,wid)
    except EngineFailure:raise HTTPException(403,'model_metadata_authority_changed') from None
    await manager(db,wid,who)
    row=await db.scalar(select(ModelProviderConnection).where(
        ModelProviderConnection.workspace_id==wid,ModelProviderConnection.provider==provider)
        .with_for_update().execution_options(populate_existing=True))
    if publication and stamp(row)!=expected:raise HTTPException(409,'model_metadata_source_changed')
    return row


async def fetch(db,provider,key,loader):
    # No workspace/source/member locks or open DB transaction across network.
    await db.commit()
    try:
        async with asyncio.timeout(TIMEOUT):
            result=await loader(provider,key)
            # Keep publication safe even with a replacement catalogue adapter.
            try:require_clean_payload(result,key)
            except CredentialPayloadError as exc:
                raise ModelRouterError('provider_models_sensitive' if str(exc)=='payload_credential_reflected' else 'provider_models_limit') from None
            return result
    except TimeoutError:raise HTTPException(503,'model_metadata_timeout') from None


async def begin(db,wid,provider,who,kind,request_key,*,existing=False):
    # Global order for admission: metadata pool -> model pool -> actor/source.
    await metadata_resources.lock(db,wid)
    row=await source(db,wid,provider,who)
    if existing and not row:raise HTTPException(409,'Provider chưa được kết nối')
    expected=stamp(row)
    lease=await metadata_resources.admit(db,wid,who.id,kind,request_key,provider+':'+str(expected))
    return row,expected,lease


async def admitted_fetch(db,provider,key,loader,lease):
    wid,lid=lease.workspace_id,lease.id
    await db.commit()
    try:
        await metadata_resources.require_current(wid,lid)
        return await fetch(db,provider,key,loader)
    finally:
        await metadata_resources.finish(wid,lid)
