"""Bounded install snapshot/read-only contract+archive checks, not owner consent."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/api'), str(ROOT / 'packages/cli-runtime'), str(ROOT / 'scripts')]
import httpx
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from pao.config import settings
from pao.db import Session, engine
from pao.models import Member, User
from pao.auth import issue_token
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest, entries
from check_p11_migration import snapshot
from check_m2_restore import inspect


async def main(args):
    cfg = settings()
    url = make_url(cfg.database_url)
    folder = args.install_folder
    assert ROOT == Path('F:/PAO-ACOS') and folder.parent == ROOT / '.runtime'
    assert folder.name.startswith('p84-native-install-') and str(UUID(folder.name[19:])).replace('-', '') == folder.name[19:]
    assert folder.is_dir() and not folder.is_symlink() and not folder.is_junction()
    assert (url.host, url.port, url.database) == ('127.0.0.1', 15432, 'pao_acos_local')
    before_path = folder / 'database-before.json'
    if args.action == 'before':
        value = {'snapshot': await snapshot(url), 'archives': await inspect(url),
                 'env_sha256': digest(ROOT / '.env'), 'binding': execution_binding(),
                 'runtime_pin_sha256': digest(ROOT / '.runtime/acos-python-runtime.json'),
                 'requirements_sha256': digest(ROOT / 'requirements.lock')}
        assert value['archives']['revision'] == '0071' and len(value['archives']['counts']) == 153
        assert len(value['archives']['artifact_hashes']) == 3
        with before_path.open('x', encoding='utf-8') as output:
            json.dump(value, output, indent=2)
        print('before_snapshot_saved_without_primary_writes')
        return
    original = json.loads(before_path.read_text(encoding='utf-8'))
    intent = json.loads((folder / 'install-intent.json').read_text(encoding='utf-8'))
    plan = json.loads((folder / 'source-plan.json').read_text(encoding='utf-8'))
    assert plan['source_plan_ready'] and not plan['primary_installed']
    current = entries(ROOT)
    for name, hashed in plan['candidate_source'].items():
        if name.startswith(('apps/api/', 'packages/cli-runtime/pao_cli_runtime/')):
            assert current.get(name) == hashed, 'Installed tested source differs: ' + name
    for name, change in plan['changes'].items():
        assert digest(ROOT / name) == change['after']
    derived = plan['derived_contract']
    assert derived['target'] == 'packages/contracts/schema.d.ts' and digest(ROOT / derived['target']) == derived['after']
    assert digest(ROOT / '.env') == intent['env_after_sha256']
    assert digest(ROOT / '.runtime/acos-python-runtime.json') == original['runtime_pin_sha256']
    assert digest(ROOT / 'requirements.lock') == original['requirements_sha256']
    assert cfg.cli_connections_enabled
    assert not any(getattr(cfg, key) for key in ('meta_enabled', 'google_ads_enabled', 'meta_write_enabled',
        'meta_autopilot_enabled', 'ads_autopilot_global_enabled', 'telegram_enabled', 'telegram_scoped_runtime_enabled'))
    from pao.modules.cli_connections.runtime import device_config
    device = device_config()
    assert device == intent['device_registry']
    old_columns, old_hashes = original['snapshot']
    assert (await snapshot(url, old_columns))[1] == old_hashes
    whole = await snapshot(url)
    assert set(whole[0]) - set(old_columns) == {'cli_model_connections', 'cli_model_dispatches'}
    assert all(whole[1][name]['count'] == 0 for name in ('cli_model_connections', 'cli_model_dispatches'))
    archives = await inspect(url)
    assert archives['revision'] == '0072' and len(archives['counts']) == 155
    assert archives['artifact_hashes'] == original['archives']['artifact_hashes']
    saved = json.loads((ROOT / 'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    operations = sum(k in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
                     for methods in saved['paths'].values() for k in methods)
    assert operations == 412
    replays = 0
    seen_attempts = set()
    async with Session() as db, httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=30) as client:
        assert (await client.get('/openapi.json')).json() == saved
        for path in ('/health', '/ready'):
            assert (await client.get(path)).status_code == 200
        assert (await client.get('/v1/workspaces/' + intent['selected_workspace'] + '/cli-connections')).status_code == 401
        # Internal diagnostic bearer is read-only here: no CLI registration,
        # setup, grant, model execution or representation of owner consent.
        for member in await db.scalars(select(Member).join(User, User.id == Member.user_id)
                                       .where(Member.role == 'owner', User.active.is_(True))):
            user = await db.get(User, member.user_id)
            headers = {'Authorization': 'Bearer ' + issue_token(user.id, user.auth_version)}
            runs = await db.execute(text("SELECT r.id,r.execution_plan FROM runs r JOIN sessions s ON s.id=r.session_id AND s.workspace_id=r.workspace_id WHERE r.workspace_id=:wid AND s.user_id=:uid AND r.status='completed'"), {'wid': member.workspace_id, 'uid': member.user_id})
            for rid, plan_value in runs:
                artifact = (plan_value or {}).get('skill_artifact')
                if not artifact:
                    continue
                response = await client.get('/v1/runs/' + str(rid) + '/skill-replay', headers=headers)
                assert response.status_code == 200 and response.json()['hash'] == artifact['hash'] and response.json()['tools_reexecuted'] is False
                replays += 1
            attempts = await db.execute(text('SELECT id,task_id,skill_artifact FROM task_attempts WHERE workspace_id=:wid AND skill_artifact IS NOT NULL'), {'wid': member.workspace_id})
            for aid, tid, artifact in attempts:
                if str(aid) in seen_attempts:
                    continue
                response = await client.get('/v1/tasks/' + str(tid) + '/attempts/' + str(aid) + '/skill-replay', headers=headers)
                assert response.status_code == 200 and response.json()['hash'] == artifact['hash'] and response.json()['tools_reexecuted'] is False
                replays += 1
                seen_attempts.add(str(aid))
    assert replays == 3
    async with httpx.AsyncClient(timeout=30) as client:
        assert (await client.get('http://127.0.0.1:3200/')).status_code == 200
    assert (await snapshot(url, old_columns))[1] == old_hashes
    assert digest(ROOT / '.env') == intent['env_after_sha256']
    result = {'pass': True, 'schema': '0072', 'physical_tables': 155, 'operations': operations,
              'binding': execution_binding(), 'old_rows_exact': True, 'historical_archive_reads': 3,
              'read_only_HTTP_replays': replays, 'source_plan_installed_exactly': True,
              'only_intended_env_change': 'CLI_CONNECTIONS_ENABLED=true', 'runtime_pin_unchanged': True,
              'diagnostic_readonly_bearer_only': True, 'CLI_connections': 0, 'CLI_dispatches': 0,
              'real_profile_login': False, 'provider_calls': 0, 'native_PAO_job_test': False,
              'whole_P84_C_accepted': False, 's6_accepted': False, 'production_accepted': False}
    with (folder / 'installed-check.json').open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    print(json.dumps(result))


async def run(args):
    try:
        await main(args)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('before', 'after'))
    parser.add_argument('--install-folder', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args))
