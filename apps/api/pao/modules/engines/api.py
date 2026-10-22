"""Four additive APIs; old session/run DTOs and SSE event enum are unchanged."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...access import membership, owned_run, owned_session
from ...auth import Principal, principal
from ...config import settings
from ...db import database
from ...models import ChatSession, ModelProviderConnection, CliModelConnection, ModelGrantActivation, Run, TenantConnectionGrant, TenantConnectionReference
from .contract import EngineFailure, capabilities
from .service import choose_config, default_config, local_models, public
from . import metadata
from .service import digest

router = APIRouter()


class EngineChoice(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    provider: Literal['ollama', 'openai', 'anthropic', 'gemini', 'openrouter', 'codex_cli','muse']
    model: str = Field(min_length=1, max_length=120, pattern=r'^[^\s\x00-\x1f\x7f]+$')
    version: int = Field(ge=1)
    grant_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    enterprise_source_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    personal_cli_source_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    installation_resource_id: str | None = Field(default=None, pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    reasoning_effort: str | None = Field(default=None,pattern=r'^[a-z][a-z0-9_-]{0,23}$')
    prepare_muse_context: bool = False


def view(chat, config):
    selection = public(config)
    authority = (config or {}).get('connection_authority')
    if selection and isinstance(authority,dict) and authority.get('mode')=='installation_resource':
        selection['installation_resource_id']=authority['resource_id']
    if selection and isinstance(authority, dict) and authority.get('mode') == 'model_grant':
        selection['grant_id'] = authority['grant_id']
    if selection and isinstance(authority, dict) and authority.get('mode') == 'enterprise_policy':
        selection['enterprise_source_id'] = authority['source_id']
    if selection and isinstance(authority, dict) and authority.get('mode') == 'personal_cli':
        selection['personal_cli_source_id'] = authority['source_id']
    return {'available': settings().engine_contract_enabled, 'version': chat.engine_version,
            'selection': selection, 'pinned': chat.engine_config is not None,
            'knowledge_override': chat.knowledge_enabled}


@router.get('/v1/workspaces/{workspace_id}/model-grants')
async def model_grants(workspace_id: UUID, response: Response, brand_id: UUID | None = None,
                       limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                       who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from ..connections.grants import active_member
    from ..connections.model_authority import pin
    workspace = str(workspace_id)
    member = await membership(db, workspace, who)
    if member.role == 'viewer':
        from ..connections.enterprise_ai import chat_access
        await chat_access(db, workspace, who)
        response.headers['Cache-Control'] = 'no-store'
        return {'items': [], 'has_more': False, 'acceptance': 'enterprise_read_only_no_personal_grants'}
    await active_member(db, workspace, who.id)
    response.headers['Cache-Control'] = 'no-store'
    query = (select(TenantConnectionGrant.id.label('id'), ModelProviderConnection.provider, ModelProviderConnection.model)
        .join(ModelGrantActivation, ModelGrantActivation.grant_id == TenantConnectionGrant.id)
        .join(TenantConnectionReference, TenantConnectionReference.id == TenantConnectionGrant.reference_id)
        .join(ModelProviderConnection, ModelProviderConnection.id == TenantConnectionReference.source_id)
        .where(TenantConnectionGrant.workspace_id == workspace, TenantConnectionGrant.grantee_id == who.id,
               ModelProviderConnection.workspace_id == workspace,
               TenantConnectionReference.kind == 'model',
               TenantConnectionGrant.brand_id == (str(brand_id) if brand_id else None))
    )
    if settings().cli_connections_enabled:
        cli_query = (select(TenantConnectionGrant.id.label('id'), CliModelConnection.provider, CliModelConnection.model)
            .join(ModelGrantActivation, ModelGrantActivation.grant_id == TenantConnectionGrant.id)
            .join(TenantConnectionReference, TenantConnectionReference.id == TenantConnectionGrant.reference_id)
            .join(CliModelConnection, CliModelConnection.id == TenantConnectionReference.source_id)
            .where(TenantConnectionGrant.workspace_id == workspace, TenantConnectionGrant.grantee_id == who.id,
                   CliModelConnection.workspace_id == workspace, CliModelConnection.owner_id == who.id,
                   TenantConnectionReference.kind == 'cli_model',
                   TenantConnectionGrant.brand_id == (str(brand_id) if brand_id else None)))
        combined = query.union_all(cli_query).subquery()
        query = select(combined.c.id, combined.c.provider, combined.c.model).order_by(combined.c.id)
    else:
        query = query.order_by(TenantConnectionGrant.id)
    rows = (await db.execute(query.offset(offset).limit(limit+1))).all()
    items = []
    for grant_id, provider, model in rows[:limit]:
        try:
            await pin(db, workspace, who.id, str(brand_id) if brand_id else None, grant_id)
        except EngineFailure:
            continue
        items.append({'grant_id': grant_id, 'provider': provider, 'model': model,
                      'capability': 'model_inference', 'tools_enabled': False})
    return {'items': items, 'has_more': len(rows)>limit, 'acceptance': 'local_authority_not_provider_health'}


async def personal_engines(db, workspace_id, actor_id):
    """Project an existing self-owned authority; never activate or discover a source."""
    if not settings().cli_connections_enabled:
        return []
    from ..cli_connections.personal import policy as personal_policy, config as personal_config
    own = await personal_policy(db, workspace_id, actor_id)
    if not own or not own.content.get('enabled'):
        return []
    try:
        value = await personal_config(db, workspace_id, actor_id)
    except EngineFailure:
        return []
    from ..cli_connections.model_catalog import public_catalog
    catalog=await public_catalog(db,workspace_id,actor_id,value['cli_pin'])
    return [{'provider':'codex_cli','models':[value['model']],'local':False,
        'capabilities':capabilities('codex_cli'),'error':None,
        'personal_cli_source_id':value['connection_id'],
        'personal_cli_source_version':value['cli_pin']['source_version'],**(catalog or {})}]


@router.get('/v1/engines')
async def catalog(workspace_id: UUID, response: Response, idempotency_key:UUID|None=Header(default=None), who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control']='no-store'
    await membership(db, str(workspace_id), who)
    if not settings().engine_contract_enabled:
        return {'available': False, 'engines': []}
    if settings().installation_ai_enabled:
        from ..installation_ai.service import catalog as installation_catalog
        engines=await installation_catalog(db,str(workspace_id),who.id)
        if engines:
            for item in engines:item['capabilities']=capabilities(item['provider'])
            engines.extend(await personal_engines(db,str(workspace_id),who.id))
            return {'available':True,'engines':engines,'scope':'installation','provider_calls':False}
    async with metadata.discovery(db,str(workspace_id),who,local_models,'model_catalogue',idempotency_key) as (models,error,_):
        engines = [{'provider': 'ollama', 'models': models, 'local': True,
                'capabilities': capabilities('ollama'), 'error': error}]
        from ..connections.enterprise_api import view as enterprise_view
        member = await membership(db, str(workspace_id), who)
        enterprise = await enterprise_view(db, str(workspace_id), member)
        rows = (await db.execute(select(ModelProviderConnection.id, ModelProviderConnection.provider, ModelProviderConnection.model).where(
        ModelProviderConnection.workspace_id == str(workspace_id), ModelProviderConnection.status == 'connected'))).all()
        for row in rows:
            if len(row.model) <= 120:
                shared = next((v for v in enterprise['connections'] if v['id'] == row.id and v['available']), None)
                registered = await db.scalar(select(TenantConnectionReference.id).where(
                TenantConnectionReference.workspace_id == str(workspace_id), TenantConnectionReference.kind == 'model',
                TenantConnectionReference.source_id == row.id))
                engines.append({'provider': row.provider, 'models': [row.model], 'local': False,
                            'capabilities': capabilities(row.provider),
                            'error': None if shared else ('enterprise_ai_source_not_enabled' if enterprise['enabled'] else
                                'engine_connection_authority_not_activated' if registered else None),
                            **({'enterprise_source_id': row.id} if shared else {})})
        if settings().cli_connections_enabled:
            engines.extend(await personal_engines(db,str(workspace_id),who.id))
            rows = (await db.execute(select(CliModelConnection.provider, CliModelConnection.model).where(
                CliModelConnection.workspace_id == str(workspace_id), CliModelConnection.owner_id == who.id,
                CliModelConnection.status == 'connected'))).all()
            for row in rows:
                engines.append({'provider':row.provider, 'models':[row.model], 'local':False,
                                'capabilities':capabilities(row.provider), 'error':'engine_connection_grant_required'})
        return {'available': True, 'engines': engines}


@router.get('/v1/sessions/{session_id}/engine')
async def get_selection(session_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    chat = await owned_session(db, session_id, who)
    config = chat.engine_config
    if config is None and settings().engine_contract_enabled:
        try:
            config = await default_config(db, chat.workspace_id, actor_id=who.id, brand_id=chat.brand_id)
        except EngineFailure as exc:
            # Keep the chooser usable for an explicit recovery selection, without
            # pretending that a failed default has silently become local.
            return {**view(chat, None), 'error': exc.code}
    return view(chat, config)


@router.put('/v1/sessions/{session_id}/engine')
async def set_selection(session_id: UUID, body: EngineChoice, response:Response, idempotency_key:UUID|None=Header(default=None), who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control']='no-store'
    from ..connections.enterprise_ai import chat_owned
    chat = await chat_owned(db, session_id, who)
    if not settings().engine_contract_enabled:
        raise HTTPException(503, 'engine_contract_disabled')
    sid,wid=chat.id,chat.workspace_id
    if body.provider=='ollama':
        if (chat.chat_profile or {}).get('enterprise_ai_read_only'):
            raise HTTPException(403, 'enterprise_ai_read_only_required')
        if body.grant_id is not None:raise HTTPException(409,'engine_connection_grant_denied')
        async with metadata.discovery(db,wid,who,local_models,'model_select',idempotency_key,
            check=lambda: selection(db,sid,wid,who,body.version)) as (models,error,chat):
            if error:raise HTTPException(409,error)
            return await save_selection(db,chat,body,who,models)
    # Cloud selection reads existing server-owned configuration only: no new I/O.
    await metadata.actor(db,wid,who)
    chat,_=await selection(db,sid,wid,who,body.version)
    return await save_selection(db,chat,body,who)


async def selection(db,sid,wid,who,version):
    chat = await db.scalar(select(ChatSession).where(ChatSession.id == sid)
                           .with_for_update().execution_options(populate_existing=True))
    if not chat or chat.user_id!=who.id or chat.archived_at is not None:raise HTTPException(404,'Không tìm thấy hội thoại')
    if chat.workspace_id!=wid:raise HTTPException(403,'engine_metadata_scope_changed')
    if version != chat.engine_version:
        raise HTTPException(409, 'engine_revision_conflict')
    if await db.scalar(select(Run.id).where(Run.session_id == chat.id, Run.status.in_(['queued', 'running']))):
        raise HTTPException(409, 'engine_run_active')
    return chat,(chat.id,chat.workspace_id,chat.user_id,chat.brand_id,chat.brain_id,
        chat.engine_version,chat.chat_revision,chat.knowledge_enabled,digest(chat.engine_config))


async def save_selection(db,chat,body,who,local_catalogue=None):
    try:
        config = await choose_config(db, chat.workspace_id, body.provider, body.model,
                                     grant_id=body.grant_id, actor_id=who.id, brand_id=chat.brand_id,local_catalogue=local_catalogue,
                                     enterprise_source_id=str(body.enterprise_source_id) if body.enterprise_source_id else None,
                                     personal_cli_source_id=body.personal_cli_source_id,
                                     **({'installation_resource_id':body.installation_resource_id,'reasoning_effort':body.reasoning_effort}
                                        if body.installation_resource_id is not None or body.reasoning_effort is not None else {}))
        if (chat.chat_profile or {}).get('enterprise_ai_read_only') and (config.get('connection_authority') or {}).get('mode') not in ('enterprise_policy','installation_resource'):
            raise EngineFailure('enterprise_ai_read_only_required')
        if settings().chat_features_enabled:
            from ..chat.policy import policy_for, enforce
            enforce(body.provider, policy_for(chat), policy_for(chat))
    except EngineFailure as exc:
        raise HTTPException(409, exc.code) from None
    if body.prepare_muse_context:
        if body.provider!='muse':raise HTTPException(422,'muse_context_selection_invalid')
        from ..cli_connections.muse_resource import MIN_CONTEXT,MIN_RUN_BUDGET
        # Explicit chooser action with visible budget disclosure. Never alter
        # privacy, tool authority or another chat's settings.
        profile=dict(chat.chat_profile or {});policy=dict(profile.get('policy') or {})
        if settings().provider_managed_tokens:policy['token_mode']='provider'
        else:
            policy['context_tokens']=max(policy.get('context_tokens',0),MIN_CONTEXT)
            policy['max_run_tokens']=max(policy.get('max_run_tokens',0),MIN_RUN_BUDGET)
        profile['policy']=policy;chat.chat_profile=profile
    chat.engine_config, chat.engine_version = config, chat.engine_version + 1
    await db.commit()
    return view(chat, config)


@router.get('/v1/runs/{run_id}/engine')
async def get_snapshot(run_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    run = await owned_run(db, run_id, who)
    return {'snapshot': public(run.engine_snapshot),
            'status': 'pinned' if run.engine_snapshot else 'legacy_unknown'}
