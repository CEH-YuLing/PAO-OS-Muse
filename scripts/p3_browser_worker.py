"""Isolated synthetic P3 worker; never real model/cloud/customer data."""
import asyncio,os
from arq import cron
from arq.connections import RedisSettings
from arq.worker import create_worker
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Run
from pao.gateway import Chunk
from pao.agents import ExecutionPlan
from pao.runtime import execute_run as actual_execute
config=settings();queue=os.environ['PAO_P21_BROWSER_QUEUE'];redis=RedisSettings.from_dsn(config.redis_url)
assert os.environ.get('PAO_P3_BROWSER_TEST')=='1' and config.database_url.endswith('/pao_test') and redis.database==15
assert queue.startswith('pao-test:sources-browser:') and config.chat_features_enabled and config.engine_contract_enabled
assert not any((config.memory_enabled,config.tools_enabled,config.meta_enabled,config.google_ads_enabled,config.telegram_enabled))
class Fixture:
    provider_name='ollama';model_name=config.ollama_model
    async def plan(self,messages):return ExecutionPlan(goal='Synthetic P3 verification',steps=[],tools=[])
    async def stream(self,messages,max_tokens=None):
        assert any(row['content'].startswith('P3 fixture:') for row in messages)
        yield Chunk(text='P3 synthetic response');await asyncio.sleep(.3)
        yield Chunk(usage={'prompt_eval_count':100,'eval_count':5})
async def execute_run(ctx,rid):
    async with Session() as db:
        row=await db.get(Run,rid)
        assert row and row.prompt.startswith('P3 fixture:') and row.engine_snapshot['provider']=='ollama'
    await actual_execute({**ctx,'gateway':Fixture()},rid)
async def dispatch(ctx):
    async with Session() as db:
        for row in await db.scalars(select(Run).where(Run.status=='queued')):
            if row.prompt.startswith('P3 fixture:'):await ctx['redis'].enqueue_job('execute_run',row.id,_job_id='p3-browser:'+row.id,_queue_name=queue)
class Worker:
    functions=[execute_run];redis_settings=redis;queue_name=queue;max_jobs=1;handle_signals=False;job_timeout=30;max_tries=1;keep_result=0
    on_startup=dispatch;cron_jobs=[cron(dispatch,name=queue+':dispatch',second=set(range(0,60,2)),run_at_startup=True)]
if __name__=='__main__':create_worker(Worker).run()
