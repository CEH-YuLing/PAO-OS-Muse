"""Explicit dry-run ARQ/Temporal wiring; not registered in the live runtime.

ARQ results are not evidence: only verified immutable DB outcomes are accepted.
The queue carries stable IDs, never instructions, executable code or credentials.
"""
import asyncio
from temporalio import activity
from temporalio.exceptions import ApplicationError
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from ...db import Session
from ...models import StudioEvent, now
from ...config import settings
from sqlalchemy import select
from ...models import StudioExecution
from fastapi import HTTPException
from sqlalchemy import cast, Uuid
from sqlalchemy.orm import aliased
from . import durable, step_jobs as jobs
from .results import verify_result
from ...skills import execution_binding

def worker_marker():
    return execution_binding()['sha256'] + ':' + settings().workflow_temporal_task_queue


async def execute_studio_echo(ctx, plan_id, step_id, execution_id):
    try:
        claimed = await jobs.claim(plan_id, step_id, execution_id)
        if not claimed['claimed']:
            return {'status': claimed['status'], 'duplicate': True}
        # No provider/tool call inside the fixed adapter. ARQ abort must still
        # persist native cancellation when the DB already requested it.
        return await jobs.finish(plan_id, step_id, execution_id, claimed['token'], claimed['input'])
    except asyncio.CancelledError:
        # Do not invent a user cancel on generic worker shutdown. recover()
        # observes the durable flag, otherwise keeps running/UNKNOWN evidence.
        await asyncio.shield(jobs.recover(plan_id, step_id, execution_id))
        raise


async def verified_receipt(plan_id, step_id, execution_id):
    async with Session.begin() as db:
        row, plan, _, step = await jobs.context(db, plan_id, step_id, execution_id, admission=False)
        event = await db.get(StudioEvent, jobs.event_id(execution_id, 'outcome'))
        if not event or event.data['status'] != 'completed':
            return None
        durable.require_admission()
        await durable.verify_plan(db, plan, row.actor_id)
        value = event.data
        if (value.get('origin') != 'fixture_echo' or value.get('dry_run') is not True or
                verify_result(step['skill']['payload'], value['input'], value['output']) != value['receipt']):
            raise ApplicationError('invalid_db_receipt', non_retryable=True)
        return {'execution_id': execution_id, 'status': 'completed', 'dry_run': True}


async def cancel_and_drain(plan_id, step_id, execution_id):
    async with Session.begin() as db:
        row, _, _, _ = await jobs.context(db, plan_id, step_id, execution_id, admission=False)
        if row.status not in durable.TERMINAL:
            row.cancel_requested = True; row.version += 1; row.updated_at = now()
    return await jobs.recover(plan_id, step_id, execution_id)


async def dispatch_studio(ctx):
    """Bounded reconciliation; no new enqueue with gates off, cancel still drains."""
    c = settings()
    if c.workflow_worker_enabled:
        await ctx['redis'].set('pao:studio:arq:health', worker_marker(), ex=20)
    outcome = aliased(StudioEvent)
    unresolved = select(cast(StudioEvent.data['plan_id'].as_string(), Uuid(as_uuid=False))).where(
        StudioEvent.action == 'p62_step_reserved',
        ~select(outcome.id).where(outcome.action == 'p62_step_outcome',
            outcome.data['execution_id'].as_string() == StudioEvent.data['execution_id'].as_string())
            .exists().correlate(StudioEvent))
    async with Session() as db:
        rows = list(await db.scalars(select(StudioExecution).where(
            StudioExecution.id.in_(unresolved))
            .order_by(StudioExecution.updated_at).limit(50)))
    for row in rows:
        step_id = row.state.get('current_step')
        step = next((s for s in row.command['steps'] if s['step_id'] == step_id), None)
        if not step:
            continue
        args = (row.id, step_id, step['execution_id'])
        state = await jobs.recover(*args)
        if state['status'] == 'pending' and all((c.workflow_worker_enabled,
                c.workflow_dispatch_enabled, c.workflow_durable_enabled, c.temporal_enabled)):
            # Revalidate membership/pins immediately before enqueue. Worker also
            # checks before claim and result commit; Redis cannot grant authority.
            try:
                await jobs.reserve(*args)
                await asyncio.wait_for(ctx['redis'].enqueue_job('execute_studio_echo', *args,
                    _job_id='p62:' + args[2], _expires=60), timeout=2)
            except HTTPException:
                await jobs.fail_pending(*args)
            except (OSError, asyncio.TimeoutError, RedisConnectionError, RedisTimeoutError):
                pass  # pending is known-no-effect; next bounded pass recovers it
    if c.workflow_worker_enabled:
        await asyncio.wait_for(durable.dispatch_commands(), timeout=10)


class DryRunBridge:
    """Inject an explicitly selected Redis pool; no default live connection."""
    def __init__(self, redis, *, require_queue_ack=False):
        if type(require_queue_ack) is not bool:
            raise ValueError('require_queue_ack must be bool')
        self.redis = redis
        self.require_queue_ack = require_queue_ack

    async def drain(self, args):
        if not self.require_queue_ack:
            return await cancel_and_drain(*args)
        # Explicit opt-in only. A persisted, authorized cancel command is
        # required; generic activity shutdown cannot manufacture user consent.
        from .queue_cancel import cancel_queue_step
        result = await cancel_queue_step(self.redis, *args)
        if result.get('queue_ack_verified') is not True:
            raise ApplicationError('step_queue_drain_unknown', non_retryable=True)
        return result

    @activity.defn(name='p62_dryrun_step')
    async def step(self, data: dict):
        args = (data['plan_id'], data['step_id'], data['execution_id'])
        try:
            receipt = await verified_receipt(*args)
            if receipt:
                return receipt
            await jobs.reserve(*args)
            deadline = asyncio.get_running_loop().time() + 25
            while asyncio.get_running_loop().time() < deadline:
                activity.heartbeat({'execution_id': args[2]})
                state = await jobs.recover(*args)
                if state['status'] == 'completed':
                    return await verified_receipt(*args)
                if state['status'] in ('failed', 'cancelled'):
                    if state['status'] == 'cancelled' and self.require_queue_ack:
                        await self.drain(args)
                        # The database cancel is committed before its outbox
                        # signal reaches Temporal. A verified native abort is
                        # not an activity failure: keep heartbeating within the
                        # existing deadline until Temporal delivers cancellation.
                        # If that signal is lost, the deadline still fails closed.
                        await asyncio.sleep(.2)
                        continue
                    raise ApplicationError('step_' + state['status'], non_retryable=True)
                if state['status'] == 'pending':
                    # Recovery of enqueue failure/lost queued entry is safe only
                    # before claim. A running or UNKNOWN claim is never requeued.
                    try:
                        await asyncio.wait_for(self.redis.enqueue_job('execute_studio_echo', *args,
                            _job_id='p62:' + args[2], _expires=60), timeout=2)
                    except (OSError, asyncio.TimeoutError, RedisConnectionError, RedisTimeoutError):
                        pass  # bounded by the activity deadline; ledger remains.
                await asyncio.sleep(.2)
            raise ApplicationError('step_bridge_timeout', non_retryable=True)
        except asyncio.CancelledError:
            await asyncio.shield(self.drain(args))
            raise
