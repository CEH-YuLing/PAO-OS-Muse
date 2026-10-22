"""Serial disposable-DB acceptance for the separate local MCP bridge.

No migration/reset, serving restart, Google CLI, provider or primary mutation.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'apps/api')]
from local_cycle_test_lock import isolated_test_slot
from check_p84_foundation import primary_schema, health
from pao.config import settings


def digests():
    files = [ROOT / name for name in ('.env', 'pyproject.toml', 'requirements.lock',
             '.runtime/acos-python-runtime.json', '.runtime/cli-device.json')]
    files += list((ROOT / 'apps/api/pao').rglob('*.py'))
    files += list((ROOT / 'packages/cli-runtime/pao_cli_runtime').glob('*.py'))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def source():
    files = list((ROOT / 'packages/pao-mcp').rglob('*.py'))
    files += [ROOT / name for name in ('scripts/pao_mcp.py', 'scripts/open_pao_mcp_setup.ps1',
              'scripts/check_pao_mcp_local.py', 'apps/api/tests/test_mcp_readonly_bridge.py')]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    assert ROOT == Path('F:/PAO-ACOS')
    cfg = settings()
    pg = urlsplit(cfg.database_url)
    assert pg.hostname == '127.0.0.1' and pg.port == 15432 and pg.path == '/pao_acos_local'
    folder = ROOT / '.runtime' / ('pao-mcp-local-' + uuid4().hex)
    folder.mkdir()
    before = digests(); candidate = source()
    schema = asyncio.run(primary_schema())
    state = {'pass': False, 'scope': 'PAO_readonly_MCP_local', 'provider_calls': 0,
             'Google_auth_access': False, 'Antigravity_model_acceptance': False,
             'native_Antigravity_MCP_handshake': False, 'full_backend_regression': False,
             'primary_schema_before': schema, 'source': candidate, 'protected_before': before}
    try:
        bootstrap = """import json,sys,unittest
suite=unittest.defaultTestLoader.discover('packages/pao-mcp/tests')
result=unittest.TextTestRunner(verbosity=2).run(suite)
print('MCP_UNIT_COUNTS='+json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}))
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
"""
        with (folder / 'unit.log').open('wb') as log:
            unit = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap], cwd=ROOT,
                                  stdout=log, stderr=subprocess.STDOUT, timeout=90)
        lines = (folder / 'unit.log').read_text(encoding='utf-8').splitlines()
        counts = [json.loads(v.split('=', 1)[1]) for v in lines if v.startswith('MCP_UNIT_COUNTS=')]
        assert unit.returncode == 0 and len(counts) == 1
        state['unit'] = counts[0]
        test_url = urlunsplit(pg._replace(path='/pao_test'))
        env = {**os.environ, 'PAO_TEST_DATABASE_URL': test_url, 'DATABASE_URL': test_url,
               'REDIS_URL': urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
               'JWT_SECRET': 'synthetic-mcp-' + secrets.token_hex(24),
               'PYTHONPATH': os.pathsep.join((str(ROOT / '.runtime/p84-native-test-deps'),
                   str(ROOT / 'apps/api'), str(ROOT / 'packages/cli-runtime'), str(ROOT / 'scripts'))),
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'}
        # conftest enforces pao_test, preserves schema, and uses real auth/ACL.
        with (folder / 'integration.log').open('wb') as log:
            run = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '--maxfail=1',
                '-p', 'local_cycle_network_guard', 'apps/api/tests/test_mcp_readonly_bridge.py',
                '--junitxml=' + str(folder / 'junit.xml')], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT, timeout=240)
        state['integration_exit_code'] = run.returncode
        assert (folder / 'junit.xml').is_file(), 'Test process did not produce JUnit; see preserved integration.log'
        counts = {k: 0 for k in ('tests', 'failures', 'errors', 'skipped')}
        for suite in ElementTree.parse(folder / 'junit.xml').getroot().iter('testsuite'):
            for key in counts: counts[key] += int(suite.attrib.get(key, 0))
        state['integration'] = counts
        assert run.returncode == 0 and counts['tests'] >= 6 and not any(counts[k] for k in ('failures', 'errors', 'skipped'))
        state['health'] = health()
        assert all(code == 200 for code in state['health'].values()), 'Local serving health is not green'
        state['pass'] = True
    finally:
        state.update(protected_hashes_unchanged=digests() == before, candidate_unchanged=source() == candidate,
                     primary_schema_after=asyncio.run(primary_schema()))
        state['pass'] = state['pass'] and state['protected_hashes_unchanged'] and state['candidate_unchanged'] and schema == state['primary_schema_after']
        with (folder / 'receipt.json').open('x', encoding='utf-8') as out: json.dump(state, out, indent=2)
        print(json.dumps({'folder': str(folder), **{k: v for k, v in state.items() if k not in ('source', 'protected_before')}}))
    raise SystemExit(0 if state['pass'] else 1)


if __name__ == '__main__':
    with isolated_test_slot(): main()
