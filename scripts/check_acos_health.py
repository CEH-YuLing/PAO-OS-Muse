"""Read-only ACOS liveness snapshot; no provider requests or business jobs."""
import asyncio,json,time,urllib.request
from pao.config import settings
from pao.modules.operations.health import snapshot
from arq import create_pool
from arq.connections import RedisSettings

def endpoint_status(url):
    # Bounded startup race tolerance: three probes, never label a failed probe healthy.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=3) as response:
                return response.status
        except Exception:
            if attempt < 2:
                time.sleep(0.5)
    return 'unavailable'

async def operations_ready(redis, config):
    # A new worker publishes its lease after startup dispatch, not at PID creation.
    for attempt in range(20):
        result = await snapshot(redis, config)
        if result['worker']['healthy'] is True or attempt == 19:
            return result
        await asyncio.sleep(1)

async def main():
    config=settings()
    if not config.database_url.endswith('/pao_acos_local'):
        raise SystemExit('ACOS-local only')
    endpoints={}
    for name,url in (('api_health','http://127.0.0.1:8100/health'),
                     ('api_ready','http://127.0.0.1:8100/ready'),
                     ('web','http://127.0.0.1:3200/')):
        endpoints[name]=endpoint_status(url)
    redis=await create_pool(RedisSettings.from_dsn(config.redis_url))
    try:
        result={'endpoints':endpoints,'operations':await operations_ready(redis,config)}
        print(json.dumps(result))
        if any(v!=200 for v in endpoints.values()) or result['operations']['worker']['healthy'] is not True:
            raise SystemExit('Local readiness failed')
    finally:await redis.aclose()
if __name__=='__main__':
    asyncio.run(main())
