"""Workspace-scoped cloud model credentials and provider discovery."""
from cryptography.fernet import Fernet, InvalidToken
import asyncio
import json
import httpx
from sqlalchemy import select

from .config import settings
from .gateway import OllamaGateway, cloud_gateway
from .models import ModelProviderConnection
from .credential_guard import require_clean_payload, CredentialPayloadError

PROVIDERS = {
    'openai': {'name':'OpenAI','default_model':'gpt-4.1-mini','models_url':'https://api.openai.com/v1/models'},
    'anthropic': {'name':'Anthropic','default_model':'claude-sonnet-4-5','models_url':'https://api.anthropic.com/v1/models'},
    'gemini': {'name':'Google Gemini','default_model':'gemini-2.5-flash','models_url':'https://generativelanguage.googleapis.com/v1beta/models'},
    'openrouter': {'name':'OpenRouter','default_model':'openai/gpt-4.1-mini','models_url':'https://openrouter.ai/api/v1/models'},
}

# Catalogue discovery is metadata, not inference or subscription quota.
# Fixed origins only; bounded decoded bytes, pagination and total wall time.
MODEL_DISCOVERY_TIMEOUT = 30
MODEL_DISCOVERY_BYTES = 4 * 1024 * 1024
MODEL_DISCOVERY_ROWS = 5000
MODEL_DISCOVERY_PAGES = 3


class ModelRouterError(RuntimeError):
    pass


def _cipher():
    try: return Fernet(settings().integration_encryption_key.encode())
    except (ValueError,TypeError): raise ModelRouterError('model_encryption_not_configured') from None


def encrypt_key(value:str)->str:return _cipher().encrypt(value.encode()).decode()
def decrypt_key(value:str)->str:
    try:return _cipher().decrypt(value.encode()).decode()
    except (InvalidToken,AttributeError,UnicodeError):raise ModelRouterError('model_credential_unreadable') from None


def _headers(provider,key):
    if provider=='anthropic':return {'x-api-key':key,'anthropic-version':'2023-06-01'}
    if provider=='gemini':return {'x-goog-api-key':key}
    return {'Authorization':f'Bearer {key}'}


async def fetch_models(provider:str,key:str,transport=None,*,detailed=False)->list:
    if provider not in PROVIDERS or not key:raise ModelRouterError('invalid_provider_credentials')
    meta=PROVIDERS[provider];params={}
    headers=_headers(provider,key)
    try:
        ids=set();details={};seen=set();count=0;total_bytes=0
        async with asyncio.timeout(MODEL_DISCOVERY_TIMEOUT),httpx.AsyncClient(
            timeout=20,transport=transport,trust_env=False,follow_redirects=False) as client:
            for page in range(MODEL_DISCOVERY_PAGES):
                async with client.stream('GET',meta['models_url'],headers=headers,params=params) as response:
                    if response.status_code in (401,403):raise ModelRouterError('provider_authentication_failed')
                    if response.status_code!=200:raise ModelRouterError('provider_unavailable')
                    if response.headers.get('content-type','').split(';')[0].strip().lower()!='application/json':
                        raise ModelRouterError('provider_models_invalid')
                    raw=bytearray()
                    async for part in response.aiter_bytes(chunk_size=16384):
                        total_bytes+=len(part)
                        if total_bytes>MODEL_DISCOVERY_BYTES:raise ModelRouterError('provider_models_limit')
                        raw.extend(part)
                payload=json.loads(raw)
                if not isinstance(payload,dict):raise ModelRouterError('provider_models_invalid')
                # Before extracting IDs/cursors, also inspect discarded fields.
                try:require_clean_payload(payload,key)
                except CredentialPayloadError as exc:
                    raise ModelRouterError('provider_models_sensitive' if str(exc)=='payload_credential_reflected' else 'provider_models_limit') from None
                rows=payload.get('models' if provider=='gemini' else 'data')
                if not isinstance(rows,list):raise ModelRouterError('provider_models_invalid')
                count+=len(rows)
                if count>MODEL_DISCOVERY_ROWS:raise ModelRouterError('provider_models_limit')
                for row in rows:
                    if not isinstance(row,dict):raise ModelRouterError('provider_models_invalid')
                    if provider=='gemini':
                        methods=row.get('supportedGenerationMethods',[])
                        if not isinstance(methods,list):raise ModelRouterError('provider_models_invalid')
                        if 'generateContent' not in methods:continue
                        value=row.get('name')
                        if isinstance(value,str):value=value.removeprefix('models/')
                    else:value=row.get('id')
                    if not isinstance(value,str) or not 1<=len(value)<=160 or any(ord(c)<33 or ord(c)==127 for c in value):
                        raise ModelRouterError('provider_models_invalid')
                    ids.add(value)
                    if detailed:
                        item={'model':value}
                        if provider=='openrouter' and isinstance(row.get('architecture'),dict):
                            declared=row['architecture'].get('output_modalities')
                            if declared is not None:
                                item['provider_output_modalities']=declared
                        if provider=='openai':
                            from .modules.installation_ai.openai_effort import metadata
                            item.update(metadata(value))
                        if provider in ('anthropic','gemini'):
                            from .modules.installation_ai.api_effort import metadata
                            item.update(metadata(provider,value))
                        # IDs remain dynamic. Only provider-declared effort
                        # ladders are offered; absence does not mean "High".
                        if provider=='openrouter' and isinstance(row.get('reasoning'),dict):
                            reasoning=row['reasoning']
                            item.update(reasoning_efforts=reasoning.get('supported_efforts',[]),
                                        default_effort=reasoning.get('default_effort'))
                        details[value]=item
                cursor=None
                if provider=='gemini':cursor=payload.get('nextPageToken')
                elif provider=='anthropic':
                    more=payload.get('has_more',False)
                    if type(more) is not bool:raise ModelRouterError('provider_models_invalid')
                    if more:cursor=payload.get('last_id')
                    if more and cursor is None:raise ModelRouterError('provider_models_invalid')
                if cursor is None:break
                if not isinstance(cursor,str) or not 1<=len(cursor)<=1024 or cursor in seen or any(ord(c)<33 or ord(c)==127 for c in cursor):
                    raise ModelRouterError('provider_models_invalid')
                seen.add(cursor)
                if page+1==MODEL_DISCOVERY_PAGES:raise ModelRouterError('provider_models_limit')
                # Only pass an opaque cursor to the same fixed endpoint. Never
                # follow a provider-supplied URL or change auth/version/scopes.
                params={**params,'pageToken' if provider=='gemini' else 'after_id':cursor}
        ids=sorted(ids)
        if not ids:raise ModelRouterError('provider_has_no_chat_models')
        if detailed:
            from .modules.installation_ai.catalog import normalize
            return normalize([details[name] for name in ids[:500] if len(name)<=120])
        return ids[:500]
    except ModelRouterError:raise
    except (httpx.HTTPError,ValueError,TypeError,RecursionError,TimeoutError):
        raise ModelRouterError('provider_unavailable') from None


async def fetch_model_catalog(provider,key,transport=None):
    return await fetch_models(provider,key,transport,detailed=True)


def choose_model(provider:str,models:list[str],requested:str='')->str:
    if requested:
        if requested not in models:raise ModelRouterError('model_not_available')
        return requested
    preferred=PROVIDERS[provider]['default_model']
    if preferred in models:return preferred
    return models[0]


async def gateway_for_workspace(db,workspace_id:str):
    """Deprecated unpinned execution route; no policy-row exemption or fallback."""
    from .modules.connections.resources import require_accounted
    from .modules.connections.model_fence import unregistered
    await unregistered(db, workspace_id)
    await require_accounted(db,workspace_id)
