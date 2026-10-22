"""Read-only projections: never load/decrypt credentials or probe a provider.

This is an inventory, not a resolver or a grant. Preserve native ownership until
an explicitly reviewed migration and execution fence replace it.
"""
from fastapi import HTTPException
from sqlalchemy import and_, exists, or_, select

from ...access import membership
from ...models import (
    AdEntity, Brain, BrainMember, ConnectorConnection, ConnectorSecret,
    GoogleAdsConnection, GoogleAdsSyncJob, Member, MetaConnection, MetaSnapshot, MetaSyncJob,
    ModelProviderConnection, CliModelConnection, User,
)

SOURCES = {
    'cli_model': (CliModelConnection, CliModelConnection.owner_id, None),
    'model': (ModelProviderConnection, None, ModelProviderConnection.api_key_ciphertext),
    'mcp': (ConnectorConnection, ConnectorConnection.owner_id, None),
    'meta_ads': (MetaConnection, MetaConnection.user_id, MetaConnection.token_ciphertext),
    'google_ads': (GoogleAdsConnection, GoogleAdsConnection.user_id, GoogleAdsConnection.refresh_token_ciphertext),
}

# Fixed code inventory only; no installation config/secret-presence introspection.
LEGACY = [
    {'provider': 'telegram', 'scope': 'installation_local', 'next_checkpoint': 'S3',
     'mapping': 'explicit_bot_and_workspace_selection_required'},
    {'provider': 'ollama', 'scope': 'installation_local', 'next_checkpoint': 'S2.2',
     'mapping': 'shared_compute_not_shared_tenant_context'},
    {'provider': 'meta_app', 'scope': 'installation_local', 'next_checkpoint': 'S4',
     'mapping': 'managed_or_byo_app_required'},
    {'provider': 'google_ads_app', 'scope': 'installation_local', 'next_checkpoint': 'S4',
     'mapping': 'managed_or_byo_app_required'},
]


async def manager(db, workspace_id, who):
    member = await membership(db, workspace_id, who)
    if member.role not in ('owner', 'admin'):
        raise HTTPException(403, 'connection_inventory_manager_required')


def projection(kind, workspace_id, actor_id):
    model, owner, credential = SOURCES[kind]
    if kind == 'cli_model':
        present = and_(model.auth_checked_at.is_not(None), model.status == 'connected')
    elif kind == 'mcp':
        present = exists(select(ConnectorSecret.id).where(
            ConnectorSecret.connection_id == model.id,
            ConnectorSecret.workspace_id == model.workspace_id,
            ConnectorSecret.ciphertext.is_not(None), ConnectorSecret.ciphertext != ''))
    else:
        present = and_(credential.is_not(None), credential != '')
    columns = [model.id, model.workspace_id, model.status, present.label('credential_present')]
    if owner is not None:
        columns.append(owner.label('owner_id'))
        columns.append(model.version)
        if kind == 'cli_model':
            columns.append(model.provider)
    else:
        columns.append(model.provider)
    query = select(*columns).where(model.workspace_id == workspace_id)
    if owner is not None:
        query = query.where(owner == actor_id)
    if kind == 'mcp':
        # Even tenant owners do not bypass a private/archived/foreign Brain.
        grant = exists(select(BrainMember.brain_id).where(
            BrainMember.brain_id == Brain.id, BrainMember.workspace_id == workspace_id,
            BrainMember.user_id == actor_id))
        brain = exists(select(Brain.id).where(
            Brain.id == model.brain_id, Brain.workspace_id == workspace_id,
            Brain.archived_at.is_(None), or_(Brain.owner_id == actor_id, grant)))
        query = query.where(or_(model.brain_id.is_(None), brain))
    return query


def public(kind, row):
    data = dict(row)
    return {
        'identity': {'workspace_id': data['workspace_id'], 'kind': kind,
                     'connection_id': data['id'], 'provider': data.get('provider', kind)},
        'ownership': 'workspace_unassigned_manager' if kind == 'model' else 'legacy_creator',
        'manager_id': data.get('owner_id'),
        'config_version': data.get('version'),
        'stored_status': data['status'], 'credential_present': bool(data['credential_present']) if kind != 'cli_model' else False,
        **({'authentication_ready': bool(data['credential_present']), 'auth_storage': 'isolated_local_cli_profile',
            'credential_stored_in_PAO': False} if kind == 'cli_model' else {}),
        'acceptance': 'not_verified_by_inventory', 'brand_account_grants': 'not_implemented',
        'migration_required': True,
    }


async def inventory(db, workspace_id, who, limit, offset):
    await manager(db, workspace_id, who)
    items, more = [], {}
    for kind, (model, _, _) in SOURCES.items():
        query = projection(kind, workspace_id, who.id).order_by(model.created_at, model.id)
        rows = list((await db.execute(query.offset(offset).limit(limit + 1))).mappings())
        more[kind] = len(rows) > limit
        items.extend(public(kind, row) for row in rows[:limit])
    return {
        'workspace_id': workspace_id, 'items': items,
        'page': {'limit_per_kind': limit, 'offset_per_kind': offset, 'has_more': more},
        'visibility': 'native_owner_and_brain_acl_preserved',
        'legacy_installation_sources': LEGACY,
        'unimplemented_providers': ['tiktok_ads', 'facebook_pages'],
        'external_calls': False, 'credentials_loaded': False, 'mutation_applied': False,
    }


async def connection_metadata(db, workspace_id, who, kind, connection_id):
    model = SOURCES[kind][0]
    row = (await db.execute(projection(kind, workspace_id, who.id).where(
        model.id == connection_id))).mappings().first()
    if row is None:
        raise HTTPException(404, 'connection_mapping_source_not_found')
    return public(kind, row)


async def grantee(db, workspace_id, user_id):
    role = await db.scalar(select(Member.role).join(User, User.id == Member.user_id).where(
        Member.workspace_id == workspace_id, Member.user_id == user_id, User.active.is_(True)))
    if role not in ('owner', 'admin', 'operator', 'analyst'):
        raise HTTPException(404, 'connection_mapping_grantee_not_found')
    return role


async def account_known(db, workspace_id, kind, connection_id, version, account_id):
    # Local provenance only. An Ads account ID is never global identity.
    column = AdEntity.connection_id if kind == 'meta_ads' else AdEntity.google_connection_id
    platform = 'meta' if kind == 'meta_ads' else 'google'
    model = SOURCES[kind][0]
    job = MetaSyncJob if kind == 'meta_ads' else GoogleAdsSyncJob
    source = AdEntity.source_job_id if kind == 'meta_ads' else AdEntity.google_source_job_id
    known = await db.scalar(select(AdEntity.id).join(model, model.id == column).join(job, job.id == source).where(
        model.workspace_id == workspace_id, column == connection_id,
        job.connection_id == connection_id, job.connection_version == version, job.status == 'completed',
        AdEntity.connection_version == version, AdEntity.platform == platform,
        AdEntity.kind == 'account', AdEntity.account_id == account_id,
        AdEntity.remote_id == account_id).limit(1))
    if not known and kind == 'meta_ads':
        known = await db.scalar(select(MetaSnapshot.id).join(MetaSyncJob).join(
            MetaConnection, MetaConnection.id == MetaSyncJob.connection_id).where(
                MetaConnection.workspace_id == workspace_id, MetaSyncJob.connection_id == connection_id,
                MetaSyncJob.connection_version == version, MetaSyncJob.status == 'completed',
                MetaSyncJob.kind == 'accounts', MetaSnapshot.kind == 'accounts',
                MetaSnapshot.remote_key == account_id).limit(1))
    if not known:
        raise HTTPException(404, 'connection_mapping_account_not_found')
