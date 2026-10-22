"""Narrow GitHub Linux test-only profile; never permits primary schema rollout."""
from pathlib import Path
import re
import sys


def service_container(root, url, env, *, populated, manifest, platform=None):
    platform = sys.platform if platform is None else platform
    if (platform != 'linux' or env.get('PAO_CI_RESTORE') != '1'
            or env.get('GITHUB_ACTIONS') != 'true' or not populated or manifest):
        raise ValueError('ci_restore_test_only')
    workspace = env.get('GITHUB_WORKSPACE')
    if not workspace or Path(workspace).resolve() != Path(root).resolve():
        raise ValueError('ci_workspace_mismatch')
    if (url.drivername != 'postgresql+asyncpg' or url.host != '127.0.0.1'
            or url.port != 5432 or url.database != 'pao_test' or url.username != 'pao'):
        raise ValueError('ci_test_database_required')
    container = env.get('PAO_CI_RESTORE_CONTAINER', '')
    if not re.fullmatch(r'[0-9a-f]{64}', container):
        raise ValueError('ci_service_container_id_required')
    return container
