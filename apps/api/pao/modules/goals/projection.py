"""P6.3B2b2a pre-child DB projection. NOT registered in a live worker.

This stage deliberately never grants iteration execution. Child claims and
trusted receipts must be implemented before running/completed projections.
"""
from uuid import UUID, uuid5

from fastapi import HTTPException
from temporalio import activity
from temporalio.exceptions import ApplicationError
from sqlalchemy import select

from ...config import settings
from ...db import Session
from ...models import GoalEvent, GoalCommand, now
from ..studio.contracts import digest
from .control import GoalControl, closed, integer, validate, TERMINAL
from .evidence import verify_admission
from .ledger import lock_execution, audit


def invalid(code):
    raise ApplicationError(code, non_retryable=True)


def validate_pre_child(row, state, stamp):
    """Reconstruct the closed, iteration-zero state; do not trust success/usage."""
    try:
        deadline = state['deadline_unix_ms']
        integer(deadline, 0, row.envelope['policy']['deadline_unix_ms'])
        elapsed = row.envelope['policy']['max_elapsed_seconds'] * 1000
        if not row.sequence and deadline > stamp + elapsed:
            raise ValueError()
        if row.sequence and deadline != row.state['deadline_unix_ms']:
            raise ValueError()
        start = max(0, deadline - elapsed)
        controller = GoalControl(row.envelope, start)
        expected = controller.propose(row.initial_proposal, start)
        if state['status'] == 'waiting_approval':
            if stamp >= deadline: raise ValueError()
        elif state['status'] == 'manual_review':
            expected = controller.uncertain(start)
        elif state['status'] == 'deadline_exceeded':
            if stamp < deadline: raise ValueError()
            expected = controller.advance(deadline)
        elif state['status'] == 'cancelled':
            # Custom cancel must first be persisted through the authorized API.
            if not row.cancel_requested or state['cancel_requested'] is not True: raise ValueError()
            expected = controller.cancel(start)
        else:
            raise ValueError()
        expected = {**expected, 'sequence':state['sequence'], 'child_id':None,
                    'transport_reason':state['transport_reason']}
        if type(state['cancel_requested']) is not bool:
            raise ValueError()
        # Workflow can observe the durable cancel just before its next reducer
        # tick. False does not erase the DB request; true needs DB provenance.
        if state['cancel_requested'] and not row.cancel_requested: raise ValueError()
        expected['cancel_requested'] = state['cancel_requested']
        if (digest(state) != digest(expected) or state['transport_reason'] not in
                (None,'permission_or_gate_lost','adapter_unavailable')):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        invalid('goal_projection_state_invalid')


async def project_pre_child(data, workflow_id):
    """Internal transaction helper; workflow identity comes from activity.info.

Not a browser/model endpoint. Tests call this helper with an explicit fixture
identity; that is not proof of live Temporal worker authentication.
"""
    try:
        closed(data, {'envelope','state'})
        envelope, state = data['envelope'], data['state']
        validate(envelope)
        closed(state, {'status','reason','iteration','cost_microusd','reserved_cost_microusd',
            'cancel_requested','proposal','proposal_hash','checks','receipt_hash','execution_id',
            'deadline_unix_ms','dry_run','model_executed','sequence','child_id','transport_reason'})
        integer(state['sequence'], 1, 2147483647)
        for field in ('iteration','cost_microusd','reserved_cost_microusd'):
            integer(state[field], 0, 0)
        if state['dry_run'] is not True or state['model_executed'] is not False:
            raise ValueError()
        ident = envelope['execution_id']
    except (ValueError, KeyError, TypeError):
        invalid('goal_projection_contract_invalid')
    async with Session.begin() as db:
        row = await lock_execution(db, ident)
        if workflow_id != row.temporal_id or digest(envelope) != digest(row.envelope):
            invalid('goal_projection_scope_invalid')
        start_command = await db.scalar(select(GoalCommand).where(
            GoalCommand.execution_id == row.id, GoalCommand.operation == 'start'))
        if (not start_command or start_command.attempts < 1 or
                start_command.status not in ('processing','delivered') or
                (start_command.status == 'processing' and not start_command.lease_token) or
                (start_command.status == 'delivered' and not start_command.delivered_at)):
            invalid('goal_projection_start_not_dispatched')
        # Reauthorization also happens on retries. Lost permission must never
        # block cancellation/drain or turn an old grant into a new permission.
        permission_error = None
        try: await verify_admission(db, row)
        except HTTPException as exc: permission_error = exc.detail
        sequence = state['sequence']
        event_id = str(uuid5(UUID(row.id), 'pre-child-projection:'+str(sequence)))
        previous = await db.get(GoalEvent, event_id)
        if previous:
            stored = {'state':state, 'receipt':{'allow_iteration':False,
                'cancel_requested':previous.data['receipt']['cancel_requested']},
                'scope':'pre_child_only', 'permission_error':previous.data['permission_error']}
            if (previous.execution_id != row.id or previous.workspace_id != row.workspace_id or
                    previous.actor_id != row.actor_id or previous.action != 'pre_child_projection' or
                    digest(previous.data) != digest(stored) or previous.content_hash != digest({
                        'action':'pre_child_projection','data':stored,'actor_id':row.actor_id})):
                invalid('goal_projection_retry_conflict')
            return {'allow_iteration':False, 'cancel_requested':row.cancel_requested}
        if row.status in TERMINAL:
            return {'allow_iteration':False, 'cancel_requested':row.cancel_requested}
        if sequence != row.sequence + 1:
            invalid('goal_projection_sequence_invalid')
        validate_pre_child(row, state, int(now().timestamp()*1000))
        receipt = {'allow_iteration':False, 'cancel_requested':row.cancel_requested}
        row.state = state; row.status = state['status']; row.sequence = sequence
        row.version += 1; row.updated_at = now()
        await audit(db, row, row.actor_id, 'pre_child_projection', {'state':state,
            'receipt':receipt, 'scope':'pre_child_only', 'permission_error':permission_error}, event_id)
        return receipt


@activity.defn(name='p63_project')
async def project_state(data:dict):
    info = activity.info()
    if (info.workflow_type != 'PaoBoundedDryRunGoalWorkflow' or
            info.workflow_namespace != settings().temporal_namespace or
            info.task_queue != settings().workflow_temporal_task_queue):
        invalid('goal_projection_workflow_origin_invalid')
    if type(data) is dict and type(data.get('state')) is dict and data['state'].get('iteration') == 1:
        from .first_projection import project_first
        return await project_first(data, info.workflow_id)
    return await project_pre_child(data, info.workflow_id)
