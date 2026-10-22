"""Trusted DB admission pins. No worker registration or receipt API.

Hashes alone are not provenance. Read the server-owned immutable admission,
start command and audit, then reauthorize the actor and the frozen plan.
This boundary does not authorize child execution or prove business success.
"""
from uuid import UUID, uuid5

from ...auth import Principal
from ...models import Goal, GoalCommand, GoalEvent, StudioEvent
from ..studio import durable
from ..studio.contracts import digest
from ..studio.service import reject
from .control import validate


def source_pin(goal):
    value = {k: getattr(goal, k) for k in (
        'id', 'workspace_id', 'project_id', 'owner_id', 'created_by', 'status', 'version')}
    value['content_hash'] = digest({k: getattr(goal, k) for k in (
        'title', 'description', 'success_criteria')})
    value['due_at'] = goal.due_at.isoformat() if goal.due_at else None
    return value


async def verify_admission(db, row):
    """Verify persisted provenance afresh in the caller's locked transaction.

Only the admission actor may own a plan. Current approvers may be other
workspace admins but cannot substitute their own authority for a revoked owner.
No settings gates here: rollback must not block evidence/cancel reconciliation.
"""
    try:
        envelope = row.envelope
        validate(envelope)
        if (envelope['execution_id'] != row.id or envelope['goal_id'] != row.goal_id or
                envelope['workspace_id'] != row.workspace_id or envelope['actor_id'] != row.actor_id or
                envelope['plan_id'] != row.initial_plan_id or row.temporal_id != 'p63-' + row.id):
            raise ValueError()
        if row.admission_hash != digest({'envelope': envelope,
                'initial_proposal': row.initial_proposal, 'goal_snapshot': row.goal_snapshot}):
            raise ValueError()
        admission = await db.get(GoalEvent, str(uuid5(UUID(row.id), 'admission-audit')))
        expected = {'admission_hash': row.admission_hash, 'goal_version': envelope['goal_version']}
        if (not admission or admission.execution_id != row.id or
                admission.workspace_id != row.workspace_id or admission.actor_id != row.actor_id or
                admission.action != 'admitted' or admission.data != expected or
                admission.content_hash != digest({'action': 'admitted', 'data': expected, 'actor_id': row.actor_id})):
            raise ValueError()
        from sqlalchemy import select
        starts = list(await db.scalars(select(GoalCommand).where(
            GoalCommand.execution_id == row.id, GoalCommand.operation == 'start')))
        if len(starts) != 1:
            raise ValueError()
        start = starts[0]
        payload = start.payload
        if set(payload) != {'request_key', 'goal_version', 'proposal', 'policy', 'success_criteria', 'confirmation_hash'}:
            raise ValueError()
        policy = dict(payload['policy'])
        from datetime import datetime
        if row.goal_snapshot['due_at']:
            policy['deadline_unix_ms'] = min(policy['deadline_unix_ms'],
                int(datetime.fromisoformat(row.goal_snapshot['due_at']).timestamp() * 1000))
        if (start.workspace_id != row.workspace_id or start.actor_id != row.actor_id or
                start.ordinal != 1 or start.id != str(uuid5(UUID(row.id), start.request_key)) or
                row.id != str(uuid5(UUID(row.goal_id), start.request_key)) or
                start.content_hash != digest({'operation': 'start', 'payload': payload, 'actor_id': row.actor_id}) or
                payload['confirmation_hash'] != row.admission_hash or
                payload['request_key'] != start.request_key or policy != envelope['policy'] or
                payload['proposal'] != row.initial_proposal or payload['goal_version'] != envelope['goal_version'] or
                payload['success_criteria'] != envelope['success_criteria']):
            raise ValueError()
        command_audit = await db.get(GoalEvent, str(uuid5(UUID(start.id), 'audit')))
        command_data = {'command_id': start.id, 'operation': 'start', 'ordinal': 1}
        if (not command_audit or command_audit.execution_id != row.id or
                command_audit.workspace_id != row.workspace_id or command_audit.actor_id != row.actor_id or
                command_audit.action != 'command' or command_audit.data != command_data or
                command_audit.content_hash != digest({'action': 'command', 'data': command_data, 'actor_id': row.actor_id})):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        reject('goal_admission_evidence_invalid', 409)
    goal = await db.get(Goal, row.goal_id)
    if not goal or source_pin(goal) != row.goal_snapshot:
        reject('goal_source_pin_changed', 409)
    await durable.authorize(db, row, Principal(row.actor_id, 0))
    snapshot = await durable.verify_plan(db, await db.get(StudioEvent, row.initial_plan_id), row.actor_id)
    if snapshot['sha256'] != envelope['snapshot_hash']:
        reject('goal_initial_plan_pin_changed', 409)
    return snapshot
