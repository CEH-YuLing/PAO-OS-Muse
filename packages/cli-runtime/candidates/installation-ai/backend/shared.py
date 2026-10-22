"""Candidate-only shared CLI boundary. Never imports host authentication caches.

The admission function intentionally has no production success path yet. Tests
replace only that provider-identity boundary, not ACL, accounting or dispatch.
"""
from sqlalchemy import select
from pao.models import CliModelConnection
from pao.modules.engines.contract import EngineFailure


async def admit(db, resource):
    raise EngineFailure('installation_ai_cli_adapter_pending')


async def source_pin(db, resource):
    from .service import source, pin
    row = await source(db, resource.source_workspace_id, resource.owner_id, resource.source_id)
    return pin(row)


async def check_source(db, workspace, value):
    from ..installation_ai.service import config
    authority = value.get('connection_authority') or {}
    current = await config(db, workspace, authority.get('actor_id'), authority.get('brand_id'),
        authority.get('resource_id'), value.get('model'), value.get('reasoning_effort'))
    if any(current.get(key) != value.get(key) for key in current):
        raise EngineFailure('installation_ai_selection_changed')


async def connection(db, workspace, value):
    # The caller SME stays on Run/Attempt/Lease/Dispatch. The transport pin stays
    # on the installation source custodian; never rewrite a Docker volume label.
    await check_source(db, workspace, value)
    selected = value['cli_pin']
    row = await db.scalar(select(CliModelConnection).where(
        CliModelConnection.id == value['connection_id'],
        CliModelConnection.workspace_id == selected['workspace_id'],
        CliModelConnection.owner_id == selected['actor_id']).with_for_update())
    if row is None:
        raise EngineFailure('cli_connection_unavailable')
    return row


def invocation(value):
    authority = value.get('connection_authority') or {}
    if authority.get('mode') != 'installation_resource':
        # Old personal/grant histories retain their exact old invocation shape.
        if value.get('reasoning_effort') is not None or value['model'] != value['cli_pin']['model']:
            raise EngineFailure('cli_selection_incompatible')
        return {}
    return {'model': value['model'], 'reasoning_effort': value.get('reasoning_effort')}
