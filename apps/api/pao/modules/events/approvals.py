"""Unified read adapters; domain state and execution authorization remain authoritative."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import jwt
from fastapi import HTTPException
from sqlalchemy import select
from ...config import settings
from ...models import Task, ToolCall, AdAction, Run, ChatSession, MetaConnection, AdsAutopilotPolicy, now
from .producer import checksum

MODELS = {'task': Task, 'tool': ToolCall, 'ads': AdAction}


def serial(value):
    if isinstance(value, (date, datetime, time)): return value.isoformat()
    if isinstance(value, Decimal): return str(value)
    if isinstance(value, dict): return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)): return [serial(item) for item in value]
    return value


def record(row):
    return serial({column.key: getattr(row, column.key) for column in row.__table__.columns})


async def input_hash(db, kind, row):
    context = {}
    if kind == 'task':
        dependencies = list(await db.scalars(select(Task).where(Task.id.in_(row.dependencies or []),
            Task.workspace_id == row.workspace_id).order_by(Task.id)))
        context = {'dependencies': [{'id': dep.id, 'version': dep.version, 'status': dep.status} for dep in dependencies]}
    elif kind == 'tool':
        run = await db.get(Run, row.run_id)
        chat = await db.get(ChatSession, run.session_id) if run else None
        context = {'run': record(run) if run else None, 'session_user': chat.user_id if chat else None,
                   'tools_enabled': settings().tools_enabled}
    elif kind == 'ads':
        conn = await db.get(MetaConnection, row.connection_id)
        policy = await db.get(AdsAutopilotPolicy, row.policy_id) if row.policy_id else None
        # Never include tokens/credential ciphertext in the ticket hash input.
        context = {'connection': {'id': conn.id, 'version': conn.version, 'status': conn.status,
                    'scopes': conn.scopes} if conn else None,
                   'policy': record(policy) if policy else None,
                   'meta_write_enabled': settings().meta_write_enabled,
                   'autopilot_enabled': settings().ads_autopilot_global_enabled}
    return checksum({'kind': kind, 'subject': record(row), 'context': context})


def expires(kind, row):
    return row.approval_expires_at if kind == 'ads' else (
        row.updated_at if kind == 'task' else row.created_at) + timedelta(hours=24)


def pending(kind, row):
    return row.status == 'waiting_approval' if kind == 'task' else row.status == 'pending' if kind == 'tool' else (
        row.approval_status == 'pending' and row.execution_status == 'pending')


async def item(db, kind, row, who, role):
    expiry = expires(kind, row)
    capable = role != 'viewer' if kind == 'task' else (
        row.user_id == who.id and role in ('owner', 'admin', 'operator') and settings().tools_enabled) if kind == 'tool' else role in ('owner', 'admin')
    # Non-dry-run Ads cannot be approved while live writes are disabled.
    if kind == 'ads' and not row.dry_run and not settings().meta_write_enabled: capable = False
    digest = await input_hash(db, kind, row)
    claims = {'iss': 'pao-approval', 'aud': 'pao-approval-decision', 'sub': who.id,
              'workspace_id': row.workspace_id, 'kind': kind, 'subject_id': row.id,
              'version': row.version, 'input_hash': digest, 'exp': int(expiry.timestamp()),
              'iat': int(now().timestamp())}
    return {'id': row.id, 'kind': kind, 'workspace_id': row.workspace_id,
            'title': row.title if kind == 'task' else row.name if kind == 'tool' else f'{row.action_type} {row.resource_id}',
            'version': row.version, 'input_hash': digest, 'expires_at': expiry,
            'can_decide': capable and pending(kind, row) and expiry > now(),
            'ticket': jwt.encode(claims, settings().jwt_secret, algorithm='HS256'),
            'dry_run': row.dry_run if kind == 'ads' else None,
            'review': {'criteria':row.success_criteria,'evidence':row.evidence,'result_reference':row.result_reference} if kind=='task' else
                {'name':row.name,'arguments':row.arguments} if kind=='tool' else
                {'account_id':row.account_id,'before':row.before_state,'proposed':row.proposed_state,'reason':row.reason,'dry_run':row.dry_run}}


def ticket(value, who):
    try:
        claims = jwt.decode(value, settings().jwt_secret, algorithms=['HS256'],
            issuer='pao-approval', audience='pao-approval-decision',
            options={'require': ['sub', 'exp', 'iat', 'workspace_id', 'kind', 'subject_id', 'version', 'input_hash']})
        if claims['sub'] != who.id or claims['kind'] not in MODELS: raise ValueError()
        return claims
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(409, 'approval_snapshot_invalid_or_expired') from None


async def require_snapshot(db, kind, row, expected_hash):
    if expected_hash and await input_hash(db, kind, row) != expected_hash:
        raise HTTPException(409, 'approval_input_changed')
