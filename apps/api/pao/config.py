from functools import lru_cache
from typing import Literal
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(os.environ.get('PAO_ROOT', Path(__file__).resolve().parents[3]))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str = 'postgresql+asyncpg://pao:pao@127.0.0.1:5432/pao'
    redis_url: str = 'redis://127.0.0.1:6379/0'
    jwt_secret: str = Field(min_length=32)
    jwt_minutes: int = Field(default=60, ge=5, le=1440)
    ollama_url: str = 'http://127.0.0.1:11434'
    ollama_model: str = 'qwen3:4b-instruct-2507-q4_K_M'
    run_timeout_seconds: int = Field(default=180, ge=10, le=600)
    installation_ai_enabled: bool = False
    installation_ai_manager_ids: list[str] = Field(default_factory=list)
    meta_enabled: bool = False
    # Private installer compatibility only. Never enable on a shared SaaS host.
    meta_installation_config_enabled: bool = False
    result_inbox_enabled: bool = False
    learning_review_enabled: bool = False
    outcome_observations_enabled: bool = False
    meta_write_enabled: bool = False
    meta_write_max_budget_change_pct: int = Field(default=20, ge=1, le=50)
    ads_approval_ttl_hours: int = Field(default=24, ge=1, le=168)
    ads_autopilot_global_enabled: bool = False
    meta_autopilot_enabled: bool = False
    meta_app_id: str = ''
    meta_app_secret: str = Field(default='', repr=False)
    meta_graph_api_version: str = ''
    meta_redirect_uri: str = 'http://localhost:3100/v1/integrations/meta/callback'
    google_ads_enabled: bool = False
    google_ads_client_id: str = ''
    google_ads_client_secret: str = Field(default='', repr=False)
    google_ads_api_version: str = 'v25'
    google_ads_redirect_uri: str = 'http://localhost:3100/v1/integrations/google-ads/callback'
    google_ads_login_customer_id: str = ''
    google_ads_developer_token: str = Field(default='', repr=False)
    temporal_enabled: bool = False
    temporal_address: str = '127.0.0.1:7233'
    temporal_namespace: str = 'default'
    temporal_task_queue: str = 'pao-automation'
    temporal_workflow_timeout_days: int = Field(default=30, ge=1, le=365)
    voice_enabled: bool = False
    voice_stt_model_path: str = '.runtime/models/faster-whisper-small'
    voice_stt_device: Literal['cpu','cuda'] = 'cpu'
    voice_stt_compute_type: str = 'int8'
    voice_tts_provider: Literal['windows_sapi','piper'] = 'windows_sapi'
    voice_tts_executable: str = ''
    voice_tts_model_path: str = ''
    voice_max_audio_bytes: int = Field(default=10_485_760, ge=1024, le=52_428_800)
    voice_max_seconds: int = Field(default=30, ge=2, le=120)
    integration_encryption_key: str = Field(default='', repr=False)
    memory_enabled: bool = True
    brain_manager_enabled: bool = False
    knowledge_sources_enabled: bool = False
    knowledge_enabled: bool = False
    engine_contract_enabled: bool = False
    cli_connections_enabled: bool = False
    cli_browser_login_enabled: bool = False  # Operator opt-in for personal local login only.
    cli_device_id: str = ''  # Operator-owned identity; not supplied by customers.
    chat_features_enabled: bool = False
    provider_managed_tokens: bool = True
    studio_enabled: bool = False
    business_planning_enabled: bool = False
    workflow_planning_enabled: bool = False
    workflow_durable_enabled: bool = False
    workflow_dispatch_enabled: bool = False
    workflow_worker_enabled: bool = False
    goal_admission_enabled: bool = False
    goal_iterations_enabled: bool = False
    goal_runner_enabled: bool = False
    studio_schedule_manager_enabled: bool = False
    studio_schedule_dispatch_enabled: bool = False
    workflow_temporal_task_queue: str = 'pao-studio-dryrun'
    connectors_enabled: bool = False
    business_events_enabled: bool = False
    business_event_delivery_enabled: bool = False
    unified_approvals_enabled: bool = False
    knowledge_embeddings_enabled: bool = True
    agent_runtime_enabled: bool = True
    # Javis compatibility is initially observational. It records routing
    # decisions without changing the established PAO execution path.
    javis_compat_shadow_enabled: bool = True
    telegram_enabled: bool = False
    # S3.2 kernel only; no daemon, credential store or public activation yet.
    telegram_scoped_runtime_enabled: bool = False
    telegram_public_base_url: str = ''
    channels_enabled: bool = False
    channel_identity_key: str = Field(default='',repr=False)
    channel_autoreply_enabled: bool = False
    channel_retention_enabled: bool = False
    voice_turns_enabled: bool = False
    telegram_bot_token: str = Field(default='', repr=False)
    telegram_webhook_secret: str = Field(default='', repr=False)
    telegram_mode: Literal['polling','webhook'] = 'polling'
    tools_enabled: bool = True
    searxng_url: str = 'http://127.0.0.1:8888'
    agent_run_timeout_seconds: int = Field(default=600, ge=180, le=900)
    embedding_model: str = 'embeddinggemma:300m'
    memory_timeout_seconds: int = Field(default=180, ge=10, le=600)
    memory_top_k: int = Field(default=5, ge=1, le=10)
    memory_min_similarity: float = Field(default=0.3, ge=0, le=1)
    context_tokens: int = Field(default=4096, ge=1024, le=8192)
    output_tokens: int = Field(default=512, ge=32, le=2048)
    # Optional Javis-compatible channel and cloud-provider adapters. Secrets
    # stay server-side and the platform catalog exposes configured booleans only.
    openai_api_key: str = Field(default='', repr=False)
    anthropic_api_key: str = Field(default='', repr=False)
    google_ai_api_key: str = Field(default='', repr=False)
    openrouter_api_key: str = Field(default='', repr=False)
    zalo_oa_access_token: str = Field(default='', repr=False)
    botcake_api_token: str = Field(default='', repr=False)
    tiktok_ads_access_token: str = Field(default='', repr=False)


@lru_cache
def settings() -> Settings:
    return Settings()
