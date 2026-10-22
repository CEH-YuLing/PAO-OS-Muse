"""Server-owned engine pins. No implicit fallback, secret-bearing public output,
remote discovery, provider installation or configuration change at this boundary.
"""
import asyncio
import hashlib
import json
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from ...config import settings
from ...gateway import OllamaGateway, cloud_gateway
from ...model_router import decrypt_key
from ...models import ChatSession, ModelProviderConnection
from .contract import EngineFailure, ManagedEngine, capabilities

VERSION = 'p3.1-v1'
CLI_VERSION = 'p84-cli-engine-v1'


def model_name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 120 or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise EngineFailure('engine_model_invalid')
    return value


def local_url(value=None):
    value = value or settings().ollama_url
    parsed = urlsplit(value)
    # Explicit loopback only: no DNS, credentials, path, proxy or redirects.
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1')
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('', '/')):
        raise EngineFailure('engine_local_endpoint_invalid')
    try:
        if not parsed.port or not 1 <= parsed.port <= 65535:
            raise ValueError()
    except ValueError:
        raise EngineFailure('engine_local_endpoint_invalid') from None
    return value.rstrip('/')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


async def local_models(transport=None):
    try:
        # Capture the loopback endpoint before the first await; slow chunks must
        # not extend a request indefinitely or follow a changed setting.
        url=local_url() + '/api/tags'
        async with asyncio.timeout(5),httpx.AsyncClient(timeout=3, transport=transport, trust_env=False, follow_redirects=False) as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()
                if response.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':raise ValueError()
                raw = bytearray()
                async for part in response.aiter_bytes(chunk_size=8192):
                    if len(raw)+len(part)>262144:raise ValueError()
                    raw.extend(part)
        payload=json.loads(raw)
        if not isinstance(payload,dict):raise ValueError()
        values=payload.get('models')
        if not isinstance(values,list) or len(values)>500:raise ValueError()
        names = set()
        for item in values:
            try:
                names.add(model_name(item.get('name')))
            except (EngineFailure, AttributeError):
                pass
        return sorted(names)
    except Exception:
        raise EngineFailure('engine_local_offline') from None


async def default_config(db, workspace_id, *, actor_id=None, brand_id=None):
    if actor_id:
        from ..installation_ai.service import default_config as installation_default
        common = await installation_default(db, workspace_id, actor_id, brand_id)
        if common is not None:
            return common
    if actor_id:
        from ..cli_connections.personal import default_config as personal_default
        personal = await personal_default(db, workspace_id, actor_id, brand_id)
        if personal is not None:
            return personal
    from ..connections import enterprise_ai
    enterprise = await enterprise_ai.policy(db, workspace_id)
    if actor_id and enterprise_ai.enabled(enterprise):
        selected = await enterprise_ai.pin(db, workspace_id, actor_id, brand_id)
        source = await enterprise_ai.source(db, workspace_id, selected['source_id'])
        return {'provider': source['provider'], 'model': source['model'],
                'connection_id': source['source_id'], 'connection_authority': selected}
    row = (await db.execute(select(ModelProviderConnection.id, ModelProviderConnection.provider,
        ModelProviderConnection.model, ModelProviderConnection.status).where(
        ModelProviderConnection.workspace_id == workspace_id,
        ModelProviderConnection.is_default.is_(True)))).first()
    if row:
        from ..connections.model_fence import unregistered
        await unregistered(db, workspace_id, row.id)
        if row.status != 'connected':
            raise EngineFailure('engine_connection_unavailable')
        return {'provider': row.provider, 'model': model_name(row.model), 'connection_id': row.id}
    from ..connections.model_fence import unregistered
    await unregistered(db, workspace_id)
    return {'provider': 'ollama', 'model': model_name(settings().ollama_model)}


async def choose_config(db, workspace_id, provider, model, *, grant_id=None, actor_id=None, brand_id=None, local_catalogue=None, enterprise_source_id=None, personal_cli_source_id=None, installation_resource_id=None, reasoning_effort=None):
    model = model_name(model)
    capabilities(provider)
    from ..installation_ai.modalities import require_chat
    try:require_chat(provider,model)
    except ValueError as exc:raise EngineFailure(str(exc)) from None
    if installation_resource_id is not None:
        if actor_id is None or any(v is not None for v in (grant_id,enterprise_source_id,personal_cli_source_id)):
            raise EngineFailure('installation_ai_selection_invalid')
        from ..installation_ai.service import config
        value=await config(db,workspace_id,actor_id,brand_id,installation_resource_id,model,reasoning_effort)
        if value['provider']!=provider:raise EngineFailure('installation_ai_selection_invalid')
        return value
    if reasoning_effort is not None:
        raise EngineFailure('ai_effort_not_supported')
    if personal_cli_source_id is not None:
        if provider != 'codex_cli' or actor_id is None or grant_id is not None or enterprise_source_id is not None:
            raise EngineFailure('personal_cli_selection_invalid')
        from ..cli_connections.personal import config
        value = await config(db, workspace_id, actor_id, brand_id, personal_cli_source_id,model=model)
        return value
    from ..connections import enterprise_ai
    enterprise = await enterprise_ai.policy(db, workspace_id)
    if enterprise_source_id is not None or (grant_id is None and provider != 'ollama' and enterprise_ai.enabled(enterprise)):
        if actor_id is None or grant_id is not None or provider in ('ollama', 'knowledge'):
            raise EngineFailure('enterprise_ai_selection_invalid')
        matches = [v for v in (enterprise.content['sources'] if enterprise else [])
                   if v['provider'] == provider and v['model'] == model
                   and (enterprise_source_id is None or v['source_id'] == enterprise_source_id)]
        if len(matches) != 1:
            raise EngineFailure('enterprise_ai_source_unavailable')
        authority = await enterprise_ai.pin(db, workspace_id, actor_id, brand_id, matches[0]['source_id'])
        return {'provider': provider, 'model': model, 'connection_id': authority['source_id'],
                'connection_authority': authority}
    if grant_id is not None:
        from ..connections.model_authority import pin
        if provider == 'ollama' or actor_id is None:
            raise EngineFailure('engine_connection_grant_denied')
        authority = await pin(db, workspace_id, actor_id, brand_id, grant_id)
        if (provider == 'codex_cli') != (authority.get('source_kind') == 'cli_model'):
            raise EngineFailure('engine_connection_grant_denied')
        if provider == 'codex_cli':
            from ..cli_connections.service import source, pin as cli_pin
            row = await source(db, workspace_id, actor_id, authority['source_id'], model)
            return {'provider': provider, 'model': model, 'connection_id': row.id,
                    'connection_authority': authority, 'cli_pin': cli_pin(row)}
        row = (await db.execute(select(ModelProviderConnection.provider, ModelProviderConnection.model).where(
            ModelProviderConnection.id == authority['source_id'], ModelProviderConnection.workspace_id == workspace_id))).first()
        if not row or row.provider != provider or row.model != model:
            raise EngineFailure('engine_connection_unavailable')
        return {'provider': provider, 'model': model, 'connection_id': authority['source_id'],
                'connection_authority': authority}
    if provider == 'ollama':
        # Only the admitted native selection boundary supplies this internal
        # catalogue. Never start an unaccounted second /api/tags request here.
        if local_catalogue is None:raise EngineFailure('engine_local_discovery_required')
        if model not in local_catalogue:
            raise EngineFailure('engine_model_not_installed')
        return {'provider': provider, 'model': model}
    if provider == 'codex_cli':
        raise EngineFailure('engine_connection_grant_denied')
    row = (await db.execute(select(ModelProviderConnection.id, ModelProviderConnection.model).where(
        ModelProviderConnection.workspace_id == workspace_id,
        ModelProviderConnection.provider == provider, ModelProviderConnection.status == 'connected'))).first()
    # P3.1 offers the already configured cloud model, not remote model discovery.
    if not row or row.model != model:
        raise EngineFailure('engine_connection_unavailable')
    from ..connections.model_fence import unregistered
    await unregistered(db, workspace_id, row.id)
    return {'provider': provider, 'model': model, 'connection_id': row.id}


async def pin_run(db, run, chat):
    if run.engine_snapshot is not None:
        return
    if not settings().engine_contract_enabled:
        if settings().chat_features_enabled:
            raise EngineFailure('engine_contract_disabled')
        if chat.engine_config:
            raise EngineFailure('engine_contract_disabled')
        if not (run.brain_context or {}).get('knowledge'):
            from ..connections.model_fence import unregistered
            await unregistered(db, run.workspace_id)
        return
    if (run.brain_context or {}).get('knowledge'):
        value = {'provider': 'knowledge', 'model': 'pao-grounded-excerpts-v1'}
    else:
        if chat.engine_config is None:
            chat.engine_config = await default_config(db, chat.workspace_id, actor_id=chat.user_id, brand_id=chat.brand_id)
            chat.engine_version += 1
        value = dict(chat.engine_config)
        preference=((run.studio_snapshot or {}).get('agent') or {}).get('payload',{}).get('model_preference')
        if preference and preference.get('installation_resource_id'):
            # The published specialist can override the chat orchestrator for
            # this run only. Never mutate the conversation or old run pins.
            value=await choose_config(db,run.workspace_id,preference['provider'],preference['model'],
                actor_id=chat.user_id,brand_id=chat.brand_id,
                installation_resource_id=preference['installation_resource_id'],
                reasoning_effort=preference.get('reasoning_effort'))
    provider = value['provider']
    snapshot = {**value, 'version': CLI_VERSION if provider == 'codex_cli' else VERSION, 'session_version': chat.engine_version,
                'capabilities': capabilities(provider)}
    if (chat.chat_profile or {}).get('enterprise_ai_read_only'):
        authority = value.get('connection_authority') or {}
        if authority.get('mode') not in ('enterprise_policy','installation_resource') or chat.memory_enabled or chat.knowledge_enabled or run.studio_snapshot:
            raise EngineFailure('enterprise_ai_read_only_required')
        snapshot['interaction_mode'] = 'read_only_ai'
    if settings().chat_features_enabled:
        from ..chat.policy import policy_for, enforce
        snapshot['chat_policy'] = policy_for(chat)
        price = snapshot['chat_policy'].get('pricing')
        if price and (price.get('provider')!=provider or price.get('model')!=value['model']):
            snapshot['chat_policy'] = {**snapshot['chat_policy'],'pricing':None}
        enforce(provider, snapshot['chat_policy'], snapshot['chat_policy'])
        snapshot['memory_engine'] = {'model': model_name(settings().ollama_model), 'url': local_url()}
        if (value.get('connection_authority') or {}).get('mode') == 'installation_resource' and provider in ('openai','openrouter','anthropic','gemini'):
            # Same already-authorized source and exact parent pin; no independent
            # workspace default, provider fallback or new credential lookup.
            # Historical snapshots retain their original local extraction path.
            snapshot['memory_engine'] = {'mode': 'run_engine'}
        snapshot['embedding_engine'] = {'model': model_name(settings().embedding_model), 'url': local_url()}
    if provider == 'ollama':
        snapshot['local_url'] = local_url()
    elif provider=='muse':
        if (value.get('connection_authority') or {}).get('mode')!='installation_resource':raise EngineFailure('installation_ai_selection_invalid')
        from ..installation_ai.service import check
        await check(db,run,chat,snapshot)
        from ..cli_connections.muse_resource import MIN_CONTEXT,MIN_RUN_BUDGET,MIN_JOB_BUDGET
        minimum=MIN_JOB_BUDGET if run.studio_snapshot else MIN_RUN_BUDGET
        from ..chat.token_policy import automatic
        if not automatic(snapshot.get('chat_policy',{})) and (snapshot.get('chat_policy',{}).get('context_tokens',0)<MIN_CONTEXT or snapshot['chat_policy'].get('max_run_tokens',0)<minimum):
            raise EngineFailure('muse_context_budget_too_small')
        if not automatic(snapshot.get('chat_policy',{})) and run.studio_snapshot and run.studio_snapshot['skill']['payload']['token_budget']<MIN_JOB_BUDGET:
            raise EngineFailure('muse_job_budget_too_small')
    elif provider == 'codex_cli':
        if (value.get('connection_authority') or {}).get('mode') == 'personal_cli':
            from ..cli_connections.personal import check
        else:
            from ..connections.model_authority import check
        from ..cli_connections.service import check_source
        await check(db, run, chat, snapshot)
        await check_source(db, run.workspace_id, snapshot)
    elif provider != 'knowledge':
        from ..connections.model_fence import pin_legacy
        if value.get('connection_authority') is not None:
            if value['connection_authority'].get('mode') == 'installation_resource':
                from ..installation_ai.service import check
            elif value['connection_authority'].get('mode') == 'enterprise_policy':
                from ..connections.enterprise_ai import check
            else:
                from ..connections.model_authority import check
            # Recheck exact selection, never repin to a newer/different grant.
            await check(db, run, chat, snapshot)
        else:
            snapshot['connection_authority'] = await pin_legacy(db, run, chat, value.get('connection_id'))
        row = await db.get(ModelProviderConnection, value.get('connection_id'))
        common=(snapshot.get('connection_authority') or {}).get('mode')=='installation_resource'
        if not row or (not common and row.workspace_id != run.workspace_id) or row.provider != provider or row.status != 'connected':
            raise EngineFailure('engine_connection_unavailable')
        snapshot['credential_binding'] = hashlib.sha256(row.api_key_ciphertext.encode()).hexdigest()
    if run.studio_snapshot:
        if not settings().chat_features_enabled:
            raise EngineFailure('studio_requires_chat')
        skill = run.studio_snapshot['skill']['payload']
        preference = run.studio_snapshot['agent']['payload'].get('model_preference')
        if preference and (preference['provider'] != provider or preference['model'] != value['model']):
            raise EngineFailure('studio_model_preference_mismatch')
        if preference and preference.get('reasoning_effort') is not None and preference['reasoning_effort']!=value.get('reasoning_effort'):
            raise EngineFailure('studio_model_preference_mismatch')
        policy = dict(snapshot['chat_policy'])
        policy.update(max_calls=1, max_run_tokens=min(policy['max_run_tokens'],skill['token_budget']),
            max_output_tokens=min(policy['max_output_tokens'],skill['output_tokens']),require_reported_usage=True)
        snapshot['chat_policy'] = policy
    snapshot['sha256'] = digest(snapshot)
    run.engine_snapshot = snapshot


def checked_snapshot(value):
    if not isinstance(value, dict) or value.get('version') != (CLI_VERSION if value.get('provider') == 'codex_cli' else VERSION):
        raise EngineFailure('engine_snapshot_incompatible')
    payload = {k: v for k, v in value.items() if k != 'sha256'}
    if value.get('sha256') != digest(payload) or value.get('capabilities') != capabilities(value.get('provider')):
        raise EngineFailure('engine_snapshot_incompatible')
    model_name(value.get('model'))
    return value


def public(value):
    if not value:
        return None
    # Explicit allowlist: never leak connection binding, local endpoint or secrets.
    return {k: value[k] for k in ('version', 'provider', 'model', 'reasoning_effort', 'session_version', 'capabilities') if k in value}


async def gateway_for_run(db, run):
    from ..business_planning.jobs import guard_run
    await guard_run(db, run)
    if not settings().engine_contract_enabled:
        raise EngineFailure('engine_contract_disabled')
    value = checked_snapshot(run.engine_snapshot)
    provider, model = value['provider'], value['model']
    if settings().chat_features_enabled:
        from ..connections.resources import require_run_accounting
        require_run_accounting(value)
        from ..chat.policy import policy_for, run_policy, enforce
        chat = await db.get(ChatSession, run.session_id)
        enforce(provider, run_policy(run), policy_for(chat))
    if provider == 'knowledge':
        raise EngineFailure('engine_capability_denied')
    if provider == 'ollama':
        from ..connections.resources import require_accounted,require_run_accounting
        if not settings().chat_features_enabled:await require_accounted(db,run.workspace_id)
        require_run_accounting(value)
        gateway = OllamaGateway(model=model, url=local_url(value.get('local_url')))
    elif provider=='muse':
        from ..connections.model_fence import check_run
        from ..cli_connections.muse_execution import MuseGateway
        await check_run(db,run)
        require_run_accounting(value)
        gateway=MuseGateway(run.id,value)
    elif provider == 'codex_cli':
        from ..connections.model_fence import check_run
        from ..cli_connections.gateway import CliGateway
        await check_run(db, run)
        require_run_accounting(value)
        gateway = CliGateway(run.id, value)
    else:
        from ..connections.model_fence import check_run, ModelFenceGateway
        await check_run(db, run)
        row = await db.get(ModelProviderConnection, value.get('connection_id'))
        common=(value.get('connection_authority') or {}).get('mode')=='installation_resource'
        if not row or (not common and row.workspace_id != run.workspace_id) or row.provider != provider or row.status != 'connected':
            raise EngineFailure('engine_connection_unavailable')
        if hashlib.sha256(row.api_key_ciphertext.encode()).hexdigest() != value.get('credential_binding'):
            raise EngineFailure('engine_connection_changed')
        from ..connections.resources import require_accounted,require_run_accounting
        if not settings().chat_features_enabled:await require_accounted(db,run.workspace_id)
        require_run_accounting(value)
        try:
            args={'reasoning_effort':value['reasoning_effort']} if value.get('reasoning_effort') is not None else {}
            gateway = ModelFenceGateway(cloud_gateway(provider, decrypt_key(row.api_key_ciphertext), model, **args),
                                        run.workspace_id, run=run)
        except Exception:
            raise EngineFailure('engine_credential_unavailable') from None
    return ManagedEngine(gateway, value['capabilities'])
