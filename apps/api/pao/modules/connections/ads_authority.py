"""Read-only Ads grants do not authorize config, accounts discovery or actions."""
from fastapi import HTTPException
from sqlalchemy import select
from ...models import MetaConnection, GoogleAdsConnection, TenantConnectionReference, TenantConnectionGrant
from ...config import settings
from . import read_authority

DENIED = 'ads_connection_grant_denied'
MODELS = {'meta_ads': MetaConnection, 'google_ads': GoogleAdsConnection}


async def registered(db, conn, kind):
    return bool(await db.scalar(select(TenantConnectionReference.id).where(
        TenantConnectionReference.workspace_id == conn.workspace_id,
        TenantConnectionReference.kind == kind, TenantConnectionReference.source_id == conn.id).limit(1)))


async def legacy(db, conn, kind):
    if conn and await registered(db, conn, kind):
        raise HTTPException(403, DENIED)
    from ...integrations import ads_apps
    if conn and not await ads_apps.matches(db,conn,'meta' if kind=='meta_ads' else 'google'):
        raise HTTPException(409,ads_apps.DENIED)


async def selected(db, wid, actor, brand, account, grant_id, kind, *, write=False):
    model = MODELS[kind]
    await read_authority.lock_scope(db, wid)
    # Resolve identity only, lock source before any authority/credential checks.
    source = await db.scalar(select(TenantConnectionReference.source_id).join(
        TenantConnectionGrant, TenantConnectionGrant.reference_id == TenantConnectionReference.id).where(
        TenantConnectionReference.workspace_id == wid, TenantConnectionReference.kind == kind,
        TenantConnectionGrant.workspace_id == wid, TenantConnectionGrant.id == grant_id,
        TenantConnectionGrant.grantee_id == actor))
    conn = await db.scalar(select(model).where(model.id == source, model.workspace_id == wid)
                           .with_for_update(read=not write).execution_options(populate_existing=True))
    if not conn:
        raise HTTPException(403, DENIED)
    from ...integrations import ads_apps
    if not await ads_apps.matches(db,conn,'meta' if kind=='meta_ads' else 'google'):
        raise HTTPException(403,DENIED)
    try:
        pin = await read_authority.pin(db, wid, actor, brand, grant_id, kind=kind, account_id=account)
    except HTTPException:
        raise HTTPException(403, DENIED) from None
    enabled = settings().meta_enabled if kind == 'meta_ads' else settings().google_ads_enabled
    scopes = {'ads_read', 'ads_management'} if kind == 'meta_ads' else {'https://www.googleapis.com/auth/adwords'}
    if not enabled or not scopes.intersection(conn.scopes or []) or conn.version != pin['source_version']:
        raise HTTPException(403, DENIED)
    return conn, pin


async def job_allowed(db, conn, kind, job):
    pin = job.authority_pin
    if pin is None:
        return not await registered(db, conn, kind)
    if not isinstance(pin, dict) or pin.get('source_id') != conn.id or job.kind != 'historical':
        return False
    try:
        _, fresh = await selected(db, conn.workspace_id, pin.get('actor_id'), pin.get('brand_id'),
                                  job.account_id, pin.get('grant_id'), kind)
        return pin == fresh and job.connection_version == conn.version
    except HTTPException:
        return False
