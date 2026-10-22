"""B2a fail-closed model fence. Staged grants NEVER authorize execution.

Explicit B2b model consent/pins supplement the legacy unregistered path.
B1 staged data alone never grants inference. Completed runs are never repinned.
"""
from sqlalchemy import select
from fastapi import HTTPException

from ...db import Session
from ...models import ChatSession, ModelProviderConnection, TenantConnectionReference, Workspace
from ..engines.contract import EngineFailure

VERSION = 's21b2a-legacy-model-fence-v1'
DENIED = 'engine_connection_authority_not_activated'


async def unregistered(db, workspace_id, source_id=None):
    # Mapping/revoke takes Workspace FOR UPDATE. Holding KEY SHARE until this
    # transaction ends linearizes credential admission/publication with mapping.
    await db.scalar(select(Workspace.id).where(Workspace.id == workspace_id)
                    .with_for_update(read=True, key_share=True))
    query = select(TenantConnectionReference.id).where(
        TenantConnectionReference.workspace_id == workspace_id,
        TenantConnectionReference.kind == 'model')
    if source_id is not None:
        query = query.where(TenantConnectionReference.source_id == source_id)
    # Revoked/tombstoned references must not restore legacy access. Do not filter
    # status, grantee, expiry or manager; no active-authority concept exists yet.
    if await db.scalar(query.limit(1)):
        raise EngineFailure(DENIED)


async def pin_legacy(db, run, chat, source_id):
    await unregistered(db, run.workspace_id, source_id)
    return {'version': VERSION, 'mode': 'legacy_unregistered',
            'workspace_id': run.workspace_id, 'actor_id': chat.user_id,
            'brand_id': (run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id,
            'source_id': source_id}


async def check_source(db, workspace_id, value):
    authority=value.get('connection_authority') or {}
    if authority.get('mode')=='installation_resource':
        from ..installation_ai.service import config
        current=await config(db,workspace_id,authority.get('actor_id'),authority.get('brand_id'),
            authority.get('resource_id'),value.get('model'),value.get('reasoning_effort'))
        if current['connection_authority']!=authority or current['connection_id']!=value.get('connection_id'):
            raise EngineFailure('installation_ai_selection_changed')
        return
    if value.get('provider') == 'codex_cli':
        from ..cli_connections.service import check_source as cli_source
        return await cli_source(db, workspace_id, value)
    from .grants import hashed
    row = (await db.execute(select(ModelProviderConnection.provider,
        ModelProviderConnection.status, hashed(ModelProviderConnection.api_key_ciphertext),ModelProviderConnection.model).where(
        ModelProviderConnection.id == value.get('connection_id'),
        ModelProviderConnection.workspace_id == workspace_id))).first()
    probe=value.get('management_probe') is True
    expected_status=value.get('status') if probe else 'connected'
    if probe:
        from ...models import Member,User
        member=await db.scalar(select(Member.role).join(User,User.id==Member.user_id).where(
            Member.workspace_id==workspace_id,Member.user_id==value.get('actor_id'),User.active.is_(True)))
        if member not in ('owner','admin') or expected_status not in ('connected','error'):
            raise EngineFailure('access_revoked')
    if not row or row[0] != value.get('provider') or row[1] != expected_status:
        raise EngineFailure('engine_connection_unavailable')
    if row[2] != value.get('credential_binding'):
        raise EngineFailure('engine_connection_changed')
    # A management probe tests CURRENT configuration. A durable run intentionally
    # keeps its selected model when only the native default changes. Registered
    # grants still check the complete immutable source stamp in model_authority.
    if probe and value.get('model') is not None and row[3]!=value['model']:
        raise EngineFailure('engine_connection_changed')


async def check_run(db, run):
    from ..business_planning.jobs import guard_run
    await guard_run(db, run)
    value = run.engine_snapshot
    if value is None:
        # Old unpinned resolver has no actor/source authority pins. It cannot
        # choose another cloud connection or local fallback once models map.
        await unregistered(db, run.workspace_id)
        return
    if value.get('provider') in ('ollama', 'knowledge'):
        return  # Explicit local/grounded selection is not a cloud fallback.
    source_id = value.get('connection_id')
    if not source_id:
        raise EngineFailure('engine_snapshot_incompatible')
    chat = await db.get(ChatSession, run.session_id)
    if not chat or chat.workspace_id != run.workspace_id:
        raise EngineFailure('engine_snapshot_incompatible')
    pin = value.get('connection_authority')
    if isinstance(pin,dict) and pin.get('mode')=='installation_resource':
        from ..installation_ai.service import check
        await check(db,run,chat,value)
        return
    if isinstance(pin, dict) and pin.get('mode') == 'personal_cli':
        from ..cli_connections.personal import check
        await check(db, run, chat, value)
        await check_source(db, run.workspace_id, value)
        return
    if isinstance(pin, dict) and pin.get('mode') == 'enterprise_policy':
        from .enterprise_ai import check
        await check(db, run, chat, value)
        await check_source(db, run.workspace_id, value)
        return
    if value.get('provider') == 'codex_cli' and (not isinstance(pin, dict) or pin.get('mode') != 'model_grant'):
        raise EngineFailure('engine_connection_grant_denied')
    if isinstance(pin, dict) and pin.get('mode') == 'model_grant':
        from .model_authority import check
        await check(db, run, chat, value)
        await check_source(db, run.workspace_id, value)
        return
    if pin is not None:
        if (not isinstance(pin, dict) or set(pin) != {'version', 'mode', 'workspace_id', 'actor_id', 'brand_id', 'source_id'}
                or pin['version'] != VERSION or pin['mode'] != 'legacy_unregistered'
                or pin['workspace_id'] != run.workspace_id or pin['source_id'] != source_id
                or not chat or chat.workspace_id != run.workspace_id or pin['actor_id'] != chat.user_id
                or pin['brand_id'] != ((run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id)):
            raise EngineFailure('engine_snapshot_incompatible')
    # Missing pin means historical legacy, NOT an implicit grant. It is still
    # rechecked against registration; never mutate/rewrite the old snapshot.
    await unregistered(db, run.workspace_id, source_id)
    from .grants import active_member
    try:
        await active_member(db, run.workspace_id, chat.user_id)
    except HTTPException:
        raise EngineFailure('engine_connection_access_revoked') from None
    await check_source(db, run.workspace_id, value)


class ModelFenceGateway:
    """Recheck per call and before exposing results; no transaction over network.

    This cannot undo bytes already sent before mapping commits. Publication
    must recheck in its own transaction too. Not a native provider cancellation.
    """
    def __init__(self, gateway, workspace_id, *, run=None, source_pin=None):
        self._gateway, self.workspace_id, self.run = gateway, workspace_id, run
        self._source_pin = dict(source_pin) if source_pin is not None else None
        self.provider_name, self.model_name = gateway.provider_name, gateway.model_name

    @property
    def last_usage(self):
        return getattr(self._gateway, 'last_usage', {})

    async def check(self):
        async with Session.begin() as db:
            if self.run is None:
                probe=self._source_pin and self._source_pin.get('management_probe') is True
                await unregistered(db, self.workspace_id,self._source_pin.get('connection_id') if probe else None)
                if self._source_pin is not None:
                    await check_source(db, self.workspace_id, self._source_pin)
            else:
                await check_run(db, self.run)

    async def plan(self, messages):
        await self.check()
        result = await self._gateway.plan(messages)
        await self.check()
        return result

    async def extract(self, prompt):
        await self.check()
        result = await self._gateway.extract(prompt)
        await self.check()
        return result

    async def stream(self, messages, max_tokens=None):
        await self.check()
        source = self._gateway.stream(messages, max_tokens=max_tokens)
        try:
            async for chunk in source:
                await self.check()
                yield chunk
            await self.check()
        finally:
            close = getattr(source, 'aclose', None)
            if close:
                await close()
