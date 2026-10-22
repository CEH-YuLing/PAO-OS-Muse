"""Native connection pins and durable dispatch admission; no credential handling."""
from sqlalchemy import select
from ...config import settings
from ...db import Session
from ...models import CliModelConnection, CliModelDispatch, LlmAttempt, TenantModelLease, ChatSession, Run, now
from ..connections import resources
from ..engines.contract import EngineFailure
from ..engines.service import digest

VERSION = 'p84-cli-pin-v1'


def pin(row):
    from .runtime import host_digest
    return {'version': VERSION, 'connection_id': row.id, 'workspace_id': row.workspace_id,
            'actor_id': row.owner_id, 'provider': row.provider, 'device_id': row.device_id,
            'profile_id': row.profile_id, 'source_version': row.version, 'model': row.model,
            'binary_sha256': row.binary_sha256, 'binary_version': row.binary_version,
            'runtime_image_id': row.runtime_image_id,
            'host_runtime_sha256': host_digest(),
            'auth_checked_at': row.auth_checked_at.isoformat() if row.auth_checked_at else None}


async def source(db, workspace, actor, connection, model=None):
    from .runtime import configured_device
    if not settings().cli_connections_enabled:
        raise EngineFailure('cli_connections_disabled')
    row = await db.scalar(select(CliModelConnection).where(CliModelConnection.id == connection,
        CliModelConnection.workspace_id == workspace, CliModelConnection.owner_id == actor)
        .execution_options(populate_existing=True))
    if (not row or row.setup_operation_id is not None or row.status != 'connected' or not row.auth_checked_at or not row.binary_sha256 or not row.runtime_image_id
            or row.device_id != configured_device() or row.provider != 'codex_cli'
            or (model is not None and row.model != model)):
        raise EngineFailure('cli_connection_unavailable')
    return row


async def check_source(db, workspace, value):
    selected = value.get('cli_pin')
    authority = value.get('connection_authority')
    if (not isinstance(selected, dict) or not isinstance(authority, dict)
            or authority.get('mode') not in ('model_grant','personal_cli') or authority.get('source_kind') != 'cli_model'
            or value.get('provider') != 'codex_cli'):
        raise EngineFailure('engine_snapshot_incompatible')
    if value.get('cli_model_catalog') is not None:
        if authority.get('mode') != 'personal_cli':
            raise EngineFailure('engine_snapshot_incompatible')
        row = await source(db,workspace,authority.get('actor_id'),value.get('connection_id'))
        from .model_catalog import check
        await check(db,workspace,authority.get('actor_id'),pin(row),value)
    else:
        row = await source(db, workspace, authority.get('actor_id'), value.get('connection_id'), value.get('model'))
        if selected != pin(row):
            raise EngineFailure('cli_connection_changed')


async def current(db, run_id, attempt_id):
    from ..engines.service import checked_snapshot
    from ..connections.model_fence import check_run
    run = await db.scalar(select(Run).where(Run.id == run_id).execution_options(populate_existing=True))
    if not run or run.status != 'running' or run.cancel_requested:
        raise EngineFailure('engine_run_not_active')
    value = checked_snapshot(run.engine_snapshot)
    if value['provider'] != 'codex_cli':
        raise EngineFailure('engine_snapshot_incompatible')
    await check_run(db, run)
    chat = await db.get(ChatSession, run.session_id, populate_existing=True)
    from ..chat.policy import enforce, run_policy, policy_for
    enforce('codex_cli', run_policy(run), policy_for(chat))
    attempt = await db.scalar(select(LlmAttempt).where(LlmAttempt.id == attempt_id,
        LlmAttempt.workspace_id == run.workspace_id, LlmAttempt.run_id == run.id,
        LlmAttempt.session_id == run.session_id, LlmAttempt.user_id == chat.user_id,
        LlmAttempt.provider == 'codex_cli', LlmAttempt.model == value['model'], LlmAttempt.status == 'started'))
    lease = await db.scalar(select(TenantModelLease.id).where(TenantModelLease.attempt_id == attempt_id,
        TenantModelLease.workspace_id == run.workspace_id, TenantModelLease.actor_id == chat.user_id,
        TenantModelLease.kind == 'llm', TenantModelLease.status == 'active', TenantModelLease.expires_at > now()))
    if not attempt or not lease:
        raise EngineFailure('tenant_resource_accounting_required')
    return run, value


async def claim(run_id, attempt_id):
    # Native resource lock -> source -> dispatch; no I/O or transaction over child.
    async with Session.begin() as db:
        workspace = await db.scalar(select(Run.workspace_id).where(Run.id == run_id))
        if workspace is None:
            raise EngineFailure('engine_run_not_active')
        await resources.lock(db, workspace)
        run, value = await current(db, run_id, attempt_id)
        connection = await db.scalar(select(CliModelConnection).where(CliModelConnection.id == value['connection_id'],
            CliModelConnection.workspace_id == workspace).with_for_update())
        if await db.scalar(select(CliModelDispatch.id).where(CliModelDispatch.attempt_id == attempt_id)):
            raise EngineFailure('cli_attempt_already_dispatched')
        if await db.scalar(select(CliModelDispatch.id).where(CliModelDispatch.connection_id == connection.id,
                CliModelDispatch.status.in_(('dispatched','unknown')))):
            raise EngineFailure('cli_profile_busy')
        row = CliModelDispatch(workspace_id=workspace, connection_id=connection.id,
                               attempt_id=attempt_id, status='dispatched')
        db.add(row)
        await db.flush()
        return row.id, value['cli_pin']


async def finish(dispatch_id, state, *, cleanup_verified):
    # Unknown cleanup keeps the unique profile fence. Never infer exactly-once
    # inference from a process receipt or refund/replay an uncertain attempt.
    if state not in ('completed','failed','cancelled') or type(cleanup_verified) is not bool:
        raise EngineFailure('cli_dispatch_state_invalid')
    async with Session.begin() as db:
        row = await db.scalar(select(CliModelDispatch).where(CliModelDispatch.id == dispatch_id).with_for_update())
        if row is None or row.status != 'dispatched':
            return
        row.status = state if cleanup_verified else 'unknown'
        row.finished_at = now()
