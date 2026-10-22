"""Explicit, append-only model consent. Never auto-select a grant or credential."""
from fastapi import HTTPException
from sqlalchemy import select

from ...auth import Principal
from ...models import ModelGrantActivation, TenantConnectionGrant, TenantConnectionReference, Workspace
from ..engines.contract import EngineFailure
from ..studio.contracts import digest
from . import grants

VERSION = 's21b2b-model-grant-v1'
CAPABILITY = 'model_inference'
DENIED = 'engine_connection_grant_denied'


def public(row, replayed=False):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'grant_id': row.grant_id,
            'manager_id': row.actor_id, 'reference_revision': row.reference_revision,
            'grant_revision': row.grant_revision, 'capability': row.capability,
            'consent_recorded': True, 'replayed': replayed,
            'selection_required': True, 'tools_enabled': False}


async def activate(db, workspace, who, reference_id, grant_id, body):
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await grants.active_member(db, workspace, who.id, managing=True, lock=True)
    ref = await grants.managed(db, workspace, reference_id, who, lock=True)
    if ref.kind not in ('model', 'cli_model'):
        raise HTTPException(422, 'connection_activation_kind_not_supported')
    fingerprint = digest({'reference_id': reference_id, 'grant_id': grant_id,
                          'body': body.model_dump(mode='json')})
    old = await db.scalar(select(ModelGrantActivation).where(
        ModelGrantActivation.workspace_id == workspace, ModelGrantActivation.actor_id == who.id,
        ModelGrantActivation.request_key == str(body.request_key)))
    if old:
        if old.fingerprint != fingerprint:
            raise HTTPException(409, 'connection_activation_request_key_conflict')
        # Immutable consent replay is not a renewed grant or a health assertion.
        return public(old, True)
    grant = await db.scalar(select(TenantConnectionGrant).where(
        TenantConnectionGrant.workspace_id == workspace, TenantConnectionGrant.reference_id == reference_id,
        TenantConnectionGrant.id == grant_id).with_for_update())
    if not grant:
        raise HTTPException(404, 'connection_grant_not_found')
    if ref.revision != body.reference_revision or grant.revision != body.grant_revision:
        raise HTTPException(409, 'connection_activation_revision_conflict')
    await grants.check_staged_grant(db, workspace, Principal(grant.grantee_id, 0), ref.id, grant.id,
                                   grant.brand_id, None, ref.revision)
    if await db.scalar(select(ModelGrantActivation.id).where(ModelGrantActivation.grant_id == grant.id)):
        raise HTTPException(409, 'connection_grant_already_activated')
    row = ModelGrantActivation(workspace_id=workspace, grant_id=grant.id, actor_id=who.id,
        reference_revision=ref.revision, grant_revision=grant.revision, source_stamp=ref.source_stamp,
        capability=CAPABILITY, request_key=str(body.request_key), fingerprint=fingerprint)
    db.add(row)
    await db.flush()
    await db.commit()
    return public(row)


async def pin(db, workspace, actor_id, brand_id, grant_id):
    # Same lock as legacy admission; consent/revoke takes workspace FOR UPDATE.
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update(read=True, key_share=True))
    grant = await db.scalar(select(TenantConnectionGrant).where(
        TenantConnectionGrant.id == grant_id, TenantConnectionGrant.workspace_id == workspace,
        TenantConnectionGrant.grantee_id == actor_id).execution_options(populate_existing=True))
    if not grant:
        raise EngineFailure(DENIED)
    ref = await db.scalar(select(TenantConnectionReference).where(
        TenantConnectionReference.id == grant.reference_id, TenantConnectionReference.workspace_id == workspace)
        .execution_options(populate_existing=True))
    activation = await db.scalar(select(ModelGrantActivation).where(
        ModelGrantActivation.workspace_id == workspace, ModelGrantActivation.grant_id == grant.id))
    if (not ref or ref.kind not in ('model', 'cli_model') or not activation or activation.actor_id != ref.manager_id
            or activation.reference_revision != ref.revision or activation.grant_revision != grant.revision
            or activation.source_stamp != ref.source_stamp or activation.capability != CAPABILITY):
        raise EngineFailure(DENIED)
    try:
        await grants.check_staged_grant(db, workspace, Principal(actor_id, 0), ref.id, grant.id,
                                       brand_id, None, ref.revision)
    except HTTPException:
        raise EngineFailure(DENIED) from None
    return {'version': 'p84-cli-grant-v1' if ref.kind == 'cli_model' else VERSION,
            **({'source_kind':'cli_model'} if ref.kind == 'cli_model' else {}),
            'mode': 'model_grant', 'workspace_id': workspace,
            'actor_id': actor_id, 'brand_id': brand_id, 'source_id': ref.source_id,
            'reference_id': ref.id, 'reference_revision': ref.revision,
            'grant_id': grant.id, 'grant_revision': grant.revision, 'activation_id': activation.id,
            'expires_at': grant.expires_at.isoformat(), 'capability': CAPABILITY}


async def check(db, run, chat, value):
    selected = value.get('connection_authority')
    if not isinstance(selected, dict) or not isinstance(selected.get('grant_id'), str):
        raise EngineFailure('engine_snapshot_incompatible')
    brand = (run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id
    current = await pin(db, run.workspace_id, chat.user_id, brand, selected['grant_id'])
    if selected != current or current['source_id'] != value.get('connection_id'):
        raise EngineFailure('engine_snapshot_incompatible')
    if run.brain_id:
        from ..brains.context import check_run_brain
        try:
            brain = await check_run_brain(db, run, chat)
        except HTTPException:
            raise EngineFailure(DENIED) from None
        if brain.workspace_id != run.workspace_id or brain.brand_id != brand:
            raise EngineFailure(DENIED)
