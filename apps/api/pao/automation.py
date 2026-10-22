"""Temporal boundary for the small allowlisted Phase 17 workflow surface."""
from datetime import timedelta
from temporalio import activity
from temporalio.client import Client
from sqlalchemy import or_, select

from .config import settings
from .db import Session
from .models import AutomationOutbox, AutomationWorkflow, now
from .automation_workflows import PaoAutomationWorkflow


class TemporalGateway:
    def __init__(self):
        self.client: Client | None = None

    async def connect(self):
        if not self.client:
            self.client = await Client.connect(settings().temporal_address, namespace=settings().temporal_namespace)
        return self.client

    async def start(self, workflow_id: str, payload: dict) -> str:
        client = await self.connect()
        try:
            handle = await client.start_workflow(PaoAutomationWorkflow.run, payload, id=workflow_id,
                task_queue=settings().temporal_task_queue,
                execution_timeout=timedelta(days=settings().temporal_workflow_timeout_days))
        except Exception as exc:
            # A retry after Temporal accepted the start but before PAO marked the
            # outbox delivered is success, not a second workflow.
            if type(exc).__name__ != 'WorkflowAlreadyStartedError':
                raise
            handle = client.get_workflow_handle(workflow_id)
            description = await handle.describe()
            return description.run_id or ''
        return handle.first_execution_run_id or ''

    async def signal(self, workflow_id: str, name: str, payload: dict | None = None):
        client = await self.connect();handle = client.get_workflow_handle(workflow_id)
        await handle.signal(name, payload or {})

    async def cancel(self, workflow_id: str):
        client = await self.connect();await client.get_workflow_handle(workflow_id).cancel()


gateway = TemporalGateway()


async def dispatch_automation(_ctx: dict | None = None) -> int:
    """Deliver committed automation commands to Temporal at least once.

    Deterministic workflow IDs and idempotent signals make retries safe. A
    short lease lets another worker recover an interrupted delivery.
    """
    claimed: list[str] = []
    cutoff = now() - timedelta(minutes=2)
    async with Session.begin() as db:
        items = list(await db.scalars(
            select(AutomationOutbox).where(
                AutomationOutbox.available_at <= now(),
                or_(AutomationOutbox.status == 'pending',
                    (AutomationOutbox.status == 'processing') & (AutomationOutbox.locked_at < cutoff)),
            ).order_by(AutomationOutbox.created_at).limit(50).with_for_update(skip_locked=True)
        ))
        for item in items:
            item.status = 'processing'
            item.attempts += 1
            item.locked_at = now()
            item.updated_at = now()
            claimed.append(item.id)

    delivered = 0
    for item_id in claimed:
        async with Session() as db:
            item = await db.get(AutomationOutbox, item_id)
            workflow_row = await db.get(AutomationWorkflow, item.workflow_id)
            operation, signal_name, payload = item.operation, item.signal_name, item.payload
            temporal_id = workflow_row.temporal_workflow_id
        try:
            run_id = await gateway.start(temporal_id, payload) if operation == 'start' else None
            if operation == 'signal':
                await gateway.signal(temporal_id, signal_name, payload)
        except Exception as exc:
            error_code = type(exc).__name__[:64]
            async with Session.begin() as db:
                item = await db.get(AutomationOutbox, item_id, with_for_update=True)
                if not item or item.status != 'processing':
                    continue
                item.last_error = error_code
                item.locked_at = None
                item.updated_at = now()
                if item.attempts >= 5:
                    item.status = 'dead'
                    row = await db.get(AutomationWorkflow, item.workflow_id, with_for_update=True)
                    if row and (item.operation == 'start' and row.status == 'starting' or
                                item.operation == 'signal' and row.status not in ('completed','failed','cancelled')):
                        row.status = 'failed'
                        row.error_code = 'automation_dispatch_failed'
                        row.completed_at = now()
                        row.updated_at = now()
                else:
                    item.status = 'pending'
                    item.available_at = now() + timedelta(seconds=min(2 ** item.attempts, 60))
            continue

        async with Session.begin() as db:
            item = await db.get(AutomationOutbox, item_id, with_for_update=True)
            if not item or item.status != 'processing':
                continue
            item.status = 'delivered'
            item.locked_at = None
            item.last_error = None
            item.updated_at = now()
            if item.operation == 'start':
                row = await db.get(AutomationWorkflow, item.workflow_id, with_for_update=True)
                row.temporal_run_id = run_id
                if row.status == 'starting':
                    row.status = ('waiting_approval' if item.payload['approval_required'] else
                                  'waiting_timer' if item.payload.get('wait_until') else 'running')
                    row.updated_at = now()
            delivered += 1
    return delivered


@activity.defn
async def project_workflow(change: dict) -> None:
    """Idempotent DB projection; Temporal history remains execution authority."""
    async with Session.begin() as db:
        row = await db.get(AutomationWorkflow, change['id'], with_for_update=True)
        if not row or row.status in ('completed','failed','cancelled'):
            return
        row.status = change['status'];row.updated_at = now()
        if 'approval_status' in change: row.approval_status = change['approval_status']
        if 'result' in change: row.result = change['result']
        if change['status'] in ('completed','failed','cancelled'): row.completed_at = now()
