"""Close only the local account/data phase from actual matching release evidence."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.engine import make_url
from pao.config import ROOT, settings
from pao.skills import execution_binding, _execution_digest
from apply_s62_migration import evidence


def main():
    config = settings()
    url = make_url(config.database_url)
    assert ROOT.resolve() == Path('F:/PAO-ACOS')
    assert (url.host, url.port, url.database, url.username) == ('127.0.0.1', 15432, 'pao_acos_local', 'pao')
    assert not any(getattr(config, key) for key in (
        'channel_retention_enabled', 'meta_enabled', 'google_ads_enabled', 'meta_write_enabled',
        'ads_autopilot_global_enabled', 'meta_autopilot_enabled', 'telegram_enabled',
        'telegram_scoped_runtime_enabled', 'meta_installation_config_enabled'))
    binding = execution_binding()
    full = evidence(ROOT/'.runtime/s62-backend.json')
    rollout = evidence(ROOT/'.runtime/s62-schema-rollout.json')
    live = evidence(ROOT/'.runtime/s62-live.json')
    for value in (full, rollout, live):
        assert value['binding'] == binding and value.get('provider_calls') is False
    assert full['binding_unchanged'] is True and full['tests'] == 2258
    assert all(full[key] == 0 for key in ('errors', 'failures', 'skipped'))
    assert all(rollout[key] is True for key in ('old_columns_exact', 'new_tables_empty', 'archives_unchanged', 'env_unchanged'))
    assert (live['revision'], live['operations'], live['physical_tables'], live['read_only_replays']) == ('0071', 399, 153, 3)
    assert live['business_hashes_unchanged'] is True and live['env_unchanged'] is True
    browser = evidence(rollout['browser'])
    assert browser['binding'] == binding and browser['backend_binding_unchanged'] is True
    from pao.modules.operations.checkpoint import entries
    from backup_acos_checkpoint import frontend_supplements
    frontend = {key: value for key, value in {**entries(ROOT), **frontend_supplements(ROOT)}.items()
                if key.startswith('apps/web/') and not key.endswith('next-env.d.ts')}
    assert browser['frontend_sha256'] == hashlib.sha256(json.dumps(frontend, sort_keys=True).encode()).hexdigest()
    assert all(browser[key] is True for key in ('real_api_db', 'invitation_created',
        'invitation_accepted_in_browser', 'two_sme_ui_isolation', 'export_real_download',
        'deletion_request_confirmed_without_purge', 'mobile_390', 'member_removed', 'server_logout_all'))
    assert evidence(Path(rollout['browser']).parent/'cleanup.json')['database_absent'] is True
    migration = evidence(rollout['migration'])
    assert all(migration[key] is True for key in ('old_columns_exact', 'populated_restore_exact',
        'audit_immutable_after_restore', 'populated_downgrade_refused', 'primary_unchanged', 'env_unchanged'))
    health_run = subprocess.run([sys.executable, 'scripts/check_acos_health.py'], cwd=ROOT,
        capture_output=True, text=True, encoding='utf-8', check=True, timeout=90)
    health = json.loads(health_run.stdout)
    assert all(health['endpoints'][key] == 200 for key in ('api_health', 'api_ready', 'web'))
    assert health['operations']['worker']['healthy'] is True
    assert _execution_digest() == binding['sha256']
    value = {'pass': True, 'version': 's62-phase1-local-v1',
        'checked_at': datetime.now(timezone.utc).isoformat(), 'binding': binding,
        'phase1_accepted': True, 'identity': True, 'sessions': True, 'data': True,
        'no_auto_purge': True, 'browser': True, 'migration_restore': True,
        'tests': full['tests'], 'backend_evidence': full['evidence'],
        'checkpoint': rollout['checkpoint'], 'browser_evidence': rollout['browser'],
        'migration_evidence': rollout['migration'], 'health': health,
        'provider_calls': False, 's6_accepted': False, 'production_accepted': False}
    target = ROOT/'.runtime/s62-completion.json'
    with target.open('x', encoding='utf-8') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
    print(json.dumps({'phase1_accepted': True, 'tests': full['tests'],
        'revision': '0071', 's6_accepted': False, 'production_accepted': False,
        'receipt': str(target)}))


if __name__ == '__main__':
    main()
