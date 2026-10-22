"""Reviewed local feature switches, not a permission or provider bypass."""
import hashlib
import re

ENABLE = (
    'result_inbox_enabled', 'learning_review_enabled', 'outcome_observations_enabled',
    'business_events_enabled', 'business_event_delivery_enabled',
    'unified_approvals_enabled', 'goal_admission_enabled', 'studio_schedule_manager_enabled',
)
# Delivery above is internal.audit.v1 only, NOT a channel/provider delivery.
KEEP_OFF = (
    'meta_enabled', 'google_ads_enabled', 'meta_installation_config_enabled',
    'meta_write_enabled', 'ads_autopilot_global_enabled', 'meta_autopilot_enabled',
    'telegram_enabled', 'telegram_scoped_runtime_enabled', 'channels_enabled',
    'channel_autoreply_enabled', 'channel_retention_enabled',
    'temporal_enabled', 'workflow_durable_enabled', 'workflow_dispatch_enabled',
    'workflow_worker_enabled', 'goal_iterations_enabled', 'goal_runner_enabled',
    'studio_schedule_dispatch_enabled', 'voice_enabled', 'voice_turns_enabled',
)


def non_feature_hash(raw):
    """Compare every unrelated line, including secrets, without returning it."""
    allowed = {key.upper() for key in ENABLE}
    lines = []
    seen = set()
    for line in raw.decode('utf-8-sig').replace('\r\n', '\n').splitlines(keepends=True):
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        if match and match[1].upper() in allowed:
            if match[1].upper() in seen:
                raise ValueError('duplicate_local_feature_flag')
            seen.add(match[1].upper())
        else:
            lines.append(line)
    return hashlib.sha256(''.join(lines).encode()).hexdigest()


def flags(config):
    return {key: getattr(config, key) for key in (*ENABLE, *KEEP_OFF)}


def source_manifest(snapshot):
    """Exclude only .env (checked separately) and declared Next build outputs.

    next.config.mjs declares these exact directories. Source files, lockfiles,
    Next config, tests and runtime pins must still compare exactly.
    """
    generated = ('apps/web/.pao-next/', 'apps/web/.pao-build-check/')
    return {key: value for key, value in snapshot.items()
            if key != '.env' and not key.startswith(generated)}


def verify_local(config):
    from sqlalchemy.engine import make_url
    pg, redis = make_url(config.database_url), make_url(config.redis_url)
    if (pg.host, pg.port, pg.database) != ('127.0.0.1', 15432, 'pao_acos_local'):
        raise ValueError('local_primary_database_required')
    if redis.host != '127.0.0.1' or redis.port != 16379:
        raise ValueError('local_redis_required')
    if any(getattr(config, key) for key in KEEP_OFF):
        raise ValueError('external_or_dispatch_switch_changed')

