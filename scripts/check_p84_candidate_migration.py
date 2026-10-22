"""Verify 0072 in two owned primary clones, never migrate/restore the primary."""
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/api'), str(ROOT / 'scripts')]
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.modules.operations.checkpoint import digest, entries
from check_p11_migration import snapshot
from check_m2_restore import inspect

CONTAINER = 'pao-acos-local-postgres-1'
GUARDS = ('pao_tenant_connection_reference_guard', 'pao_tenant_connection_grant_guard',
          'pao_model_grant_activation_guard')


def docker(*args, **kwargs):
    return subprocess.run(['docker', 'exec', *args], check=True, timeout=120, **kwargs)


async def query(url, sql, params=None):
    engine = create_async_engine(url)
    try:
        async with engine.begin() as db:
            return await db.execute(text(sql), params or {})
    finally:
        await engine.dispose()


async def guards(url):
    return {name: (await query(url, 'SELECT pg_get_functiondef(CAST(:name AS regprocedure))',
            {'name': 'public.' + name + '()'})).scalar_one() for name in GUARDS}


async def main():
    candidate = ROOT / '.runtime/p84-native-candidate-20261018'
    url = make_url(settings().database_url)
    assert ROOT == Path('F:/PAO-ACOS') and candidate.is_dir()
    assert (url.host, url.port, url.database) == ('127.0.0.1', 15432, 'pao_acos_local')
    assert (await query(url, 'SELECT version_num FROM alembic_version')).scalar_one() == '0071'
    original = await snapshot(url)
    original_archives = await inspect(url)
    original_guards = await guards(url)
    source = entries(candidate)
    env_hash = digest(ROOT / '.env')
    folder = ROOT / '.runtime' / ('p84-migration-' + uuid4().hex)
    folder.mkdir()
    dump = folder / 'before.dump'
    with dump.open('xb') as output:
        docker(CONTAINER, 'pg_dump', '-U', 'pao', '-d', url.database, '-Fc', stdout=output)
    assert dump.stat().st_size > 1024
    names = ['pao_p84_migration_' + uuid4().hex, 'pao_p84_restore_' + uuid4().hex]
    created = []
    result = {'pass': False, 'primary_migrated': False, 'primary_restored': False,
              'provider_calls': 0, 'production_accepted': False, 'backup_sha256': digest(dump)}

    def candidate_env(target):
        assert target.database in created
        return {**os.environ, 'PAO_ROOT': str(candidate),
               'DATABASE_URL': target.render_as_string(hide_password=False),
               'JWT_SECRET': 'synthetic-p84-migration-only-not-a-real-secret',
               'REDIS_URL': 'redis://127.0.0.1:1/15',
               'PYTHONPATH': os.pathsep.join((str(candidate / 'apps/api'),
                                             str(candidate / 'packages/cli-runtime'), str(ROOT / 'scripts'))),
               'PYTHONDONTWRITEBYTECODE': '1'}

    def migrate(target, direction, revision, *, failure=False):
        with (folder / 'migration.log').open('ab') as log:
            completed = subprocess.run([sys.executable, '-B', '-m', 'alembic', direction, revision],
                cwd=candidate, env=candidate_env(target), stdout=log, stderr=subprocess.STDOUT, timeout=120)
        assert (completed.returncode != 0) if failure else (completed.returncode == 0)

    try:
        for name in names:
            assert re.fullmatch(r'pao_p84_(migration|restore)_[a-f0-9]{32}', name)
            docker(CONTAINER, 'createdb', '-U', 'pao', name)
            created.append(name)
        clone, restored = (url.set(database=name) for name in names)
        with dump.open('rb') as data:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', names[0],
                   '--no-owner', '--exit-on-error', stdin=data)
        assert await snapshot(clone) == original
        migrate(clone, 'upgrade', '0072')
        assert set((await snapshot(clone))[0]) - set(original[0]) == {
            'cli_model_connections', 'cli_model_dispatches'}
        assert (await snapshot(clone, original[0]))[1] == original[1]
        migrate(clone, 'downgrade', '0071')
        assert await snapshot(clone) == original and await guards(clone) == original_guards
        migrate(clone, 'upgrade', '0072')
        identity = (await query(clone, "SELECT workspace_id,user_id FROM workspace_members WHERE role='owner' ORDER BY workspace_id,user_id LIMIT 1")).one()
        synthetic = {'id': uuid4(), 'wid': identity.workspace_id, 'uid': identity.user_id,
                     'device': uuid4(), 'profile': uuid4(), 'request': uuid4()}
        await query(clone, """INSERT INTO cli_model_connections
            (id,created_at,workspace_id,owner_id,provider,device_id,profile_id,model,request_key,version,status)
            VALUES(:id,now(),:wid,:uid,'codex_cli',:device,:profile,'synthetic-restore-model',:request,1,'pending')""", synthetic)
        populated = await snapshot(clone)
        migrate(clone, 'downgrade', '0071', failure=True)
        assert await snapshot(clone) == populated
        assert (await query(clone, 'SELECT version_num FROM alembic_version')).scalar_one() == '0072'
        saved = folder / 'populated.dump'
        with saved.open('xb') as output:
            docker(CONTAINER, 'pg_dump', '-U', 'pao', '-d', names[0], '-Fc', stdout=output)
        with saved.open('rb') as data:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', names[1],
                   '--no-owner', '--exit-on-error', stdin=data)
        assert await snapshot(restored) == populated and await guards(restored) == await guards(clone)
        triggers = (await query(restored, "SELECT count(*) FROM pg_trigger WHERE tgname='cli_dispatch_guard' AND NOT tgisinternal")).scalar_one()
        assert triggers == 1
        try:
            await query(restored, "UPDATE cli_model_connections SET status='connected'")
        except DBAPIError:
            pass
        else:
            raise AssertionError('Restored connection accepted connected without auth metadata')
        replay = await inspect(restored)
        assert replay['artifact_hashes'] == original_archives['artifact_hashes'] and len(replay['artifact_hashes']) == 3
        candidate_reader = subprocess.run([sys.executable, '-B', '-c',
            'import asyncio,json; from check_m2_restore import inspect; '
            'from sqlalchemy.engine import make_url; from pao.config import settings; '
            'print(json.dumps(asyncio.run(inspect(make_url(settings().database_url)))))'],
            cwd=candidate, env=candidate_env(restored), capture_output=True, check=True, timeout=60)
        (folder / 'candidate-reader.log').write_bytes(candidate_reader.stdout)
        assert json.loads(candidate_reader.stdout)['artifact_hashes'] == original_archives['artifact_hashes']
        assert (await snapshot(restored, original[0]))[1] == original[1]
        result.update(roundtrip='0071-0072-0071-0072', old_rows_exact=True,
            old_guard_functions_exact_after_downgrade=True, populated_downgrade_refused=True,
            populated_restore_exact=True, historical_archive_reads=3,
            candidate_reader_historical_archive_reads=3,
            restored_constraints_and_dispatch_trigger=True,
            primary_unchanged=(await snapshot(url) == original and await guards(url) == original_guards),
            env_unchanged=digest(ROOT / '.env') == env_hash,
            candidate_unchanged=entries(candidate) == source)
        result['pass'] = all(result[k] for k in ('primary_unchanged', 'env_unchanged', 'candidate_unchanged'))
    finally:
        removed = []
        for name in reversed(created):
            assert name in names and re.fullmatch(r'pao_p84_(migration|restore)_[a-f0-9]{32}', name)
            # No --force: never terminate an unexpected client to clean a fixture.
            docker(CONTAINER, 'dropdb', '-U', 'pao', name)
            removed.append(name)
        result['owned_clones_removed'] = len(removed) == len(created)
        (folder / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(folder)
        print(json.dumps(result))
    if not result['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    from local_cycle_test_lock import isolated_test_slot
    with isolated_test_slot():
        asyncio.run(main())
