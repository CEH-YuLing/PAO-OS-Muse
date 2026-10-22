"""Build an isolated backend/transport candidate, never edit serving files.

Exact-count transformations fail on source drift. There is no --install mode.
The private test runner is the only consumer; its provider identity is synthetic.
"""
from pathlib import Path
import hashlib
import shutil

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / 'packages/cli-runtime/candidates/installation-ai'


def replace(path, old, new):
    value = path.read_text(encoding='utf-8')
    if value.count(old) != 1:
        raise RuntimeError('candidate_source_drift:' + path.name)
    path.write_text(value.replace(old, new, 1), encoding='utf-8', newline='\n')


def stage(folder):
    folder = folder.resolve()
    if not folder.is_relative_to(ROOT / '.runtime') or folder.exists():
        raise RuntimeError('candidate_new_runtime_directory_required')
    folder.mkdir(parents=True)
    api = folder / 'apps/api'
    api.mkdir(parents=True)
    for name in ('pao', 'migrations', 'tests'):
        shutil.copytree(ROOT / 'apps/api' / name, api / name,
            ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc'))
    library = folder / 'packages/cli-runtime/pao_cli_runtime'
    shutil.copytree(ROOT / 'packages/cli-runtime/pao_cli_runtime', library,
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for file in (CANDIDATE / 'pao_cli_runtime').glob('*.py'):
        shutil.copyfile(file, library / file.name)
    for name in ('skill-config','agent-config'):
        shutil.copytree(ROOT / 'packages' / name, folder / 'packages' / name,
            ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(ROOT / 'alembic.ini', folder / 'alembic.ini')
    shutil.copyfile(ROOT / 'pyproject.toml', folder / 'pyproject.toml')
    cli = api / 'pao/modules/cli_connections'
    shutil.copyfile(CANDIDATE / 'backend/shared.py', cli / 'shared.py')
    common = api / 'pao/modules/installation_ai/service.py'
    replace(common,
        "        # No currently implemented shared CLI adapter passes provider identity,\n"
        "        # dispatch isolation and tool-free gates. Do not relabel a personal pin.\n"
        "        raise EngineFailure('installation_ai_cli_adapter_pending')",
        "        from ..cli_connections.shared import admit\n        await admit(db, row)")
    replace(common,
        "    return {'provider': row.provider, **chosen, 'connection_id': row.source_id, 'connection_authority': authority}",
        "    value = {'provider': row.provider, **chosen, 'connection_id': row.source_id, 'connection_authority': authority}\n"
        "    if row.source_kind == 'cli':\n        from ..cli_connections.shared import source_pin\n"
        "        value['cli_pin'] = await source_pin(db, row)\n    return value")
    replace(api / 'pao/modules/installation_ai/api.py',
        "        if row.source_kind=='cli':raise HTTPException(409,'installation_ai_cli_adapter_pending')",
        "        if row.source_kind=='cli':\n            from ..cli_connections.shared import admit\n"
        "            try:await admit(db,row)\n"
        "            except EngineFailure as exc:raise HTTPException(409,exc.code) from None")
    replace(api / 'pao/modules/engines/service.py',
        "    elif provider == 'codex_cli':\n        if (value.get('connection_authority') or {}).get('mode') == 'personal_cli':",
        "    elif provider == 'codex_cli':\n        if (value.get('connection_authority') or {}).get('mode') == 'installation_resource':\n"
        "            from ..installation_ai.service import check\n"
        "        elif (value.get('connection_authority') or {}).get('mode') == 'personal_cli':")
    replace(cli / 'service.py',
        "    selected = value.get('cli_pin')\n    authority = value.get('connection_authority')",
        "    if (value.get('connection_authority') or {}).get('mode') == 'installation_resource':\n"
        "        from .shared import check_source as common_source\n        return await common_source(db, workspace, value)\n"
        "    selected = value.get('cli_pin')\n    authority = value.get('connection_authority')")
    replace(cli / 'service.py',
        "        connection = await db.scalar(select(CliModelConnection).where(CliModelConnection.id == value['connection_id'],\n"
        "            CliModelConnection.workspace_id == workspace).with_for_update())",
        "        if (value.get('connection_authority') or {}).get('mode') == 'installation_resource':\n"
        "            from .shared import connection as common_connection\n            connection = await common_connection(db, workspace, value)\n"
        "        else:\n            connection = await db.scalar(select(CliModelConnection).where(CliModelConnection.id == value['connection_id'],\n"
        "                CliModelConnection.workspace_id == workspace).with_for_update())")
    replace(cli / 'gateway.py',
        "            outcome = await runtime.invoke(pin, attempt, prompt, authorize)",
        "            from .shared import invocation\n"
        "            outcome = await runtime.invoke(pin, attempt, prompt, authorize, **invocation(self.snapshot))")
    replace(cli / 'gateway.py',
        "                if current['cli_pin'] != pin:",
        "                if (current['cli_pin'] != pin or current['model'] != self.snapshot['model']\n"
        "                        or current.get('reasoning_effort') != self.snapshot.get('reasoning_effort')\n"
        "                        or current.get('connection_authority') != self.snapshot.get('connection_authority')):")
    replace(api / 'pao/models.py',
        "        ForeignKeyConstraint(['connection_id','workspace_id'], ['cli_model_connections.id','cli_model_connections.workspace_id']),",
        "        ForeignKeyConstraint(['connection_id'], ['cli_model_connections.id']),")
    shutil.copyfile(CANDIDATE / 'backend/0076_candidate_cli_selection.py', api / 'migrations/versions/0076_candidate_cli_selection.py')
    shutil.copyfile(CANDIDATE / 'backend/test_shared_cli_candidate.py', api / 'tests/test_shared_cli_candidate.py')
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for root in (api / 'pao', api / 'migrations', library)
        for p in sorted(root.rglob('*.py'))}
