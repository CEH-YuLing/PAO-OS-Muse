"""Bounded CLI preparation verification; not native engine acceptance/release."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_p84_foundation import binding, entries, health, primary_schema, protected


def main():
    if ROOT != Path('F:/PAO-ACOS'):
        raise SystemExit('p84_checkout_required')
    baseline_folder = ROOT / '.runtime/p84-foundation-19f81bcae1594f5d9c7fcd576df6497f'
    before = json.loads((baseline_folder / 'baseline.json').read_text(encoding='utf-8'))
    direct_path = ROOT / '.runtime/p84-codex-direct-9e566836ff98436da0e9b46ba089f479/direct-smoke.json'
    direct = json.loads(direct_path.read_text(encoding='utf-8'))
    folder = ROOT / '.runtime' / ('p84-codex-preparation-' + uuid4().hex)
    folder.mkdir()
    source = entries(ROOT)
    tests = []
    for script, count in (('test_p84_cli_foundation.py', 26), ('test_p84_codex_protocol.py', 23)):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / script)],
                                capture_output=True, timeout=90, cwd=ROOT)
        log = result.stdout + result.stderr
        (folder / (script + '.log')).write_bytes(log)
        tests.append({'script': script, 'expected': count,
                      'pass': result.returncode == 0 and f'Ran {count} tests'.encode() in log and b'\nOK' in log})
    schema = asyncio.run(primary_schema())
    endpoints = health()
    state = {'utc': datetime.now(timezone.utc).isoformat(), 'stage': 'P8.4-C-preparation-and-direct-operator-smoke',
             'tests': tests, 'source_unchanged_during_tests': source == entries(ROOT),
             'protected_unchanged_from_C_checkpoint': protected() == before['protected'],
             'binding_unchanged': binding() == before['binding'], 'binding': binding(),
             'schema_unchanged': schema == before['schema'], 'schema': schema, 'health': endpoints,
             'direct_operator_smoke_pass': direct.get('pass') is True and direct.get('auth_mode') == 'chatgpt'
                                           and direct.get('response') == 'PAO_CODEX_OK',
             'direct_receipt': str(direct_path.relative_to(ROOT)),
             'inference_repeated_in_this_check': False, 'full_backend_regression': False,
             'primary_content_hashes_measured': False, 'native_PAO_engine_registered': False,
             'whole_P84_C_accepted': False, 'production_accepted': False,
             'tested_source_manifest': source}
    state['bounded_check_pass'] = (all(t['pass'] for t in tests)
        and all(state[k] for k in ('source_unchanged_during_tests', 'protected_unchanged_from_C_checkpoint',
                                  'binding_unchanged', 'schema_unchanged', 'direct_operator_smoke_pass'))
        and all(code == 200 for code in endpoints.values()))
    (folder / 'receipt.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    print(folder)
    print(json.dumps({k: v for k, v in state.items() if k != 'tested_source_manifest'}))
    raise SystemExit(0 if state['bounded_check_pass'] else 1)


if __name__ == '__main__':
    main()
