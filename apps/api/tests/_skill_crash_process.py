"""OS-process fault harness. Refuses non-test DB; never imported by production."""
import asyncio
import sys
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pao.config import settings
from pao.db import engine
from pao import runtime, tool_gateway


async def main():
    config = settings()
    if not config.database_url.endswith('/pao_test'):
        raise RuntimeError('Dedicated pao_test database required')
    config.memory_enabled = False
    # Mirror the parent fixture: do not inherit live P3/P4 flags from .env.
    config.engine_contract_enabled = config.chat_features_enabled = True
    config.studio_enabled = False
    config.knowledge_enabled = config.knowledge_sources_enabled = False
    config.agent_runtime_enabled = False
    config.tools_enabled = True
    config.run_timeout_seconds = 10
    config.meta_enabled = config.google_ads_enabled = config.temporal_enabled = False
    mode, run_id = sys.argv[1:]
    ctx = {'gateway': SimpleNamespace(provider_name='ollama',model_name=config.ollama_model), 'redis': AsyncMock()}
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
    elif mode == 'recover':
        # Simulate lease expiry in the restarted process, not by modifying DB.
        # This is not a wall-clock recovery-latency measurement.
        clock = runtime.now
        runtime.now = tool_gateway.now = lambda: clock() + timedelta(seconds=120)
        await runtime.dispatch(ctx)
        await runtime.dispatch(ctx)
        await runtime.execute_run(ctx, run_id)
        assert ctx['redis'].enqueue_job.await_count == 0, 'Interrupted run was re-enqueued'
        await engine.dispose()
        print('RECOVERY_DONE', flush=True)
        return
    else:
        raise ValueError('Unknown harness mode')
    await runtime.execute_run(ctx, run_id)
    raise AssertionError('Fault point was not killed')


if __name__ == '__main__':
    asyncio.run(main())
