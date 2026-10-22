"""Read-only liveness evidence; no provider probes or business jobs."""
WORKER_KEY = 'pao:worker:health'
BRIDGE_KEY = 'pao:telegram-bridge:health'


async def lease(redis, key, enabled=True):
    if not enabled:
        return {'status': 'disabled', 'healthy': None, 'scope': 'liveness_only'}
    try:
        ttl = await redis.pttl(key)
        return {'status': 'healthy' if ttl > 0 else 'missing_or_stale',
                'healthy': ttl > 0, 'scope': 'liveness_only'}
    except Exception:
        return {'status': 'unavailable', 'healthy': None, 'scope': 'liveness_only'}


async def snapshot(redis, config):
    return {'worker': await lease(redis, WORKER_KEY),
            'telegram_bridge': await lease(redis, BRIDGE_KEY, config.telegram_enabled),
            'telegram_scoped_worker': await lease(redis,'pao:telegram:scoped:health',
                config.telegram_scoped_runtime_enabled and not config.telegram_enabled and config.channels_enabled),
            'production_reboot_accepted': False}
