"""Dedicated real ARQ Sources worker; refuse local DB or non-test Redis/queue."""
import os
from arq import cron
from arq.connections import RedisSettings
from arq.worker import create_worker
from pao.config import settings
from pao.modules.knowledge.worker import ingest_source,dispatch_sources

config=settings();queue=os.environ.get('PAO_P21_BROWSER_QUEUE','');redis=RedisSettings.from_dsn(config.redis_url)
if (os.environ.get('PAO_P21_BROWSER_TEST')!='1' or not config.database_url.endswith('/pao_test') or
    redis.database!=15 or not queue.startswith('pao-test:sources-browser:') or
    not config.knowledge_sources_enabled or not config.brain_manager_enabled):
    raise SystemExit('Dedicated P2.1 browser test runtime only')

class BrowserSourcesWorker:
    functions=[ingest_source]
    redis_settings=redis
    queue_name=queue
    max_jobs=1
    handle_signals=False
    job_timeout=30
    max_tries=1
    keep_result=0
    on_startup=dispatch_sources
    cron_jobs=[cron(dispatch_sources,name=queue+':dispatch',second=set(range(0,60,2)),run_at_startup=True)]

if __name__=='__main__':create_worker(BrowserSourcesWorker).run()
