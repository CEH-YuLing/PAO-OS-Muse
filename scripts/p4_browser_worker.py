"""Isolated P4 fixture worker: one synthetic generation, no real providers."""
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
config=settings();queue=os.environ['PAO_P21_BROWSER_QUEUE'];redis=RedisSettings.from_dsn(config.redis_url)
assert os.environ.get('PAO_P4_BROWSER_TEST')=='1' and config.database_url.endswith('/pao_test') and redis.database==15
assert queue.startswith('pao-test:sources-browser:') and config.studio_enabled and config.chat_features_enabled
assert not any((config.memory_enabled,config.tools_enabled,config.meta_enabled,config.google_ads_enabled,config.telegram_enabled))
class Fixture:
    provider_name='ollama';model_name=config.ollama_model
    async def stream(self,messages,max_tokens=None):
        assert max_tokens==256 and any('P4 synthetic' in row['content'] for row in messages)
        yield Chunk(text='{"text":"P4 synthetic"}');await asyncio.sleep(.2)
        yield Chunk(usage={'prompt_eval_count':300,'eval_count':10})
async def execute_run(ctx,rid):
    async with Session() as db:
        row=await db.get(Run,rid)
        assert row and row.prompt=='/p4-echo {"text":"P4 synthetic"}' and row.studio_snapshot and row.engine_snapshot['provider']=='ollama'
    await actual_execute({**ctx,'gateway':Fixture()},rid)
async def dispatch(ctx):
    async with Session() as db:
        for row in await db.scalars(select(Run).where(Run.status=='queued')):
            if row.prompt=='/p4-echo {"text":"P4 synthetic"}':
                await ctx['redis'].enqueue_job('execute_run',row.id,_job_id='p4-browser:'+row.id,_queue_name=queue)
class Worker:
    functions=[execute_run];redis_settings=redis;queue_name=queue;max_jobs=1;handle_signals=False;job_timeout=30;max_tries=1;keep_result=0
    on_startup=dispatch;cron_jobs=[cron(dispatch,name=queue+':dispatch',second=set(range(0,60,2)),run_at_startup=True)]
if __name__=='__main__':create_worker(Worker).run()
