"""Serial candidate-only PostgreSQL tests; preserve primary source/env/schema."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from xml.etree import ElementTree
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
sys.path.insert(0, str(ROOT / 'scripts'))
from check_p84_foundation import binding, protected, primary_schema
from pao.config import settings
from pao.modules.operations.checkpoint import entries


def serving_source():
    # Generated Next caches change on normal application startup. Keep all
    # actual app/config/lock files protected; do not compare generated bundles
    # as if they were source, and never rewrite the earlier failed receipt.
    return {name: value for name, value in protected().items()
            if not any(part in ('.pao-next', '.pao-build-check') for part in Path(name).parts)}


def main():
    candidate = ROOT / '.runtime/p84-native-candidate-20261018'
    if ROOT != Path('F:/PAO-ACOS') or not candidate.is_dir():
        raise SystemExit('p84_candidate_scope_denied')
    cfg = settings()
    if not cfg.database_url.endswith(':15432/pao_acos_local'):
        raise SystemExit('p84_primary_scope_denied')
    before = {'binding': binding(), 'protected': serving_source(), 'schema': asyncio.run(primary_schema())}
    folder = ROOT / '.runtime' / ('p84-native-tests-' + uuid4().hex)
    folder.mkdir()
    (folder / 'primary-before.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    # Mechanical copy of this turn's independent runtime, never credentials.
    for path in (ROOT / 'packages/cli-runtime/pao_cli_runtime').glob('*.py'):
        target = candidate / 'packages/cli-runtime/pao_cli_runtime' / path.name
        shutil.copyfile(path, target)
    shutil.copyfile(ROOT / 'scripts/windows_candidate_restore.py', candidate / 'scripts/windows_candidate_restore.py')
    source = entries(candidate)
    url = cfg.database_url.rsplit('/', 1)[0] + '/pao_test'
    env = {**os.environ, 'PAO_ROOT': str(candidate), 'DATABASE_URL': url, 'PAO_TEST_DATABASE_URL': url,
           'REDIS_URL': urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
           'PYTHONPATH': os.pathsep.join(map(str, (ROOT / '.runtime/p84-native-test-deps', candidate / 'apps/api',
                                                   candidate / 'packages/cli-runtime', ROOT / 'scripts'))),
           'JWT_SECRET': 'synthetic-p84-' + secrets.token_hex(24),
           'INTEGRATION_ENCRYPTION_KEY': Fernet.generate_key().decode(), 'PYTHONDONTWRITEBYTECODE': '1'}
    container = subprocess.check_output(['docker', 'inspect', 'pao-acos-local-postgres-1', '--format', '{{.Id}}'], timeout=15).decode().strip()
    if len(container) != 64 or any(c not in '0123456789abcdef' for c in container):
        raise SystemExit('p84_test_container_identity_invalid')
    env.update(PAO_WINDOWS_CANDIDATE_RESTORE='1', PAO_WINDOWS_CANDIDATE_PG_CONTAINER=container)
    if '--reset-test-schema' in sys.argv:
        # Only the disposable literal pao_test, under the shared operator lock.
        # No --force: refuse instead of terminating an unexpected DB client.
        for command in (['dropdb','-U','pao','--if-exists','pao_test'], ['createdb','-U','pao','pao_test']):
            subprocess.run(['docker','exec','pao-acos-local-postgres-1',*command], check=True,
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    # Regenerate the additive candidate API contract before freezing test input.
    if '--full' in sys.argv:
        subprocess.run([sys.executable, '-B', 'scripts/export_openapi.py'], cwd=candidate, env=env,
                       check=True, capture_output=True, timeout=30)
        cache_dir = candidate / '.runtime/p62-temporal-bootstrap'
        cache_dir.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(ROOT / 'apps/api/tests'))
        from temporal_fixture import cached_binary
        cached = Path(cached_binary(ROOT))
        shutil.copyfile(cached, cache_dir / cached.name)
        env['PAO_ARQ_WALL_CLOCK_TESTS'] = '1'
        source = entries(candidate)
    with (folder / 'migration.log').open('wb') as output:
        migration = subprocess.run([sys.executable, '-B', '-m', 'alembic', 'upgrade', '0072'], cwd=candidate,
            env=env, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    if migration.returncode:
        print(folder)
        raise SystemExit('p84_test_migration_failed')
    files = ['test_cli_connections.py']
    if '--focused' in sys.argv:
        files += ['test_connection_inventory.py', 'test_connection_grants.py', 'test_connection_generations.py',
                  'test_model_connection_fence.py', 'test_engine_contract.py', 'test_chat_management.py', 'test_p7_restore.py']
    files = [str(candidate / 'apps/api/tests' / name) for name in files]
    if '--full' in sys.argv:
        files = [str(candidate / 'apps/api/tests')]
    if any(not Path(path).exists() for path in files):
        raise SystemExit('p84_test_file_missing')
    with (folder / 'pytest.log').open('wb') as output:
        result = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '--maxfail=1', '-p', 'local_cycle_network_guard',
            *files, '--junitxml=' + str(folder / 'junit.xml')], cwd=candidate, env=env,
            stdout=output, stderr=subprocess.STDOUT, timeout=5400 if '--full' in sys.argv else 1200)
    counts = {key: 0 for key in ('tests','failures','errors','skipped')}
    if (folder / 'junit.xml').exists():
        for suite in ElementTree.parse(folder / 'junit.xml').getroot().iter('testsuite'):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
    after = {'binding': binding(), 'protected': serving_source(), 'schema': asyncio.run(primary_schema())}
    state = {**counts, 'primary_source_env_schema_unchanged': before == after,
        'candidate_source_unchanged': source == entries(candidate), 'full_backend_regression': '--full' in sys.argv,
        'primary_content_hashes_measured': False, 'primary_migrated': False, 'candidate_schema': '0072',
        'provider_calls': 0, 'hosted_CI': False, 'candidate_source': source}
    state['generated_cache_paths_excluded'] = ['apps/web/.pao-next', 'apps/web/.pao-build-check']
    state['pass'] = (result.returncode == 0 and counts['tests'] > 0
        and not any(counts[k] for k in ('failures','errors','skipped')) and before == after and source == entries(candidate))
    (folder / 'receipt.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    print(folder)
    print(json.dumps({k:v for k,v in state.items() if k != 'candidate_source'}))
    raise SystemExit(0 if state['pass'] else 1)


if __name__ == '__main__':
    from local_cycle_test_lock import isolated_test_slot
    with isolated_test_slot():
        main()
