"""P6.2C dry-run step ledger; explicit calls only, not a live queue executor.

Execution row locks serialize reserve/claim/finish/cancel. Immutable StudioEvents
anchor envelopes, claim tokens and outcomes; TaskAttempt is a mutable projection.
Lost claims are UNKNOWN and cannot be automatically repeated.
"""
from datetime import timedelta
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import select
from ...db import Session
from ...models import StudioEvent, TaskAttempt, now
from . import durable
from .contracts import digest, validate_value
from .results import fixture_echo, verify_result
from .service import reject

LEASE_SECONDS = 60


def event_id(execution_id, kind):
    return str(uuid5(UUID(execution_id), 'p62-step:' + kind))


async def context(db, plan_id, step_id, execution_id, admission=True):
    row = await durable.lock_execution(db, plan_id)
    if not any(s['step_id'] == step_id and s['execution_id'] == execution_id for s in row.command['steps']):
        reject('durable_step_scope', 404)
    plan = await db.get(StudioEvent, row.plan_id)
    if admission:
        durable.require_admission()
        if row.cancel_requested or row.status != 'running' or row.state.get('current_step') != step_id:
            reject('durable_step_not_running', 409)
        snapshot = await durable.verify_plan(db, plan, row.actor_id)
    else:
        snapshot = plan.data['snapshot']
    step = next(s for s in snapshot['steps'] if s['step_id'] == step_id)
    return row, plan, snapshot, step


def append(db, row, plan, execution_id, kind, data):
    db.add(StudioEvent(id=event_id(execution_id, kind), workspace_id=row.workspace_id,
        definition_id=row.definition_id, version_id=plan.version_id, actor_id=row.actor_id,
        action='p62_step_' + kind, data={'plan_id': row.id, 'execution_id': execution_id, **data}))


async def resolve_input(db, row, snapshot, step):
    resolved = {}
    outputs = {}
    for predecessor in step['depends_on']:
        if predecessor not in row.state.get('completed_steps', []):
            reject('durable_dependency_not_completed', 409)
        predecessor_id = str(uuid5(UUID(row.id), predecessor))
        event = await db.get(StudioEvent, event_id(predecessor_id, 'outcome'))
        pin = next(s for s in snapshot['steps'] if s['step_id'] == predecessor)
        if not event or event.workspace_id != row.workspace_id or event.data.get('plan_id') != row.id:
            reject('durable_dependency_receipt_missing', 409)
        value = event.data
        if value.get('status') != 'completed' or value.get('origin') != 'fixture_echo' or value.get('dry_run') is not True:
            reject('durable_dependency_receipt_invalid', 409)
        try:
            if verify_result(pin['skill']['payload'], value['input'], value['output']) != value['receipt']:
                raise ValueError()
            outputs[predecessor] = value['output']
        except (ValueError, KeyError, TypeError):
            reject('durable_dependency_receipt_invalid', 409)
    for field, binding in step['input_bindings'].items():
        if binding['source'] == 'workflow':
            resolved[field] = snapshot['input'][binding['field']]
        else:
            predecessor = binding['step']
            if predecessor not in step['depends_on'] or predecessor not in row.state.get('completed_steps', []):
                reject('durable_dependency_not_completed', 409)
            try:
                resolved[field] = outputs[predecessor][binding['field']]
            except (KeyError, TypeError):
                reject('durable_dependency_receipt_invalid', 409)
    try:
        validate_value(step['skill']['payload']['input_schema'], resolved)
    except (ValueError, TypeError):
        reject('durable_step_input_invalid')
    return resolved


async def reserve(plan_id, step_id, execution_id):
    """Persist the envelope before a future enqueue; duplicate is hash-identical."""
    async with Session.begin() as db:
        row, plan, snapshot, step = await context(db, plan_id, step_id, execution_id)
        input_value = await resolve_input(db, row, snapshot, step)
        envelope = {'step_id': step_id, 'snapshot_hash': row.snapshot_hash,
            'input': input_value, 'contract_hash': step['skill']['hash'], 'dry_run': True,
            'adapter': 'fixture_echo'}
        saved = await db.get(StudioEvent, event_id(execution_id, 'reserved'))
        if saved:
            if saved.data['envelope'] != envelope:
                reject('durable_step_envelope_conflict', 409)
        else:
            append(db, row, plan, execution_id, 'reserved', {'envelope': envelope, 'hash': digest(envelope)})
        return {'execution_id': execution_id, 'envelope_hash': digest(envelope), 'dry_run': True}


async def stop_claim(db, row, plan, step_id, execution_id, attempt, status, error):
    attempt.status = status; attempt.error_code = error; attempt.finished_at = now()
    attempt.updated_at = now(); attempt.version += 1
    append(db, row, plan, execution_id, 'outcome', {'step_id': step_id,
        'status': status, 'error_code': error, 'dry_run': True, 'origin': 'fixture_echo'})
    if status == 'failed':
        row.status = 'manual_review'; row.version += 1; row.updated_at = now()


async def claim(plan_id, step_id, execution_id):
    async with Session.begin() as db:
        row, plan, snapshot, step = await context(db, plan_id, step_id, execution_id)
        reserved = await db.get(StudioEvent, event_id(execution_id, 'reserved'))
        if not reserved:
            reject('durable_step_not_reserved', 409)
        envelope = reserved.data['envelope']
        if digest(envelope) != reserved.data['hash'] or envelope['contract_hash'] != step['skill']['hash']:
            reject('durable_step_envelope_invalid', 409)
        attempt = await db.get(TaskAttempt, execution_id)
        if attempt:
            outcome = await db.get(StudioEvent, event_id(execution_id, 'outcome'))
            if outcome:
                return {'claimed': False, 'status': outcome.data['status']}
            claimed = await db.get(StudioEvent, event_id(execution_id, 'claimed'))
            if not claimed or attempt.status != 'running':
                reject('durable_step_projection_invalid', 409)
            if claimed.created_at + timedelta(seconds=LEASE_SECONDS) <= now():
                await stop_claim(db, row, plan, step_id, execution_id, attempt, 'failed', 'worker_lost_unknown')
            return {'claimed': False, 'status': attempt.status}
        # TaskAttempt is only a projection. Its loss must not mint a new token
        # or erase the immutable fact that this execution may have run.
        if (await db.get(StudioEvent, event_id(execution_id, 'claimed')) or
                await db.get(StudioEvent, event_id(execution_id, 'outcome'))):
            reject('durable_step_projection_invalid', 409)
        token = str(uuid4())
        db.add(TaskAttempt(id=execution_id, workspace_id=row.workspace_id, task_id=execution_id,
            request_key='p62:' + execution_id, input_fingerprint=digest(envelope),
            attempt_no=1, status='running', input=envelope['input'],
            skill_snapshot={'dry_run': True, 'studio_skill_version_id': step['skill']['version_id'],
                            'studio_contract_hash': step['skill']['hash']}, result={}, evidence=[]))
        append(db, row, plan, execution_id, 'claimed', {'step_id': step_id,
            'token': token, 'envelope_hash': digest(envelope), 'lease_seconds': LEASE_SECONDS})
        return {'claimed': True, 'token': token, 'input': envelope['input'],
                'contract': step['skill']['payload'], 'execution_id': execution_id}


async def finish(plan_id, step_id, execution_id, token, output):
    """Fence stale workers and commit receipt + attempt atomically.

    Only the fixed echo adapter is accepted, never arbitrary model output.
    A repeated finish returns the anchored receipt only for identical output.
    """
    async with Session.begin() as db:
        row, plan, snapshot, step = await context(db, plan_id, step_id, execution_id, admission=False)
        claimed = await db.get(StudioEvent, event_id(execution_id, 'claimed'))
        attempt = await db.get(TaskAttempt, execution_id)
        if not claimed or claimed.data['token'] != token or not attempt:
            reject('durable_step_claim_invalid', 409)
        outcome = await db.get(StudioEvent, event_id(execution_id, 'outcome'))
        if outcome:
            if outcome.data['status'] == 'completed':
                try:
                    if digest(outcome.data['output']) != digest(output):
                        raise ValueError()
                except (ValueError, TypeError, OverflowError, RecursionError):
                    reject('durable_step_result_conflict', 409)
            return {'status': outcome.data['status'], 'receipt': outcome.data.get('receipt')}
        if attempt.status != 'running':
            reject('durable_step_projection_invalid', 409)
        if claimed.created_at + timedelta(seconds=LEASE_SECONDS) <= now():
            await stop_claim(db, row, plan, step_id, execution_id, attempt, 'failed', 'worker_lost_unknown')
            return {'status': 'failed', 'error_code': 'worker_lost_unknown'}
        if row.cancel_requested or row.status == 'cancelled':
            await stop_claim(db, row, plan, step_id, execution_id, attempt, 'cancelled', 'cancel_requested')
            return {'status': 'cancelled'}
        try:
            await context(db, plan_id, step_id, execution_id)
        except HTTPException:
            await stop_claim(db, row, plan, step_id, execution_id, attempt, 'failed', 'permission_or_gate_lost')
            return {'status': 'failed', 'error_code': 'permission_or_gate_lost'}
        reserved = await db.get(StudioEvent, event_id(execution_id, 'reserved'))
        input_value = reserved.data['envelope']['input']
        try:
            result = fixture_echo(step['skill']['payload'], input_value)
            if digest(output) != digest(result['output']):
                raise ValueError('not_echo')
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
            await stop_claim(db, row, plan, step_id, execution_id, attempt, 'failed', 'invalid_fixture_result')
            return {'status': 'failed', 'error_code': 'invalid_fixture_result'}
        receipt = result['receipt']
        attempt.status = 'completed'; attempt.result = result; attempt.finished_at = now()
        attempt.updated_at = now(); attempt.version += 1
        append(db, row, plan, execution_id, 'outcome', {'step_id': step_id, 'status': 'completed',
            'input': input_value, 'output': result['output'], 'receipt': receipt,
            'dry_run': True, 'origin': 'fixture_echo'})
        return {'status': 'completed', 'receipt': receipt}


async def recover(plan_id, step_id, execution_id):
    """Explicit recovery can drain cancellation with admission flags off."""
    async with Session.begin() as db:
        row, plan, _, _ = await context(db, plan_id, step_id, execution_id, admission=False)
        outcome = await db.get(StudioEvent, event_id(execution_id, 'outcome'))
        if outcome:
            return {'status': outcome.data['status']}
        attempt = await db.get(TaskAttempt, execution_id)
        if not attempt:
            if await db.get(StudioEvent, event_id(execution_id, 'claimed')):
                reject('durable_step_projection_invalid', 409)
            reserved = await db.get(StudioEvent, event_id(execution_id, 'reserved'))
            if reserved and row.cancel_requested:
                append(db, row, plan, execution_id, 'outcome', {'step_id': step_id,
                    'status': 'cancelled', 'error_code': 'cancelled_before_claim',
                    'dry_run': True, 'origin': 'fixture_echo'})
                return {'status': 'cancelled', 'known_no_effect': True}
            return {'status': 'pending' if reserved else 'absent', 'known_no_effect': True}
        if attempt.status != 'running':
            reject('durable_step_projection_invalid', 409)
        claimed = await db.get(StudioEvent, event_id(execution_id, 'claimed'))
        if not claimed:
            reject('durable_step_projection_invalid', 409)
        if row.cancel_requested:
            await stop_claim(db, row, plan, step_id, execution_id, attempt, 'cancelled', 'cancel_requested')
        elif claimed.created_at + timedelta(seconds=LEASE_SECONDS) <= now():
            await stop_claim(db, row, plan, step_id, execution_id, attempt, 'failed', 'worker_lost_unknown')
        return {'status': attempt.status, 'error_code': attempt.error_code}


async def fail_pending(plan_id, step_id, execution_id):
    """Fail closed after authority loss before claim; no attempt/effect exists."""
    async with Session.begin() as db:
        row, plan, _, _ = await context(db, plan_id, step_id, execution_id, admission=False)
        if await db.get(TaskAttempt, execution_id) or await db.get(StudioEvent, event_id(execution_id, 'outcome')):
            return
        if await db.get(StudioEvent, event_id(execution_id, 'claimed')):
            reject('durable_step_projection_invalid', 409)
        if not await db.get(StudioEvent, event_id(execution_id, 'reserved')):
            return
        append(db, row, plan, execution_id, 'outcome', {'step_id': step_id, 'status': 'failed',
            'error_code': 'permission_or_gate_lost', 'known_no_effect': True,
            'dry_run': True, 'origin': 'fixture_echo'})
        row.status = 'manual_review'; row.version += 1; row.updated_at = now()
