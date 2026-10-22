"""Real ARQ fault worker: dedicated pao_test + Redis DB15 + unique queue only."""
import asyncio
import os
from types import SimpleNamespace

from arq import cron
from arq.connections import RedisSettings
from arq.worker import create_worker
from pao.config import settings
from pao import runtime, tool_gateway

config = settings()
queue = os.environ.get('PAO_TEST_ARQ_QUEUE', '')
redis_settings = RedisSettings.from_dsn(config.redis_url)
if (not config.database_url.endswith('/pao_test') or redis_settings.database != 15 or
        not queue.startswith('pao-test:arq-recovery:')):
    raise RuntimeError('Dedicated test DB, Redis DB15 and test queue required')
config.memory_enabled = config.agent_runtime_enabled = False
config.engine_contract_enabled = config.chat_features_enabled = True
config.studio_enabled = False
config.knowledge_enabled = config.knowledge_sources_enabled = False
config.tools_enabled = True
config.run_timeout_seconds = 10
config.meta_enabled = config.google_ads_enabled = config.temporal_enabled = False
mode = os.environ['PAO_TEST_ARQ_FAULT']
if mode == 'recover':
    # Restarted configuration is longer; the old effective 10s pin must win.
    config.run_timeout_seconds = 120
if mode == 'between':
    execute = runtime.execute_tool

    async def pause_after_first(ctx, call_id):
        await execute(ctx, call_id)
        print('FAULT_READY', flush=True)
        await asyncio.sleep(3600)

    runtime.execute_tool = pause_after_first
elif mode == 'during':
    async def pause_read(*args):
        print('FAULT_READY', flush=True)
        await asyncio.sleep(3600)

    tool_gateway.read_tasks = pause_read
elif mode != 'recover':
    raise ValueError('Unknown fault mode')


async def startup(ctx):
    ctx['gateway'] = SimpleNamespace(provider_name='ollama',model_name=config.ollama_model)
    await runtime.dispatch(ctx)


class RecoveryWorker:
    functions = [runtime.execute_run, runtime.execute_tool]
    redis_settings = redis_settings
    queue_name = queue
    max_jobs = 1
    handle_signals = False
    job_timeout = 30
    keep_result = 0
    max_tries = 1
    on_startup = startup
    # Same 10s cadence; unique cron name avoids sharing test keys.
    cron_jobs = [cron(runtime.dispatch, name=f'{queue}:dispatch',
                      second=set(range(0, 60, 10)), run_at_startup=True)]


if __name__ == '__main__':
    create_worker(RecoveryWorker).run()
