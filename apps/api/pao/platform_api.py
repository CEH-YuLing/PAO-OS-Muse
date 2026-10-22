"""Read-only PAO platform registry for Javis-compatible capabilities.

The registry is intentionally explicit: it reports what is implemented,
available, or still gated without returning credentials or pretending that an
adapter is connected before its runtime exists.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, principal
from .access import membership
from .config import settings
from .db import database
from .javis_compat import capability_manifest
from .models import ModelProviderConnection
from .modules.platform.readiness import annotate
from .modules.operations.health import snapshot as operations_snapshot

router = APIRouter(prefix='/v1/platform', tags=['platform'])


@router.get('/catalog')
async def catalog(request: Request, workspace_id: UUID | None = None, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    config = settings()
    cloud = {}
    if workspace_id:
        await membership(db, str(workspace_id), who)
        cloud = {row.provider: row for row in await db.scalars(select(ModelProviderConnection).where(
            ModelProviderConnection.workspace_id == str(workspace_id)))}
    has_default = any(row.is_default for row in cloud.values())
    features = [
        {'key': 'self_learning', 'name': 'Tự học', 'status': 'partial',
         'target': 'Memory extraction, learning jobs và approval'},
        {'key': 'capabilities', 'name': 'Năng lực', 'status': 'ready',
         'target': 'Capability registry và tool gateway'},
        {'key': 'collaborators', 'name': 'Cộng sự', 'status': 'ready',
         'target': 'Chief of Staff, Researcher, Editor, Marketing, Performance Analyst'},
        {'key': 'skills', 'name': 'Kỹ năng', 'status': 'partial',
         'target': 'Agent registry; skill package importer đang được kiểm soát'},
        {'key': 'chatbot', 'name': 'Chatbot', 'status': 'partial',
         'target': 'Web chat và Telegram đã có; Zalo/Botcake là adapter kế tiếp'},
        {'key': 'tasks', 'name': 'Công việc', 'status': 'ready',
         'target': 'Projects, tasks, comments, activity và agent assignment'},
        {'key': 'recurring_tasks', 'name': 'Công việc định kỳ', 'status': 'partial',
         'target': 'Temporal durable workflows; recurrence scheduler đang được mở rộng'},
        {'key': 'brain_memory', 'name': 'Brain & Memory', 'status': 'ready',
         'target': 'PostgreSQL/pgvector memory theo workspace, user và brand'},
    ]
    integrations = [
        {'key': 'telegram', 'name': 'Telegram', 'category': 'channel',
         'status': 'configured' if config.telegram_enabled and config.telegram_bot_token else 'available'},
        {'key': 'zalo', 'name': 'Zalo OA', 'category': 'channel',
         'status': 'configured' if config.zalo_oa_access_token else 'available'},
        {'key': 'botcake', 'name': 'Botcake', 'category': 'channel',
         'status': 'configured' if config.botcake_api_token else 'available'},
        {'key': 'meta_ads', 'name': 'Meta Ads', 'category': 'ads',
         'status': 'configured' if config.meta_enabled else 'available'},
        {'key': 'google_ads', 'name': 'Google Ads', 'category': 'ads',
         'status': 'configured' if config.google_ads_enabled else 'available'},
        {'key': 'tiktok_ads', 'name': 'TikTok Ads', 'category': 'ads',
         'status': 'configured' if config.tiktok_ads_access_token else 'available'},
    ]
    providers = [
        {'key': 'ollama', 'name': 'Ollama Local', 'configured': True, 'default': not has_default,
         'model': config.ollama_model},
        {'key': 'openai', 'name': 'OpenAI', 'configured': 'openai' in cloud or bool(config.openai_api_key), 'default': bool(cloud.get('openai') and cloud['openai'].is_default), 'model': cloud.get('openai').model if cloud.get('openai') else None},
        {'key': 'anthropic', 'name': 'Anthropic Claude', 'configured': 'anthropic' in cloud or bool(config.anthropic_api_key), 'default': bool(cloud.get('anthropic') and cloud['anthropic'].is_default), 'model': cloud.get('anthropic').model if cloud.get('anthropic') else None},
        {'key': 'google_ai', 'name': 'Google Gemini', 'configured': 'gemini' in cloud or bool(config.google_ai_api_key), 'default': bool(cloud.get('gemini') and cloud['gemini'].is_default), 'model': cloud.get('gemini').model if cloud.get('gemini') else None},
        {'key': 'openrouter', 'name': 'OpenRouter', 'configured': 'openrouter' in cloud or bool(config.openrouter_api_key), 'default': bool(cloud.get('openrouter') and cloud['openrouter'].is_default), 'model': cloud.get('openrouter').model if cloud.get('openrouter') else None},
    ]
    compatibility = capability_manifest()
    annotate(features, integrations, providers, compatibility, config, cloud)
    return {'features': features, 'integrations': integrations, 'model_providers': providers,
            'javis_compatibility': compatibility,
            'status_semantics': 'legacy labels describe implementation/configuration; readiness is evidence-based',
            'readiness_version': 'p0-evidence-v1',
            'operations': await operations_snapshot(request.app.state.redis, config)}
