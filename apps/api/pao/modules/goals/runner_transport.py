"""One leased outbox owner for the opt-in v1 runner, including cancellation."""
import asyncio
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select,or_
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from ...config import settings
from ...db import Session
from ...models import GoalCommand,GoalEvent,now
from ...auth import Principal
from ..studio import durable
from ..studio.contracts import digest
from . import ledger,runner
from .evidence import verify_admission
from .runner_workflow import PaoGoalRunnerWorkflow


class RunnerGateway:
    def __init__(self,client):self.client=client

    async def target(self,row):
        history=await self.client.get_workflow_handle(row.temporal_id).fetch_history()
        if not history.events:runner.invalid('goal_runner_target_missing')
        first=history.events[0].workflow_execution_started_event_attributes
        payload=await self.client.data_converter.decode(first.input.payloads)
        if (first.workflow_type.name!='PaoGoalRunnerWorkflow' or first.task_queue.name!=settings().workflow_temporal_task_queue or
            len(payload)!=1 or payload[0]!={'execution_id':row.id}):runner.invalid('goal_runner_workflow_collision')

    async def deliver(self,row,item):
        if self.client.namespace!=settings().temporal_namespace:runner.invalid('goal_runner_namespace_invalid')
        if item.operation=='start':
            try:
                await self.client.start_workflow(PaoGoalRunnerWorkflow.run,{'execution_id':row.id},id=row.temporal_id,
                    task_queue=settings().workflow_temporal_task_queue,id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                    execution_timeout=timedelta(seconds=row.envelope['policy']['max_elapsed_seconds']+180))
            except WorkflowAlreadyStartedError:await self.target(row)
        else:
            await self.target(row)
            await self.client.get_workflow_handle(row.temporal_id).signal(PaoGoalRunnerWorkflow.wake)


class RunnerDispatcher:
    def __init__(self,gateway):self.gateway=gateway

    async def dispatch(self):
        async with Session() as db:
            ids=list(await db.scalars(select(GoalCommand.id).where(
                GoalCommand.status.in_(['pending','processing']),GoalCommand.available_at<=now(),
                or_(GoalCommand.lease_until.is_(None),GoalCommand.lease_until<now()),
                select(GoalEvent.id).where(GoalEvent.execution_id==GoalCommand.execution_id,
                    GoalEvent.action=='runner_bound').exists()).order_by(GoalCommand.created_at).limit(50)))
        delivered=0
        for ident in ids:
            async with Session.begin() as db:
                lookup=await db.get(GoalCommand,ident);row=await ledger.lock_execution(db,lookup.execution_id)
                item=await db.scalar(select(GoalCommand).where(GoalCommand.id==ident).with_for_update().execution_options(populate_existing=True))
                if (item.status not in ('pending','processing') or item.available_at>now() or
                    item.lease_until and item.lease_until>now()):continue
                if await db.scalar(select(GoalCommand.id).where(GoalCommand.execution_id==row.id,
                    GoalCommand.ordinal<item.ordinal,GoalCommand.status.in_(['pending','processing'])).limit(1)):continue
                await runner.bound(db,row);await runner.verify_command(db,row,item)
                if item.attempts>=8:item.status='dead';item.error_code='delivery_exhausted';continue
                if item.operation!='cancel':
                    if row.cancel_requested or row.status in runner.TERMINAL:
                        item.status='dead';item.error_code='execution_stopped';continue
                    if not runner.enabled():continue
                    from fastapi import HTTPException
                    try:
                        await verify_admission(db,row);await durable.authorize(db,row,Principal(item.actor_id,0))
                    except HTTPException:
                        item.status='dead';item.error_code='authorization_or_evidence_invalid';continue
                    if row.cancel_requested or row.status in runner.TERMINAL:
                        item.status='dead';item.error_code='execution_stopped';continue
                token=str(uuid4());item.status='processing';item.attempts+=1
                item.lease_token=token;item.lease_until=now()+timedelta(seconds=30)
            error=None
            try:await asyncio.wait_for(self.gateway.deliver(row,item),10)
            except Exception as exc:error=type(exc).__name__[:64]
            async with Session.begin() as db:
                await ledger.lock_execution(db,row.id)
                saved=await db.scalar(select(GoalCommand).where(GoalCommand.id==ident).with_for_update())
                if saved.lease_token!=token or saved.status!='processing':continue
                saved.lease_token=None;saved.lease_until=None
                if error:
                    saved.status='dead' if saved.attempts>=8 else 'pending';saved.error_code=error
                    saved.available_at=now()+timedelta(seconds=min(60,2**saved.attempts))
                else:saved.status='delivered';saved.delivered_at=now();saved.error_code=None;delivered+=1
        return delivered


async def dispatch_goal_runners(ctx):
    # No connection when no accepted runner commands exist. Cancellation must
    # still be transported when admission has been turned off.
    async with Session() as db:
        pending=await db.scalar(select(GoalCommand.id).where(GoalCommand.status.in_(['pending','processing']),
            select(GoalEvent.id).where(GoalEvent.execution_id==GoalCommand.execution_id,
                GoalEvent.action=='runner_bound').exists()).limit(1))
    if not pending:return
    client=await asyncio.wait_for(Client.connect(settings().temporal_address,namespace=settings().temporal_namespace),5)
    await RunnerDispatcher(RunnerGateway(client)).dispatch()
