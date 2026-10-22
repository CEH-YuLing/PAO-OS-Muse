"""Catalog evidence, not provider probing or credential-based health inference."""
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet


def state(implemented, configured=None, *, active=False, healthy=None,
          accepted=None, reason='not_verified', checked_at=None):
    return {'implemented': bool(implemented), 'configured': configured,
            'active': bool(active and implemented and configured),
            'healthy': healthy, 'accepted': accepted, 'reason': reason,
            'checked_at': checked_at.isoformat() if checked_at else None}


def provider_state(config, row, clock=None):
    clock = clock or datetime.now(timezone.utc)
    encryption_ready = False
    try:
        Fernet(config.integration_encryption_key.encode())
        encryption_ready = True
    except (ValueError, TypeError):
        pass
    configured = bool(row and row.api_key_ciphertext and row.model and encryption_ready)
    checked = row.last_checked_at if row else None
    recent = bool(checked and checked.tzinfo and timedelta(0) <= clock - checked <= timedelta(minutes=15))
    # Existing records mix model-list and inference checks; success is not
    # sufficient evidence of current inference health. Recent explicit failure is.
    failed = bool(row and recent and row.status == 'error' and row.last_error)
    return state(True, configured, active=bool(row and row.is_default and row.status == 'connected'),
                 healthy=False if failed else None,
                 reason='recent_check_failed' if failed else
                        'health_not_verified' if configured else 'workspace_connection_required',
                 checked_at=checked)


def annotate(features, integrations, providers, compatibility, config, cloud):
    feature_config = {'self_learning': config.memory_enabled,
        'capabilities': config.tools_enabled, 'collaborators': config.agent_runtime_enabled,
        'skills': True, 'chatbot': True, 'tasks': True, 'recurring_tasks': config.temporal_enabled,
        'brain_memory': config.memory_enabled}
    for row in features:
        configured = bool(feature_config[row['key']])
        row['readiness'] = state(True, configured, active=configured)
    integration_config = {
        'telegram': (True, bool(config.telegram_bot_token), config.telegram_enabled),
        'meta_ads': (True, bool(config.meta_app_id and config.meta_app_secret and config.meta_graph_api_version), config.meta_enabled),
        'google_ads': (True, bool(config.google_ads_client_id and config.google_ads_client_secret and config.google_ads_developer_token), config.google_ads_enabled),
    }
    for row in integrations:
        implemented, configured, enabled = integration_config.get(row['key'], (False, False, False))
        row['readiness'] = state(implemented, configured, active=enabled,
            accepted=None if implemented else False,
            reason='health_not_verified' if implemented else 'adapter_not_implemented')
        if not implemented:
            row['status'] = 'available'  # A token cannot configure a missing adapter.
    for row in providers:
        if row['key'] == 'ollama':
            row['readiness'] = state(True, bool(config.ollama_url and config.ollama_model),
                                     active=row['default'], reason='health_not_verified')
        else:
            provider = 'gemini' if row['key'] == 'google_ai' else row['key']
            row['readiness'] = provider_state(config, cloud.get(provider))
    for key, row in compatibility.items():
        row['readiness'] = state(True, None, active=False,
            accepted=False if row['status'] == 'shadow' else None,
            reason='shadow_only' if row['status'] == 'shadow' else 'parity_not_accepted')
