"""Prepare only a hash-guarded source plan; never install, migrate or log in.

This operator helper is not a business runner. A successful plan still requires
a fresh verified DB checkpoint, idle/process checks and post-install live checks.
"""
import argparse
import json
from pathlib import Path
import re
import sys
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from pao.modules.operations.checkpoint import digest, entries

CANDIDATE = ROOT / '.runtime/p84-native-candidate-20261018'
BASELINE = ROOT / '.runtime/p84-native-checkpoint-1df83a532cfa412697a10a48393c25d0/checkpoint.json'
# Explicit reviewed slice: never copy all candidate files or stale documents.
TARGETS = (
    'apps/api/migrations/versions/0072_cli_model_connections.py',
    'apps/api/pao/app.py', 'apps/api/pao/config.py', 'apps/api/pao/models.py',
    'apps/api/pao/modules/brains/validation.py', 'apps/api/pao/modules/chat/ledger.py',
    'apps/api/pao/modules/cli_connections/__init__.py',
    'apps/api/pao/modules/cli_connections/api.py',
    'apps/api/pao/modules/cli_connections/gateway.py',
    'apps/api/pao/modules/cli_connections/runtime.py',
    'apps/api/pao/modules/cli_connections/service.py',
    'apps/api/pao/modules/connections/api.py',
    'apps/api/pao/modules/connections/grants.py',
    'apps/api/pao/modules/connections/inventory.py',
    'apps/api/pao/modules/connections/model_authority.py',
    'apps/api/pao/modules/connections/model_fence.py',
    'apps/api/pao/modules/engines/api.py',
    'apps/api/pao/modules/engines/contract.py',
    'apps/api/pao/modules/engines/service.py',
    'apps/api/tests/test_app_factory.py', 'apps/api/tests/test_cli_connections.py',
    'packages/contracts/openapi.json', 'pyproject.toml',
    'scripts/check_p7_restore.py', 'scripts/check_s03_restore.py',
    'scripts/restart_acos_backend.ps1', 'scripts/run_p0_checks.py',
    'scripts/start_acos_local.ps1', 'scripts/start_local.ps1',
    'scripts/supervise_acos_local.ps1',
)


def unlinked(path, root):
    path, root = Path(path), Path(root)
    if not path.is_absolute() or not path.is_relative_to(root):
        raise ValueError('p84_release_path_denied')
    current = path
    while True:
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise ValueError('p84_release_link_denied')
        if current == root:
            break
        current = current.parent
    return path


def verified_full(folder, current):
    if (folder.parent != ROOT / '.runtime'
            or not re.fullmatch(r'p84-native-tests-[0-9a-f]{32}', folder.name)):
        raise ValueError('p84_full_receipt_scope_denied')
    receipt = json.loads(unlinked(folder / 'receipt.json', ROOT).read_text(encoding='utf-8'))
    for key in ('pass', 'full_backend_regression', 'primary_source_env_schema_unchanged', 'candidate_source_unchanged'):
        if receipt.get(key) is not True:
            raise ValueError('p84_full_gate_not_passed')
    counts = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
    for suite in ElementTree.parse(unlinked(folder / 'junit.xml', ROOT)).getroot().iter('testsuite'):
        for key in counts:
            counts[key] += int(suite.attrib.get(key, 0))
    if (counts['tests'] < 2300 or any(counts[k] for k in ('failures', 'errors', 'skipped'))
            or any(receipt.get(k) != v for k, v in counts.items())
            or receipt.get('candidate_schema') != '0072'
            or receipt.get('provider_calls') != 0 or receipt.get('primary_migrated') is not False
            or receipt.get('candidate_source') != current):
        raise ValueError('p84_frozen_full_evidence_mismatch')
    return counts


def changes_for(root, candidate, baseline, tested):
    changes = {}
    for name in TARGETS:
        source, target = unlinked(candidate / name, root), unlinked(root / name, root)
        if not source.is_file() or tested.get(name) != digest(source):
            raise ValueError('p84_candidate_changed: ' + name)
        before = digest(target) if target.is_file() else None
        if before != baseline.get(name):
            raise ValueError('p84_preserve_overlapping_change: ' + name)
        if before != tested[name]:
            changes[name] = {'before': before, 'after': tested[name]}
    if not changes:
        raise ValueError('p84_no_source_changes')
    return changes


def validate_scope(baseline, tested, primary):
    api = lambda values: {n: h for n, h in values.items() if n.startswith('apps/api/')}
    if api(primary) != api(baseline):
        raise ValueError('p84_primary_api_changed_since_checkpoint')
    for name in set(api(baseline)) | set(api(tested)):
        if baseline.get(name) != tested.get(name) and (name not in TARGETS or name not in tested):
            raise ValueError('p84_unreviewed_candidate_api_change: ' + name)
    library = lambda values: {n: h for n, h in values.items()
                              if n.startswith('packages/cli-runtime/pao_cli_runtime/')}
    if not library(tested) or library(primary) != library(tested):
        raise ValueError('p84_host_library_changed')


def frontend_contract(folder, tested, primary, baseline):
    if (folder.parent != ROOT / '.runtime'
            or not re.fullmatch(r'p84-frontend-[0-9a-f]{32}', folder.name)):
        raise ValueError('p84_frontend_receipt_scope_denied')
    proof = json.loads(unlinked(folder / 'receipt.json', ROOT).read_text(encoding='utf-8'))
    if (proof.get('pass') is not True or proof.get('provider_calls') != 0
            or proof.get('primary_frontend_changed') is not False
            or proof.get('candidate_source_changed') is not False
            or proof.get('stages') != ['contracts', 'node', 'typegen', 'typecheck', 'build']):
        raise ValueError('p84_frontend_gate_not_passed')
    source = unlinked(folder / 'source', ROOT)
    built = entries(source)
    # next-env.d.ts is generated by next typegen; no other input exclusion.
    web = lambda values: {n: h for n, h in values.items()
                          if n.startswith('apps/web/') and not n.endswith('/next-env.d.ts')}
    if web(built) != web(tested) or web(primary) != web(tested):
        raise ValueError('p84_frontend_source_changed')
    for name in ('package.json', 'package-lock.json', 'packages/contracts/openapi.json'):
        if built.get(name) != tested.get(name):
            raise ValueError('p84_frontend_contract_or_lock_changed')
    for name, hashed in proof.get('frontend_supplements', {}).items():
        if (not name.startswith('apps/web/') or not name.endswith(('.jsx', '.d.mts'))
                or any(digest(unlinked(root / name, ROOT)) != hashed for root in (ROOT, CANDIDATE, source))):
            raise ValueError('p84_frontend_supplement_changed')
    name = 'packages/contracts/schema.d.ts'
    if primary.get(name) != baseline.get(name) or name not in built:
        raise ValueError('p84_generated_contract_preimage_changed')
    return {'target': name, 'source': str(unlinked(source / name, ROOT)),
            'before': primary.get(name), 'after': built[name], 'generated_by': str(folder)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-folder', type=Path, required=True)
    parser.add_argument('--frontend-folder', type=Path, required=True)
    args = parser.parse_args()
    if ROOT != Path('F:/PAO-ACOS'):
        raise SystemExit('p84_primary_checkout_required')
    unlinked(CANDIDATE, ROOT)
    tested = entries(CANDIDATE)
    counts = verified_full(args.full_folder, tested)
    baseline = json.loads(unlinked(BASELINE, ROOT).read_text(encoding='utf-8'))['source_manifest']
    primary = entries(ROOT)
    validate_scope(baseline, tested, primary)
    derived_contract = frontend_contract(args.frontend_folder, tested, primary, baseline)
    changes = changes_for(ROOT, CANDIDATE, baseline, tested)
    # Existing host library must be exactly the library exercised by the full run.
    library = {n: h for n, h in tested.items() if n.startswith('packages/cli-runtime/pao_cli_runtime/')}
    if not library or any(digest(unlinked(ROOT / n, ROOT)) != h for n, h in library.items()):
        raise ValueError('p84_host_library_changed')
    folder = ROOT / '.runtime' / ('p84-native-release-' + uuid4().hex)
    folder.mkdir()
    result = {'version': 1, 'source_plan_ready': True, 'changes': changes,
              'derived_contract': derived_contract,
              'full_folder': str(args.full_folder), 'full_counts': counts,
              'candidate_source': tested, 'host_library': library,
              'schema_before': '0071', 'schema_target': '0072',
              'requires_fresh_verified_database_checkpoint': True,
              'primary_installed': False, 'primary_migrated': False, 'provider_calls': 0,
              'login_authorized_by_this_plan': False, 'whole_P84_C_accepted': False,
              'production_accepted': False}
    with (folder / 'source-plan.json').open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    print(json.dumps({'source_plan': str(folder / 'source-plan.json'),
                      'files': len(changes), 'primary_installed': False}))


if __name__ == '__main__':
    main()
