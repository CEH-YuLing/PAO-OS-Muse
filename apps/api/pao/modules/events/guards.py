"""Freeze execution-affecting inputs without including mutable status/version."""
from .producer import checksum


def execution_hash(kind, row):
    keys = ('workspace_id', 'run_id', 'user_id', 'name', 'agent_key', 'arguments', 'connector_snapshot') if kind == 'tool' else (
        'workspace_id', 'connection_id', 'connection_version', 'user_id', 'account_id', 'resource_type',
        'resource_id', 'action_type', 'before_state', 'proposed_state', 'dry_run', 'policy_id', 'policy_version', 'policy_snapshot')
    return checksum({key: getattr(row, key) for key in keys})


def tool_fingerprint(row):
    import hashlib
    import json
    return hashlib.sha256(json.dumps({'name': row.name, 'agent': row.agent_key, 'arguments': row.arguments},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
