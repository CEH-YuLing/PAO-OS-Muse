"""Own pao_test/Redis15 queue; synthetic gateway only, NEVER real inference."""
import asyncio,os
from arq import cron
from arq.connections import RedisSettings
from arq.worker import create_worker
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Run
from pao.gateway import Chunk
from pao.runtime import execute_run as actual_execute
config=settings();queue=os.environ.get('PAO_P21_BROWSER_QUEUE','');redis=RedisSettings.from_dsn(config.redis_url)
assert os.environ.get('PAO_P31_BROWSER_TEST')=='1' and config.database_url.endswith('/pao_test') and redis.database==15 and queue.startswith('pao-test:sources-browser:') and config.engine_contract_enabled
assert not any((config.memory_enabled,config.tools_enabled,config.agent_runtime_enabled,config.meta_enabled,config.google_ads_enabled,config.telegram_enabled))
class Fixture:
    async def stream(self,messages,max_tokens=None):
        assert messages[-1]['content'].startswith('P31 fixture:')
        yield Chunk(text='P3.1 fixture response')
        await asyncio.sleep(3)
        yield Chunk(text=' · synthetic, no provider call')
async def execute_run(ctx,rid):
    async with Session() as db:
        row=await db.get(Run,rid)
        if not row or not row.prompt.startswith('P31 fixture:') or not row.engine_snapshot or row.engine_snapshot['provider']!='ollama':raise RuntimeError('Synthetic local-pinned run only')
    await actual_execute({**ctx,'gateway':Fixture()},rid)
async def dispatch(ctx):
    async with Session() as db:
        for row in await db.scalars(select(Run).where(Run.status=='queued')):
            if row.prompt.startswith('P31 fixture:'):await ctx['redis'].enqueue_job('execute_run',row.id,_job_id='p31-browser-run:'+row.id,_queue_name=queue)
class BrowserEngineWorker:
    functions=[execute_run]
    redis_settings=redis
    queue_name=queue
    max_jobs=1
    handle_signals=False
    job_timeout=30
    max_tries=1
    keep_result=0
    on_startup=dispatch
    cron_jobs=[cron(dispatch,name=queue+':dispatch',second=set(range(0,60,2)),run_at_startup=True)]
if __name__=='__main__':create_worker(BrowserEngineWorker).run()
