"""Fresh local S6 preflight; never infer pilot/production acceptance from fixtures.

Reuses installed S5 read-only checks and native worker liveness. No provider
calls, feature activation, migrations, authentication bypass or business writes.
"""
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from zipfile import BadZipFile


class ReadinessError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def store_snapshot(root, result):
    """Regenerated diagnostic only; never overwrite immutable acceptance proof."""
    from uuid import uuid4
    runtime = root / '.runtime'
    runtime.mkdir(exist_ok=True)
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    temporary = runtime / ('s6-readiness-' + uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(runtime / 's6-readiness.json')
    return result


def failed_snapshot(root, reason, binding=None):
    return store_snapshot(root, {'version': 's6-local-preflight-v2', 'binding': binding,
        'local_checks_passed': False, 's6_accepted': False, 'production_accepted': False,
        'provider_calls': False, 'business_writes': False, 'reason': reason,
        'gates': [{'id': 'current_release_evidence', 'state': 'fail', 'reason': reason},
                  {'id': 's6_1_real_business', 'state': 'external_pending'},
                  {'id': 's6_2_production', 'state': 'deferred_by_user'},
                  {'id': 's6_3_owner_pilot', 'state': 'external_pending'}]})


def assess_current(live, health, proof, installed, ci, binding, source_verified, incident_review_verified=False):
    """Current release proof, independent gates; unresolved drift never turns green."""
    same = proof.get('binding') == installed.get('binding') == live.get('binding') == binding
    installed_ok = (installed.get('pass') is True and installed.get('primary_unchanged') is True
        and installed.get('environment_unchanged') is True and installed.get('api_mutations') == 0
        and type(installed.get('api_mutations')) is int and source_verified is True and same)
    counts = ci.get('backend', {})
    full = (ci.get('pass') is True and ci.get('linux_execution') is True
        and ci.get('node_and_typecheck_and_build') is True and ci.get('primary_unchanged') is True
        and ci.get('env_unchanged') is True and ci.get('owned_containers_removed') is True
        and valid_count(counts.get('tests'), 2293)
        and all(type(counts.get(k)) is int and counts[k] == 0 for k in ('failures','errors','skipped')))
    live_ok = (live.get('pass') is True and live.get('revision') == '0071'
        and live.get('operations') == 407 and live.get('physical_tables') == 153
        and live.get('read_only_replays') == 3 and live.get('business_hashes_unchanged') is True
        and live.get('provider_calls') is False and same)
    runtime = (all(type(health.get('endpoints', {}).get(k)) is int
        and health['endpoints'][k] == 200 for k in ('api_health','api_ready','web'))
        and health.get('operations', {}).get('worker', {}).get('healthy') is True)
    # A clean later test does not explain an earlier unexplained primary mutation.
    integrity = (incident_review_verified is True
                 and proof.get('primary_incident_review') == 'resolved_with_evidence')
    gates = [{'id': name, 'state': 'pass' if ok else 'fail'} for name, ok in (
        ('current_release_source_and_install', installed_ok), ('current_source_full_regression', full),
        ('installed_contract_replays', live_ok), ('windows_runtime', runtime),
        ('primary_data_integrity_review', integrity))]
    gates += [{'id':'s6_1_real_business','state':'external_pending'},
              {'id':'s6_1_real_action','state':'external_pending'},
              {'id':'s6_2_hosted_ci_current_source','state':'external_pending'},
              {'id':'s6_2_production','state':'deferred_by_user'},
              {'id':'s6_3_owner_pilot','state':'external_pending'}]
    return {'version':'s6-local-current-release-v1', 'binding':binding,
        'local_checks_passed': bool(installed_ok and full and live_ok and runtime and integrity),
        's6_accepted':False, 'production_accepted':False, 'provider_calls':False,
        'business_writes':False, 'gates':gates}


def current_release(root, binding):
    import hashlib
    from zipfile import ZipFile
    from pao.modules.operations.checkpoint import entries, digest
    from backup_acos_checkpoint import source_supplements
    proof = read_object(root / '.runtime/current-local-release.json')
    def evidence(field):
        path = Path(proof[field]).resolve()
        if not path.is_relative_to((root / '.runtime').resolve()):
            raise ReadinessError('evidence_path_outside_runtime')
        return path, read_object(path)
    ci_path, ci = evidence('ci_manifest')
    _, installed = evidence('installed_receipt')
    def sources():
        return {n:h for n,h in {**entries(root), **source_supplements(root)}.items()
                if not n.endswith('next-env.d.ts')}
    before = sources()
    if before != proof.get('source_files'):
        raise ReadinessError('current_source_proof_mismatch')
    archive = (ci_path.parent / 'source.zip').resolve()
    if not archive.is_relative_to((root / '.runtime').resolve()):
        raise ReadinessError('ci_archive_path_outside_runtime')
    if digest(archive) != ci.get('source_sha256'):
        raise ReadinessError('ci_source_archive_mismatch')
    with ZipFile(archive) as frozen:
        tested = {name:hashlib.sha256(frozen.read(name)).hexdigest() for name in frozen.namelist()
                  if not name.endswith('next-env.d.ts')}
    if tested != before:
        raise ReadinessError('current_source_not_tested_by_ci')
    live = probe(root, 'check_task_delete_live.py')
    health = probe(root, 'check_acos_health.py')
    if sources() != before:
        raise ReadinessError('source_changed_during_preflight')
    # This remediation preserves the unresolved incident. It does not implement
    # an automatic incident waiver, even if somebody edits a receipt string.
    result = assess_current(live, health, proof, installed, ci, binding, True, False)
    return store_snapshot(root, result)


def valid_count(value, minimum):
    return type(value) is int and value >= minimum


def assess(live, regression, health, binding, lifecycle=None):
    released = live.get('revision') == '0071'
    expected = ('0071', 399, 153) if released else ('0070', 382, 149)
    lifecycle = lifecycle or {}
    accepted = (released and lifecycle.get('phase1_accepted') is True
        and lifecycle.get('binding') == binding
        and all(lifecycle.get(key) is True for key in
                ('identity', 'sessions', 'data', 'no_auto_purge', 'browser', 'migration_restore')))
    baseline = (live.get('pass') is True and live.get('revision') == expected[0]
        and live.get('operations') == expected[1] and live.get('physical_tables') == expected[2]
        and live.get('read_only_replays') == 3 and live.get('binding') == binding
        and live.get('business_hashes_unchanged') is True
        and live.get('provider_calls') is False)
    tests = (regression.get('pass') is True and regression.get('binding') == binding
        and regression.get('binding_unchanged') is True
        and valid_count(regression.get('tests'), 2251 if released else 2224)
        and all(type(regression.get(k)) is int and regression[k] == 0
                for k in ('failures', 'errors', 'skipped')))
    endpoints = health.get('endpoints', {})
    worker = health.get('operations', {}).get('worker', {})
    runtime = (all(type(endpoints.get(k)) is int and endpoints[k] == 200
                   for k in ('api_health', 'api_ready', 'web'))
        and worker.get('healthy') is True)
    gates = [
        {'id': 's5_installed', 'state': 'pass' if baseline else 'fail',
         'reason': 'installed_contract_binding_replay_and_rows'},
        {'id': 'backend_regression', 'state': 'pass' if tests else 'fail',
         'reason': 'same_backend_full_regression_not_a_new_rerun'},
        {'id': 'windows_runtime', 'state': 'pass' if runtime else 'fail',
         'reason': 'fresh_http_and_native_worker_lease_not_provider_health'},
        {'id': 's6_1_real_business', 'state': 'external_pending',
         'reason': 'user_deferred_real_data_account_period_and_export'},
        {'id': 's6_1_real_action', 'state': 'external_pending',
         'reason': 'requires_separate_authority_destination_adapter_and_bounded_budget'},
        {'id': 's6_2_linux_ci', 'state': 'external_pending',
         'reason': 'hosted_ci_not_executed_local_linux_artifacts_reported_separately'},
        {'id': 's6_2_identity_lifecycle', 'state': 'local_accepted' if accepted else 'implementation_pending',
         'reason': 'current_binding_lifecycle_receipt' if accepted else 'lifecycle_receipt_missing_or_stale'},
        {'id': 's6_2_data_lifecycle', 'state': 'local_accepted' if accepted else 'implementation_pending',
         'reason': 'current_binding_lifecycle_receipt' if accepted else 'lifecycle_receipt_missing_or_stale'},
        {'id': 's6_2_production', 'state': 'external_pending',
         'reason': 'no_dedicated_host_https_security_retention_cold_restore_reboot_evidence'},
        {'id': 's6_3_owner_pilot', 'state': 'external_pending',
         'reason': 'no_real_pilot_owner_acceptance_or_measured_tenant_quality_cost'},
    ]
    return {'version': 's6-local-preflight-v1', 'binding': binding,
        'local_checks_passed': bool(baseline and tests and runtime and (not released or accepted)),
        's6_accepted': False, 'production_accepted': False,
        'provider_calls': False, 'business_writes': False, 'gates': gates}


def read_object(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('evidence_too_large')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('evidence_object_required')
    return value


def probe(root, script):
    result = subprocess.run([sys.executable, str(root/'scripts'/script)], cwd=root,
        capture_output=True, text=True, encoding='utf-8', timeout=90)
    if result.returncode:
        # Never echo arbitrary subprocess output, URLs, credentials or exceptions.
        raise ValueError('local_probe_failed:' + script)
    objects = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    if len(objects) != 1 or not isinstance(objects[0], dict):
        raise ValueError('local_probe_invalid:' + script)
    return objects[0]


def main():
    import asyncio
    from sqlalchemy.engine import make_url
    from pao.config import ROOT, settings
    from pao.skills import execution_binding, _execution_digest
    from datetime import datetime, timezone
    config = settings(); url = make_url(config.database_url)
    if (ROOT.resolve() != Path('F:/PAO-ACOS') or url.host != '127.0.0.1'
            or url.port != 15432 or url.database != 'pao_acos_local'):
        raise ValueError('isolated_acos_local_required')
    binding = execution_binding()
    if (ROOT/'.runtime/current-local-release.json').exists():
        result = current_release(ROOT, binding)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['local_checks_passed'] else 1
    # This additive backend release supersedes the older UI-only overlays.
    # Bounded task-deletion tests are not a current full-regression receipt.
    if (ROOT/'.runtime/task-delete-completion.json').exists():
        completion = read_object(ROOT/'.runtime/task-delete-completion.json')
        reason = ('current_release_full_evidence_required' if completion.get('binding') == binding
                  else 'latest_release_binding_stale')
        raise ReadinessError(reason)
    if (ROOT/'.runtime/ux-restructure-completion.json').exists():
        from check_ux_restructure_readiness import main as ux_restructure_readiness
        return ux_restructure_readiness()
    if (ROOT/'.runtime/connections-ui-completion.json').exists():
        from check_connections_ui_readiness import main as connections_ui_readiness
        return connections_ui_readiness()
    if (ROOT/'.runtime/organization-completion.json').exists():
        from check_organization_readiness import main as organization_readiness
        return organization_readiness()
    if any(getattr(config, k) for k in ('meta_enabled', 'google_ads_enabled',
        'meta_write_enabled', 'meta_autopilot_enabled', 'ads_autopilot_global_enabled',
        'telegram_enabled', 'telegram_scoped_runtime_enabled', 'meta_installation_config_enabled')):
        raise ValueError('external_flags_must_remain_disabled')
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    async def current_revision():
        connection_engine=create_async_engine(config.database_url)
        try:
            async with connection_engine.connect() as db:
                return await db.scalar(text('SELECT version_num FROM alembic_version'))
        finally:await connection_engine.dispose()
    released=asyncio.run(current_revision())=='0071'
    live = probe(ROOT, 'check_s62_live.py' if released else 'check_s5_live.py')
    health = probe(ROOT, 'check_acos_health.py')
    regression = read_object(ROOT/('.runtime/s62-backend.json' if released else '.runtime/s5-backend.json'))
    receipt=ROOT/'.runtime/s62-completion.json'
    lifecycle=read_object(receipt) if released and receipt.exists() else None
    result = assess(live, regression, health, binding, lifecycle)
    if _execution_digest() != binding['sha256']:
        raise ValueError('backend_changed_during_preflight')
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    runtime = ROOT/'.runtime'; runtime.mkdir(exist_ok=True)
    target = runtime/'s6-readiness.json'
    # This is a regenerated diagnostic snapshot, not an immutable acceptance receipt.
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['local_checks_passed'] else 1


def run():
    try:
        return main()
    except (OSError, ValueError, KeyError, TypeError, AssertionError, BadZipFile, subprocess.TimeoutExpired):
        from pao.config import ROOT
        # Do not expose exception strings, subprocess output or secret paths.
        error = sys.exception()
        reason = error.reason if isinstance(error, ReadinessError) else 'preflight_failed_no_acceptance'
        result = failed_snapshot(ROOT, reason) if ROOT.resolve() == Path('F:/PAO-ACOS') else {
            'local_checks_passed':False, 's6_accepted':False, 'production_accepted':False,
            'reason':'isolated_acos_local_required'}
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(run())
