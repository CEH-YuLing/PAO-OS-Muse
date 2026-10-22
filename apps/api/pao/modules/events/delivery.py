"""Postgres owns lease/retry/receipt. Redis merely wakes a fixed internal consumer."""
import asyncio
from datetime import timedelta, timezone
from sqlalchemy import select, or_, and_
from ...config import settings
from ...db import Session
from ...models import BusinessEvent, BusinessOutbox, BusinessReceipt, Member, User, now, uid
from .producer import checksum

MAX_ATTEMPTS = 5
LEASE_SECONDS = 60


def enabled():
    return settings().business_events_enabled and settings().business_event_delivery_enabled


def event_hash(event):
    keys = ('workspace_id', 'event_type', 'schema_version', 'aggregate_type', 'aggregate_id',
            'aggregate_version', 'actor_id', 'correlation_id', 'causation_id', 'payload_reference')
    return checksum({**{key: getattr(event, key) for key in keys},
                     'occurred_at': event.occurred_at.astimezone(timezone.utc).isoformat()})


async def claim(limit=20, lease_seconds=LEASE_SECONDS):
    if not enabled():
        return []
    claimed = []
    async with Session.begin() as db:
        moment = now()
        rows = await db.scalars(select(BusinessOutbox).where(or_(
            and_(BusinessOutbox.status == 'pending', BusinessOutbox.available_at <= moment),
            and_(BusinessOutbox.status == 'processing', BusinessOutbox.lease_until <= moment)))
            .order_by(BusinessOutbox.created_at, BusinessOutbox.id).limit(min(max(limit, 1), 100))
            .with_for_update(skip_locked=True))
        for row in rows:
            if row.attempts >= MAX_ATTEMPTS:
                row.status, row.error_code = 'dead_letter', 'attempts_exhausted'
                row.lease_token = row.lease_until = None
                continue
            row.status, row.lease_token = 'processing', uid()
            row.lease_until = moment + timedelta(seconds=max(1, lease_seconds))
            row.attempts += 1
            claimed.append((row.id, row.lease_token))
    return claimed


async def failed(outbox_id, token):
    # Error text/arguments are never persisted; stale workers cannot change a new lease.
    async with Session.begin() as db:
        row = await db.scalar(select(BusinessOutbox).where(BusinessOutbox.id == outbox_id).with_for_update())
        if not row or row.status != 'processing' or row.lease_token != token:
            return
        row.status = 'dead_letter' if row.attempts >= MAX_ATTEMPTS else 'pending'
        row.error_code = 'consumer_failed'
        row.available_at = now() + timedelta(seconds=min(2 ** row.attempts, 60))
        row.lease_token = row.lease_until = None


async def consume(outbox_id, token):
    if not enabled():
        return False
    async with Session.begin() as db:
        row = await db.scalar(select(BusinessOutbox).where(BusinessOutbox.id == outbox_id).with_for_update())
        if not row or row.status != 'processing' or row.lease_token != token or row.lease_until <= now():
            return False
        event = await db.get(BusinessEvent, row.event_id)
        user = await db.get(User, event.actor_id)
        member = await db.get(Member, (row.workspace_id, event.actor_id))
        reason = None
        if not user or not user.active or not member or member.role == 'viewer':
            reason = 'actor_permission_changed'
        elif event.schema_version != 1 or event.event_type not in ('task.completed','approval.requested','ads.analysis.completed') or event_hash(event) != event.content_hash:
            reason = 'event_profile_invalid'
        if reason:
            row.status, row.error_code = 'dead_letter', reason
            row.lease_token = row.lease_until = None
            return False
        receipt = await db.scalar(select(BusinessReceipt).where(BusinessReceipt.event_id == event.id))
        if receipt and (receipt.workspace_id != row.workspace_id or receipt.content_hash != event.content_hash):
            row.status, row.error_code = 'dead_letter', 'receipt_conflict'
            row.lease_token = row.lease_until = None
            return False
        if not receipt:
            db.add(BusinessReceipt(workspace_id=row.workspace_id, event_id=event.id,
                                   consumer='internal.audit.v1', content_hash=event.content_hash))
        # Receipt and acknowledgement commit together. No business task/action is created.
        row.status, row.delivered_at, row.error_code = 'delivered', now(), None
        row.lease_token = row.lease_until = None
    return True


async def deliver_business_event(ctx, outbox_id, token):
    try:
        return await consume(outbox_id, token)
    except asyncio.CancelledError:
        raise  # Lease expires; never acknowledge interrupted transactions.
    except Exception:
        await failed(outbox_id, token)
        return False


async def dispatch_business_events(ctx):
    for outbox_id, token in await claim():
        try:
            await ctx['redis'].enqueue_job('deliver_business_event', outbox_id, token,
                _job_id=f'business-event:{outbox_id}:{token}', _expires=LEASE_SECONDS)
        except Exception:
            await failed(outbox_id, token)
