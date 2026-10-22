"""Explicit leased Goal command transport. No live registration/iteration grant."""
import asyncio
from datetime import timedelta
from uuid import UUID,uuid4,uuid5
from sqlalchemy import select,or_
from fastapi import HTTPException
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import GoalCommand,GoalEvent,now
from ..studio import durable
from ..studio.contracts import digest
from ..studio.service import reject
from . import ledger
from .control import TERMINAL
from .evidence import verify_admission
from .workflow import PaoBoundedDryRunGoalWorkflow as GoalW


async def verify_command(db,row,item):
    value={'command_id':item.id,'operation':item.operation,'ordinal':item.ordinal}
    event=await db.get(GoalEvent,str(uuid5(UUID(item.id),'audit')))
    if (row.temporal_id!='p63-'+row.id or item.execution_id!=row.id or item.workspace_id!=row.workspace_id or
            item.operation not in ('start','decision','cancel') or
            item.id!=str(uuid5(UUID(row.id),item.request_key)) or
            item.content_hash!=digest({'operation':item.operation,'payload':item.payload,'actor_id':item.actor_id}) or
            not event or event.execution_id!=row.id or event.workspace_id!=row.workspace_id or
            event.actor_id!=item.actor_id or event.action!='command' or event.data!=value or
            event.content_hash!=digest({'action':'command','data':value,'actor_id':item.actor_id}) or
            (item.operation=='cancel' and (item.payload!={} or row.cancel_requested is not True))):
        reject('goal_dispatch_command_invalid',409)


class GoalGateway:
    """Trusted injected client only; cannot connect from user/browser input."""
    def __init__(self,client):self.client=client

    async def verify_target(self,row):
        history=await self.client.get_workflow_handle(row.temporal_id).fetch_history()
        if not history.events:reject('goal_dispatch_workflow_collision',409)
        first=history.events[0].workflow_execution_started_event_attributes
        decoded=await self.client.data_converter.decode(first.input.payloads)
        payload={'envelope':row.envelope,'initial_proposal':row.initial_proposal}
        if (first.workflow_type.name!='PaoBoundedDryRunGoalWorkflow' or
                first.task_queue.name!=settings().workflow_temporal_task_queue or
                len(decoded)!=1 or digest(decoded[0])!=digest(payload)):
            reject('goal_dispatch_workflow_collision',409)

    async def deliver(self,row,item):
        if self.client.namespace!=settings().temporal_namespace:
            reject('goal_dispatch_namespace_invalid',409)
        payload={'envelope':row.envelope,'initial_proposal':row.initial_proposal}
        if item.operation=='start':
            try:
                await self.client.start_workflow(GoalW.run,payload,id=row.temporal_id,
                    task_queue=settings().workflow_temporal_task_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                    execution_timeout=timedelta(seconds=row.envelope['policy']['max_elapsed_seconds']+180))
            except WorkflowAlreadyStartedError:
                # A workflow-ID collision is NOT an ACK. Compare its immutable
                # initial event/input before accepting an ambiguous retry.
                await self.verify_target(row)
        else:
            await self.verify_target(row)
            handle=self.client.get_workflow_handle(row.temporal_id)
            if item.operation=='cancel':await handle.signal(GoalW.request_cancel)
            else:await handle.signal(GoalW.decide,{
                'proposal_hash':item.payload['proposal_hash'],'decision':item.payload['decision']})


class GoalDispatcher:
    """Bounded explicit pass, ordered per execution, no DB lock across network.

    Gate rollback blocks starts/decisions, never cancellation. ACK means command
    delivery only, NOT child/ARQ drain or budget release. Pre-child adapters still
    deny iteration. No runtime cron/worker/API registration.
    """
    def __init__(self,gateway,*,allow_start=False):
        if type(allow_start) is not bool:raise ValueError('allow_start must be bool')
        self.gateway=gateway;self.allow_start=allow_start

    async def dispatch(self):
        async with Session() as db:
            ids=list(await db.scalars(select(GoalCommand.id).where(
                GoalCommand.status.in_(['pending','processing']),GoalCommand.available_at<=now(),
                or_(GoalCommand.lease_until.is_(None),GoalCommand.lease_until<now()))
                .order_by(GoalCommand.created_at).limit(50)))
        delivered=0
        for ident in ids:
            async with Session.begin() as db:
                lookup=await db.get(GoalCommand,ident)
                if not lookup:continue
                row=await ledger.lock_execution(db,lookup.execution_id)
                from .runner import event_id
                if await db.get(GoalEvent,event_id(row,'bound')):continue
                item=await db.scalar(select(GoalCommand).where(GoalCommand.id==ident)
                    .with_for_update().execution_options(populate_existing=True))
                if (item.status not in ('pending','processing') or item.available_at>now() or
                        (item.lease_until and item.lease_until>now())):continue
                earlier=await db.scalar(select(GoalCommand.id).where(GoalCommand.execution_id==row.id,
                    GoalCommand.ordinal<item.ordinal,GoalCommand.status.in_(['pending','processing'])).limit(1))
                if earlier:continue
                if item.attempts>=8:
                    item.status='dead';item.error_code='delivery_exhausted';continue
                try:
                    await verify_command(db,row,item)
                    if item.operation!='cancel':
                        c=settings()
                        if not (self.allow_start and c.goal_admission_enabled and c.temporal_enabled and
                                c.studio_enabled and c.workflow_planning_enabled):continue
                        await verify_admission(db,row)
                        await durable.authorize(db,row,Principal(item.actor_id,0))
                        if row.cancel_requested or row.status in TERMINAL:
                            item.status='dead';item.error_code='execution_stopped';continue
                        if item.operation=='decision' and (row.status!='waiting_approval' or
                                set(item.payload)!={'version','proposal_hash','decision'} or
                                item.payload['proposal_hash']!=row.state.get('proposal_hash') or
                                item.payload['decision'] not in ('approve','reject')):
                            reject('goal_dispatch_decision_stale',409)
                except HTTPException:
                    item.status='dead';item.error_code='authorization_or_evidence_invalid';continue
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
                else:
                    saved.status='delivered';saved.delivered_at=now();saved.error_code=None;delivered+=1
        return delivered
