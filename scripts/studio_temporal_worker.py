"""Dedicated dry-run worker; never registers legacy automation/provider activities.

Leave admission/dispatch off during drain. Keep this worker enabled until accepted
workflows are cancelled/reconciled; do not disable a worker before draining it.
"""
import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from temporalio.client import Client
from temporalio.worker import Worker
from redis.exceptions import RedisError
from pao.config import settings
from pao.modules.studio.arq_bridge import DryRunBridge, worker_marker
from pao.modules.studio.durable import project_state
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow
from pao.modules.goals.runner_workflow import PaoGoalRunnerWorkflow
from pao.modules.goals.runner import poll_activity,launch_activity,finish_activity,stop_activity,uncertain_activity,RunnerActivities

async def main():
    c = settings()
    if not c.workflow_worker_enabled:
        raise SystemExit('Studio worker disabled; no connections made')
    redis = await create_pool(RedisSettings.from_dsn(c.redis_url))
    heartbeat=None
    marker=worker_marker()
    async def lease():
        while True:
            await asyncio.wait_for(redis.set('pao:studio:temporal:health',marker,ex=20),timeout=2)
            await asyncio.sleep(5)
    try:
        client = await Client.connect(c.temporal_address, namespace=c.temporal_namespace)
        bridge = DryRunBridge(redis)
        goals = RunnerActivities(redis)
        async with Worker(client, task_queue=c.workflow_temporal_task_queue,
                workflows=[PaoPlannedDryRunWorkflow,PaoGoalRunnerWorkflow],
                activities=[project_state,bridge.step,poll_activity,launch_activity,finish_activity,
                    stop_activity,uncertain_activity,goals.reconcile]):
            heartbeat=asyncio.create_task(lease())
            # Health publisher failure terminates this worker, rather than
            # leaving an unobserved failed task and a misleading process PID.
            await heartbeat
    finally:
        if heartbeat:
            heartbeat.cancel(); await asyncio.gather(heartbeat,return_exceptions=True)
        try:
            if await asyncio.wait_for(redis.get('pao:studio:temporal:health'),timeout=2)==marker.encode():
                await asyncio.wait_for(redis.delete('pao:studio:temporal:health'),timeout=2)
        except (RedisError,asyncio.TimeoutError,OSError):
            pass # its existing readiness lease expires; no fabricated heartbeat
        await redis.aclose()

if __name__ == '__main__':
    asyncio.run(main())
