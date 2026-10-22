"""Staged reference/grant persistence. No credential engine or runtime authority."""
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import Text, cast, func, select

from ...auth import Principal
from ...models import (
    Brain, BrainMember, ConnectorSecret, Member, TenantConnectionAudit,
    TenantConnectionGrant, TenantConnectionReference, User, Workspace, now,
)
from ..studio.contracts import digest
from .inventory import SOURCES, account_known, connection_metadata, grantee, manager


def denied():
    raise HTTPException(403, 'connection_staged_grant_not_eligible')


def hashed(column):
    # Database computes the fingerprint; no plaintext/ciphertext value is loaded.
    return func.encode(func.sha256(func.convert_to(func.coalesce(cast(column, Text), ''), 'UTF8')), 'hex')


async def source_stamp(db, workspace, kind, source_id, manager_id):
    meta = await connection_metadata(db, workspace, Principal(manager_id, 0), kind, source_id)
    model, _, credential = SOURCES[kind]
    if kind == 'mcp':
        secret = select(hashed(ConnectorSecret.ciphertext)).where(
            ConnectorSecret.connection_id == model.id, ConnectorSecret.workspace_id == workspace).scalar_subquery()
        columns = [secret, hashed(model.endpoint), hashed(model.permissions), model.manifest_hash, model.brain_id]
    elif kind == 'cli_model':
        columns = [model.device_id, model.profile_id, model.model, model.binary_sha256,
                   model.binary_version, model.runtime_image_id, model.auth_checked_at]
    elif kind == 'model':
        columns = [hashed(credential), hashed(model.model), model.is_default]
    else:
        columns = [hashed(credential), hashed(model.scopes)]
        if kind == 'meta_ads':
            columns.append(model.expires_at)
    row = (await db.execute(select(*columns).where(model.id == source_id, model.workspace_id == workspace))).first()
    if row is None:
        raise HTTPException(404, 'connection_mapping_source_not_found')
    values = [value.isoformat() if hasattr(value, 'isoformat') else value for value in row]
    if kind == 'cli_model':
        from ..cli_connections.runtime import host_digest
        values.append(host_digest())
    return meta, digest({'identity': meta['identity'], 'manager_id': meta['manager_id'],
                         'source_version': meta['config_version'], 'stored_status': meta['stored_status'], 'config': values})


async def active_member(db, workspace, user_id, managing=False, lock=False):
    query = select(Member).join(User, User.id == Member.user_id).where(
        Member.workspace_id == workspace, Member.user_id == user_id, User.active.is_(True))
    if lock:
        query = query.with_for_update()
    member = await db.scalar(query.execution_options(populate_existing=True))
    allowed = ('owner', 'admin') if managing else ('owner', 'admin', 'operator', 'analyst')
    if not member or member.role not in allowed:
        denied()
    return member


def source_ready(meta):
    return (meta['stored_status'] == 'connected' and
            (meta.get('authentication_ready') is True if meta['identity']['kind'] == 'cli_model'
             else meta['credential_present']))


async def managed(db, workspace, reference_id, who, lock=False):
    await manager(db, workspace, who)
    query = select(TenantConnectionReference).where(
        TenantConnectionReference.id == reference_id, TenantConnectionReference.workspace_id == workspace,
        TenantConnectionReference.manager_id == who.id)
    if lock:
        query = query.with_for_update()
    row = await db.scalar(query.execution_options(populate_existing=True))
    if not row:
        raise HTTPException(404, 'connection_reference_not_found')
    return row


def public_grant(row):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'reference_id': row.reference_id,
            'reference_revision': row.reference_revision, 'revision': row.revision,
            'grantee_id': row.grantee_id, 'brand_id': row.brand_id, 'account_id': row.account_id,
            'permission': row.permission, 'expires_at': row.expires_at, 'status': row.status,
            'execution_enabled': False, 'worker_integration': 'pending_S2.1B2'}


def public_reference(row):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'kind': row.kind,
            'source_id': row.source_id, 'provider': row.provider, 'manager_id': row.manager_id,
            'source_version': row.source_version, 'revision': row.revision, 'status': row.status,
            'generation': row.generation, 'supersedes_id': row.supersedes_id,
            'execution_enabled': False, 'worker_integration': 'pending_S2.1B2'}


def audit(db, ref, actor, action, grant=None):
    db.add(TenantConnectionAudit(workspace_id=ref.workspace_id, reference_id=ref.id,
        grant_id=grant.id if grant else None, actor_id=actor, action=action,
        data={'reference_revision': ref.revision, **({'grant_revision': grant.revision} if grant else {})}))


async def stage(db, workspace, who, body, make_preview, *, generation_from=None):
    await manager(db, workspace, who)
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await active_member(db, workspace, who.id, managing=True, lock=True)
    payload={'workspace_id': workspace, 'actor_id': who.id, 'body': body.model_dump(mode='json')}
    if generation_from is not None:payload['supersedes_reference_id']=generation_from.id
    fingerprint = digest(payload)
    old = await db.scalar(select(TenantConnectionGrant).where(
        TenantConnectionGrant.workspace_id == workspace, TenantConnectionGrant.creator_id == who.id,
        TenantConnectionGrant.request_key == str(body.request_key)))
    if old:
        if old.fingerprint != fingerprint:
            raise HTTPException(409, 'connection_mapping_request_key_conflict')
        ref = await managed(db, workspace, old.reference_id, who)
        return {'reference': public_reference(ref), 'grant': public_grant(old), 'replayed': True}
    source_id = str(body.connection_id)
    model = SOURCES[body.kind][0]
    await db.scalar(select(model.id).where(model.id == source_id, model.workspace_id == workspace).with_for_update())
    preview = await make_preview()
    if preview['preview_hash'] != body.preview_hash:
        raise HTTPException(409, 'connection_mapping_preview_changed')
    selected_manager = str(body.manager_id) if body.manager_id is not None else None
    if body.kind == 'model' and selected_manager != who.id:
        raise HTTPException(422, 'connection_model_manager_explicit_self_required')
    if body.kind != 'model' and selected_manager not in (None, who.id):
        raise HTTPException(422, 'connection_native_manager_cannot_transfer')
    await active_member(db, workspace, str(body.grantee_id), lock=True)
    if body.kind == 'cli_model' and str(body.grantee_id) != who.id:
        raise HTTPException(422, 'cli_personal_account_self_only')
    meta, stamp = await source_stamp(db, workspace, body.kind, source_id, who.id)
    ref = await db.scalar(select(TenantConnectionReference).where(
        TenantConnectionReference.workspace_id == workspace, TenantConnectionReference.kind == body.kind,
        TenantConnectionReference.source_id == source_id).order_by(TenantConnectionReference.generation.desc())
        .limit(1).with_for_update().execution_options(populate_existing=True))
    parent=None
    if generation_from is not None:
        if not ref or ref.id!=generation_from.id or ref.manager_id!=who.id:
            raise HTTPException(409,'connection_generation_parent_conflict')
        if ref.revision!=body.reference_revision:
            raise HTTPException(409,'connection_reference_revision_conflict')
        if ref.status=='staged' and ref.source_stamp==stamp:
            raise HTTPException(409,'connection_generation_no_change')
        if not source_ready(meta):
            raise HTTPException(409,'connection_generation_source_not_ready')
        if body.kind=='meta_ads':
            expires=await db.scalar(select(model.expires_at).where(model.id==source_id))
            if expires is None or expires<=now():raise HTTPException(409,'connection_generation_source_not_ready')
        old_grants=list(await db.scalars(select(TenantConnectionGrant).where(
            TenantConnectionGrant.workspace_id==workspace,TenantConnectionGrant.reference_id==ref.id).with_for_update()))
        for old_grant in old_grants:
            if old_grant.status=='staged':
                old_grant.status='revoked';old_grant.revision+=1;audit(db,ref,who.id,'grant_revoked',old_grant)
        if ref.status=='staged':
            ref.status='revoked';ref.revision+=1;audit(db,ref,who.id,'reference_revoked')
        await db.flush();parent=ref;ref=None
    if ref:
        if ref.manager_id != who.id or ref.status != 'staged' or ref.source_stamp != stamp:
            raise HTTPException(409, 'connection_reference_changed_or_revoked')
    else:
        count = await db.scalar(select(func.count()).select_from(TenantConnectionReference).where(TenantConnectionReference.workspace_id == workspace))
        if count >= 100:
            raise HTTPException(409, 'connection_reference_storage_limit')
        ref = TenantConnectionReference(workspace_id=workspace, kind=body.kind, source_id=source_id,
            provider=meta['identity']['provider'], manager_id=who.id, source_version=meta['config_version'],
            generation=parent.generation+1 if parent else 1,supersedes_id=parent.id if parent else None,
            source_stamp=stamp, revision=1, status='staged')
        db.add(ref)
        await db.flush()
        audit(db, ref, who.id, 'reference_staged')
    count = await db.scalar(select(func.count()).select_from(TenantConnectionGrant).where(TenantConnectionGrant.workspace_id == workspace))
    if count >= 500:
        raise HTTPException(409, 'connection_grant_storage_limit')
    grant = TenantConnectionGrant(workspace_id=workspace, reference_id=ref.id, reference_revision=ref.revision,
        creator_id=who.id, grantee_id=str(body.grantee_id), brand_id=str(body.brand_id) if body.brand_id else None,
        account_id=body.account_id, permission=body.permission, request_key=str(body.request_key),
        fingerprint=fingerprint, ttl_minutes=body.ttl_minutes, expires_at=now()+timedelta(minutes=body.ttl_minutes),
        revision=1, status='staged')
    db.add(grant)
    await db.flush()
    audit(db, ref, who.id, 'grant_staged', grant)
    await db.commit()
    return {'reference': public_reference(ref), 'grant': public_grant(grant), 'replayed': False}


async def check_staged_grant(db, workspace, who, reference_id, grant_id, brand_id, account_id, reference_revision):
    """Eligibility only; B2 must wire/pin/recheck it before any actual execution."""
    await active_member(db, workspace, who.id)
    grant = await db.scalar(select(TenantConnectionGrant).where(
        TenantConnectionGrant.id == grant_id, TenantConnectionGrant.workspace_id == workspace,
        TenantConnectionGrant.reference_id == reference_id, TenantConnectionGrant.grantee_id == who.id))
    if not grant:
        raise HTTPException(404, 'connection_grant_not_found')
    ref = await db.scalar(select(TenantConnectionReference).where(
        TenantConnectionReference.id == reference_id, TenantConnectionReference.workspace_id == workspace))
    if (not ref or ref.status != 'staged' or grant.status != 'staged' or grant.expires_at <= now()
            or ref.revision != reference_revision or grant.reference_revision != ref.revision
            or grant.brand_id != brand_id or grant.account_id != account_id):
        denied()
    await active_member(db, workspace, ref.manager_id, managing=True)
    try:
        meta, stamp = await source_stamp(db, workspace, ref.kind, ref.source_id, ref.manager_id)
    except HTTPException:
        denied()
    if stamp != ref.source_stamp or not source_ready(meta):
        denied()
    if ref.kind == 'cli_model' and (ref.manager_id != who.id or grant.grantee_id != ref.manager_id):
        denied()
    if ref.kind == 'meta_ads':
        model = SOURCES[ref.kind][0]
        expires = await db.scalar(select(model.expires_at).where(model.id == ref.source_id, model.workspace_id == workspace))
        if expires is None or expires <= now():
            denied()
    if ref.kind == 'mcp':
        model = SOURCES['mcp'][0]
        brain_id = await db.scalar(select(model.brain_id).where(model.id == ref.source_id, model.workspace_id == workspace))
        if brain_id:
            brain = await db.get(Brain, brain_id)
            member = await db.get(BrainMember, (brain_id, who.id))
            if (not brain or brain.workspace_id != workspace or brain.archived_at or
                    (brain.owner_id != who.id and (not member or member.workspace_id != workspace)) or
                    (brain.brand_id is not None and brain.brand_id != brand_id)):
                denied()
    if ref.kind in ('meta_ads', 'google_ads'):
        if not account_id:
            denied()
        try:
            await account_known(db, workspace, ref.kind, ref.source_id, ref.source_version, account_id)
        except HTTPException:
            denied()
    return {'reference_id': ref.id, 'reference_revision': ref.revision, 'grant_id': grant.id,
            'grant_revision': grant.revision, 'eligible_for_staged_read_only': True,
            'execution_enabled': False, 'worker_integration': 'pending_S2.1B2'}


async def revoke(db, workspace, who, reference_id, expected_reference, grant_id=None, expected_grant=None):
    await manager(db, workspace, who)
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace).with_for_update())
    await active_member(db, workspace, who.id, managing=True, lock=True)
    ref = await managed(db, workspace, reference_id, who, lock=True)
    if ref.revision != expected_reference:
        raise HTTPException(409, 'connection_reference_revision_conflict')
    query = select(TenantConnectionGrant).where(
        TenantConnectionGrant.reference_id == ref.id, TenantConnectionGrant.workspace_id == workspace).with_for_update()
    if grant_id:
        query = query.where(TenantConnectionGrant.id == grant_id)
    rows = list(await db.scalars(query))
    if grant_id and (not rows or rows[0].revision != expected_grant):
        raise HTTPException(409, 'connection_grant_revision_conflict')
    for grant in rows:
        if grant.status == 'staged':
            grant.status = 'revoked'; grant.revision += 1
            audit(db, ref, who.id, 'grant_revoked', grant)
    if not grant_id and ref.status == 'staged':
        ref.status = 'revoked'; ref.revision += 1
        audit(db, ref, who.id, 'reference_revoked')
    await db.commit()
    return {'reference': public_reference(ref), 'grants': [public_grant(row) for row in rows]}
