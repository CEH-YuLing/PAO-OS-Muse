"""Installation inference resources; caller data and accounting stay tenant-local.

References encrypted native connections, never copies keys or login caches. Only
operator-provisioned installation managers publish resources. A saved personal
CLI login is not silently promoted to a provider-supported shared identity.
"""
from sqlalchemy import select, text
from ...config import settings
from ...models import User, Workspace, Brand, ModelProviderConnection, CliModelConnection
from ..engines.contract import EngineFailure
from ..engines.service import digest
from ..connections.enterprise_ai import actor
from .models import InstallationAIResource, InstallationAIRevision
from .catalog import normalize, selection

VERSION = 'installation-ai-v1'


def enabled():
    return settings().installation_ai_enabled


async def manager(db, uid):
    return bool(enabled() and uid in settings().installation_ai_manager_ids
                and await db.scalar(select(User.id).where(User.id == uid, User.active.is_(True))))


async def lock(db):
    # One short registry publication lock, never held over provider I/O.
    await db.execute(text('SELECT pg_advisory_xact_lock(170211, 75)'))


async def source(db, row):
    # Native credentials have not moved out of their original SME. Publishing a
    # resource cannot keep borrowing them after its custodian loses access there.
    await actor(db,row.source_workspace_id,row.owner_id,managing=True)
    if row.source_kind=='cli' and row.provider=='muse':
        from ..cli_connections.muse_resource import SOURCE_ID,stamp
        if row.source_id!=SOURCE_ID:raise EngineFailure('installation_ai_source_unavailable')
        return stamp()
    if row.source_kind == 'api':
        value = await db.get(ModelProviderConnection, row.source_id, populate_existing=True)
        if not value or value.workspace_id != row.source_workspace_id or value.provider != row.provider or value.status != 'connected':
            raise EngineFailure('installation_ai_source_unavailable')
        # Default model is deliberately not identity. Selection lives on each run.
        return digest({'id': value.id, 'workspace': value.workspace_id, 'provider': value.provider,
                       'credential': digest(value.api_key_ciphertext), 'status': value.status})
    if row.source_kind == 'cli':
        from ..cli_connections.service import pin, source as cli_source
        value = await cli_source(db, row.source_workspace_id, row.owner_id, row.source_id)
        return digest(pin(value))
    raise EngineFailure('installation_ai_source_unavailable')


async def ready(db, row):
    if not enabled() or not row or not row.enabled:
        raise EngineFailure('installation_ai_resource_disabled')
    if not await manager(db, row.owner_id):
        raise EngineFailure('installation_ai_manager_revoked')
    if await source(db, row) != row.source_stamp:
        raise EngineFailure('installation_ai_source_changed')
    if row.source_kind == 'cli' and row.provider!='muse':
        # No currently implemented shared CLI adapter passes provider identity,
        # dispatch isolation and tool-free gates. Do not relabel a personal pin.
        raise EngineFailure('installation_ai_cli_adapter_pending')
    return row


async def record(db, row, uid, key, fingerprint, *, catalog_capture=False):
    db.add(InstallationAIRevision(resource_id=row.id, actor_id=uid, revision=row.revision,
        request_key=key, fingerprint=fingerprint, content={
            'provider': row.provider, 'enabled': row.enabled, 'is_default': row.is_default,
            'source_stamp': row.source_stamp, 'catalog_hash': digest(row.catalog),
            'default_model': row.default_model, 'catalog_capture': catalog_capture}))


async def capture(db, uid, wid, source_id, kind, catalog):
    """Called only after native, admitted catalog read; not a client supplied list.

    Capturing metadata never enables inference. A refresh invalidates old queued
    selections via revision, including when credentials or catalog are changed.
    """
    if not await manager(db, uid):
        return
    rows = normalize(catalog)
    cls = ModelProviderConnection if kind == 'api' else CliModelConnection
    native = await db.get(cls, source_id)
    if not native or native.workspace_id != wid or kind == 'cli' and native.owner_id != uid:
        raise EngineFailure('installation_ai_source_unavailable')
    await lock(db)
    row = await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider == native.provider).with_for_update())
    if row and (row.source_id != source_id or row.owner_id != uid):
        # Another manager cannot overwrite the published resource by listing a
        # different SME's similarly named provider. Replacement is separate work.
        raise EngineFailure('installation_ai_source_conflict')
    if not row:
        row = InstallationAIResource(provider=native.provider, owner_id=uid,
            source_workspace_id=wid, source_id=source_id, source_kind=kind,
            revision=1, enabled=False, is_default=False, source_stamp='0'*64,
            catalog=rows, default_model=native.model if native.model in {v['model'] for v in rows} else rows[0]['model'])
        db.add(row)
        await db.flush()
    else:
        row.revision += 1
        row.catalog = rows
        if row.default_model not in {v['model'] for v in rows}:
            row.enabled = row.is_default = False
            row.default_model = rows[0]['model']
    stamp = await source(db, row)
    if row.source_stamp != stamp:
        row.enabled = row.is_default = False
    row.source_stamp = stamp
    from uuid import uuid4
    await record(db, row, uid, str(uuid4()), digest({'capture': row.revision, 'stamp': stamp, 'catalog': rows}), catalog_capture=True)


async def config(db, wid, uid, brand, resource_id, model=None, effort=None):
    if not enabled():
        raise EngineFailure('installation_ai_disabled')
    epoch = await db.scalar(select(Workspace.lifecycle_version).where(Workspace.id == wid).with_for_update(read=True, key_share=True))
    member = await actor(db, wid, uid)
    if brand and not await db.scalar(select(Brand.id).where(Brand.id == brand, Brand.workspace_id == wid)):
        raise EngineFailure('installation_ai_scope_denied')
    row = await db.get(InstallationAIResource, resource_id, populate_existing=True)
    await ready(db, row)
    try:
        chosen = selection(row.catalog, model or row.default_model, effort)
        if row.provider=='muse' and chosen['reasoning_effort'] is None:
            chosen['reasoning_effort']=next(v['default_effort'] for v in row.catalog if v['model']==chosen['model'])
        from .modalities import require_chat
        require_chat(row.provider, chosen['model'], next(v for v in row.catalog if v['model']==chosen['model']))
        if row.provider == 'openai':
            from .openai_effort import validate
            validate(chosen['model'], chosen['reasoning_effort'])
        if row.provider in ('anthropic', 'gemini'):
            from .api_effort import validate
            validate(row.provider, chosen['model'], chosen['reasoning_effort'])
    except ValueError as exc:
        raise EngineFailure(str(exc)) from None
    authority = {'version': VERSION, 'mode': 'installation_resource', 'resource_id': row.id,
        'resource_revision': row.revision, 'source_stamp': row.source_stamp,
        'workspace_id': wid, 'actor_id': uid, 'actor_role': member.role, 'brand_id': brand,
        'membership_epoch': epoch, 'auth_version': await db.scalar(select(User.auth_version).where(User.id == uid))}
    return {'provider': row.provider, **chosen, 'connection_id': row.source_id, 'connection_authority': authority}


async def default_config(db, wid, uid, brand):
    if not enabled():
        return None
    row = await db.scalar(select(InstallationAIResource).where(InstallationAIResource.enabled.is_(True), InstallationAIResource.is_default.is_(True)))
    if row:
        return await config(db, wid, uid, brand, row.id)
    return None


async def check(db, run, chat, value):
    selected = value.get('connection_authority') or {}
    brand = (run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id
    current = await config(db, run.workspace_id, chat.user_id, brand, selected.get('resource_id'),
                           value.get('model'), value.get('reasoning_effort'))
    if current != {k: value[k] for k in current if k in value}:
        raise EngineFailure('installation_ai_selection_changed')
    if current['connection_authority']['actor_role'] == 'viewer' and value.get('interaction_mode') != 'read_only_ai':
        raise EngineFailure('installation_ai_read_only_required')
    if run.brain_id:
        from ..brains.context import check_run_brain
        await check_run_brain(db, run, chat)


async def catalog(db, wid, uid):
    await actor(db, wid, uid)
    result = []
    for row in await db.scalars(select(InstallationAIResource).order_by(InstallationAIResource.provider)):
        error = None
        try:
            await ready(db, row)
        except EngineFailure as exc:
            error = exc.code
        # Metadata is deliberately distinct from inference and quota evidence.
        # Do not manufacture timestamps for legacy captures. Successful usage
        # is caller-SME scoped and must match the exact current resource revision.
        from ...models import Run, LlmAttempt
        capture_at = await db.scalar(select(InstallationAIRevision.created_at).where(
            InstallationAIRevision.resource_id == row.id,
            InstallationAIRevision.content['catalog_capture'].as_boolean().is_(True)
        ).order_by(InstallationAIRevision.revision.desc()).limit(1))
        success = (await db.execute(select(LlmAttempt.model,LlmAttempt.finished_at).join(Run,Run.id==LlmAttempt.run_id).where(
            LlmAttempt.workspace_id==wid, LlmAttempt.status=='completed',
            LlmAttempt.finished_at.is_not(None),
            LlmAttempt.provider==row.provider,
            Run.engine_snapshot['connection_authority']['resource_id'].as_string()==row.id,
            Run.engine_snapshot['connection_authority']['resource_revision'].as_integer()==row.revision
        ).order_by(LlmAttempt.finished_at.desc()).limit(1))).first()
        from .modalities import detail
        result.append({'provider': row.provider, 'installation_resource_id': row.id,
            'models': [v['model'] for v in row.catalog], 'model_details': [detail(row.provider,v) for v in row.catalog],
            'local': False, 'error': error,
            'catalog_evidence': {'revision':row.revision,'sha256':digest(row.catalog),
                'source_kind':row.source_kind,'observed_at':capture_at.isoformat() if capture_at else None},
            'inference_evidence': {'state':'observed_success' if success else 'not_verified',
                'model':success.model if success else None,
                'observed_at':success.finished_at.isoformat() if success else None,
                'scope':'caller_workspace','current_health':'not_probed'},
            'quota_evidence': {'state':'unknown','remaining':None,'provider_calls':False}})
    return result
