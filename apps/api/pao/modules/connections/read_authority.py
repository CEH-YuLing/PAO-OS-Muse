"""MCP consent supplements native tool/skill/Brain permissions; never replaces them."""
from fastapi import HTTPException
from sqlalchemy import select

from ...auth import Principal
from ...models import ConnectionReadActivation, TenantConnectionGrant, TenantConnectionReference, Workspace
from ..studio.contracts import digest
from . import grants

VERSION = 's21b2c-mcp-grant-v1'
CAPABILITY = 'mcp_read'
DENIED = 'connector_connection_grant_denied'


async def lock_scope(db, workspace):
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace)
                    .with_for_update(read=True, key_share=True))


def public(row, replayed=False):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'grant_id': row.grant_id,
            'manager_id': row.actor_id, 'kind': row.kind, 'capability': row.capability,
            'reference_revision': row.reference_revision, 'grant_revision': row.grant_revision,
            'consent_recorded': True, 'replayed': replayed, 'selection_required': True,
            'native_tool_permission_required': row.kind == 'mcp', 'provider_health_verified': False}


async def activate(db, workspace, who, reference_id, grant_id, body):
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await grants.active_member(db, workspace, who.id, managing=True, lock=True)
    ref = await grants.managed(db, workspace, reference_id, who, lock=True)
    kinds = ('mcp',) if body.capability == CAPABILITY else ('meta_ads', 'google_ads') if body.capability == 'ads_read' else ()
    if ref.kind not in kinds:
        raise HTTPException(422, 'connection_activation_kind_not_supported')
    fingerprint = digest({'reference_id': reference_id, 'grant_id': grant_id,
                          'body': body.model_dump(mode='json')})
    old = await db.scalar(select(ConnectionReadActivation).where(
        ConnectionReadActivation.workspace_id == workspace, ConnectionReadActivation.actor_id == who.id,
        ConnectionReadActivation.request_key == str(body.request_key)))
    if old:
        if old.fingerprint != fingerprint:
            raise HTTPException(409, 'connection_activation_request_key_conflict')
        return public(old, True)  # Recorded consent, NOT renewed/executable authority.
    grant = await db.scalar(select(TenantConnectionGrant).where(
        TenantConnectionGrant.workspace_id == workspace, TenantConnectionGrant.reference_id == ref.id,
        TenantConnectionGrant.id == grant_id).with_for_update())
    if not grant:
        raise HTTPException(404, 'connection_grant_not_found')
    if ref.revision != body.reference_revision or grant.revision != body.grant_revision:
        raise HTTPException(409, 'connection_activation_revision_conflict')
    await grants.check_staged_grant(db, workspace, Principal(grant.grantee_id, 0), ref.id, grant.id,
                                   grant.brand_id, grant.account_id, ref.revision)
    if await db.scalar(select(ConnectionReadActivation.id).where(ConnectionReadActivation.grant_id == grant.id)):
        raise HTTPException(409, 'connection_grant_already_activated')
    row = ConnectionReadActivation(workspace_id=workspace, grant_id=grant.id, actor_id=who.id,
        kind=ref.kind, capability=body.capability, reference_revision=ref.revision, grant_revision=grant.revision,
        source_stamp=ref.source_stamp, request_key=str(body.request_key), fingerprint=fingerprint)
    db.add(row)
    await db.flush()
    await db.commit()
    return public(row)


async def unregistered(db, workspace, source_id):
    await lock_scope(db, workspace)
    if await db.scalar(select(TenantConnectionReference.id).where(
        TenantConnectionReference.workspace_id == workspace, TenantConnectionReference.kind == 'mcp',
        TenantConnectionReference.source_id == source_id).limit(1)):
        # Tombstones, expired grants and manager status do not resurrect legacy.
        raise HTTPException(403, DENIED)


async def pin(db, workspace, actor_id, brand_id, grant_id, *, kind='mcp', account_id=None):
    await lock_scope(db, workspace)
    grant = await db.scalar(select(TenantConnectionGrant).where(
        TenantConnectionGrant.id == grant_id, TenantConnectionGrant.workspace_id == workspace,
        TenantConnectionGrant.grantee_id == actor_id).execution_options(populate_existing=True))
    if not grant:
        raise HTTPException(403, DENIED)
    ref = await db.scalar(select(TenantConnectionReference).where(
        TenantConnectionReference.id == grant.reference_id, TenantConnectionReference.workspace_id == workspace)
        .execution_options(populate_existing=True))
    consent = await db.scalar(select(ConnectionReadActivation).where(
        ConnectionReadActivation.workspace_id == workspace, ConnectionReadActivation.grant_id == grant.id))
    capability = CAPABILITY if kind == 'mcp' else 'ads_read'
    if (kind not in ('mcp', 'meta_ads', 'google_ads') or not ref or ref.kind != kind or not consent or consent.kind != kind
            or consent.capability != capability or consent.actor_id != ref.manager_id
            or consent.reference_revision != ref.revision or consent.grant_revision != grant.revision
            or consent.source_stamp != ref.source_stamp):
        raise HTTPException(403, DENIED)
    try:
        await grants.check_staged_grant(db, workspace, Principal(actor_id, 0), ref.id, grant.id,
                                       brand_id, account_id, ref.revision)
    except HTTPException:
        raise HTTPException(403, DENIED) from None
    result = {'version': VERSION if kind == 'mcp' else 's21b2d-ads-grant-v1', 'mode': 'mcp_grant' if kind == 'mcp' else 'ads_grant', 'workspace_id': workspace,
            'actor_id': actor_id, 'brand_id': brand_id, 'source_id': ref.source_id,
            'reference_id': ref.id, 'reference_revision': ref.revision,
            'grant_id': grant.id, 'grant_revision': grant.revision, 'activation_id': consent.id,
            'expires_at': grant.expires_at.isoformat(), 'capability': capability}
    if kind != 'mcp':
        result.update(kind=kind, account_id=account_id, source_version=ref.source_version)
    return result
