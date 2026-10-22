"""Isolated parse/index/RAG worker: refuses non-knowledge runs and real DB."""
import os
from arq import cron
from arq.connections import RedisSettings
from arq.worker import create_worker
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Run
from pao.modules.knowledge.worker import ingest_source,dispatch_sources
from pao.modules.knowledge.index import index_source,dispatch_indexes
from pao.runtime import execute_run as actual_execute
config=settings();queue=os.environ.get('PAO_P21_BROWSER_QUEUE','');redis=RedisSettings.from_dsn(config.redis_url)
assert os.environ.get('PAO_P2_BROWSER_TEST')=='1' and config.database_url.endswith('/pao_test') and redis.database==15 and queue.startswith('pao-test:sources-browser:') and config.knowledge_enabled and not config.knowledge_embeddings_enabled
async def execute_run(ctx,rid):
    async with Session() as db:
        row=await db.get(Run,rid)
        if not row or not (row.brain_context or {}).get('knowledge'):raise RuntimeError('Knowledge test run only')
    await actual_execute(ctx,rid)
async def dispatch(ctx):
    await dispatch_sources(ctx);await dispatch_indexes(ctx)
    async with Session() as db:
        for row in await db.scalars(select(Run).where(Run.status=='queued')):
            if (row.brain_context or {}).get('knowledge'):await ctx['redis'].enqueue_job('execute_run',row.id,_job_id='p2-browser-run:'+row.id,_queue_name=queue)
class BrowserKnowledgeWorker:
    functions=[ingest_source,index_source,execute_run]
    redis_settings=redis
    queue_name=queue
    max_jobs=1
    handle_signals=False
    job_timeout=30
    max_tries=1
    keep_result=0
    on_startup=dispatch
    cron_jobs=[cron(dispatch,name=queue+':dispatch',second=set(range(0,60,2)),run_at_startup=True)]
if __name__=='__main__':create_worker(BrowserKnowledgeWorker).run()
