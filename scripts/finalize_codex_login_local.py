"""Summarize verified local install, never infer real owner auth or inference."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.modules.operations.checkpoint import entries,digest
from codex_login_regression import verified_coverage

def folder(value,prefix):
    value=value.resolve()
    assert value.parent==ROOT/'.runtime' and value.name.startswith(prefix)
    assert not value.is_symlink()
    return value

def read(path):return json.loads(path.read_text(encoding='utf-8'))

def main(args):
    install=folder(args.install,'codex-login-install-')
    plan=read(install/'source-plan.json')
    installed=read(install/'installed-check.json')
    assert installed['pass'] and installed['old_rows_exact'] and installed['read_only_archive_replays']==3
    assert installed['diagnostic_bearer_GET_only'] and installed['provider_calls']==0
    assert not any(installed[k] for k in ('real_profile_login','grant_activated','native_job_tested','production_accepted'))
    for name,value in plan['changes'].items():assert digest(ROOT/name)==value['after']
    actual=entries(ROOT)
    for name,value in plan['candidate_backend'].items():
        if name.startswith(('apps/api/','packages/cli-runtime/','packages/contracts/')) or name in ('requirements.lock','pyproject.toml','alembic.ini'):
            # Generated schema comes from the verified frontend build, not the
            # candidate's old generated file. Its exact digest is in the plan.
            expected=plan['changes'][name]['after'] if name=='packages/contracts/schema.d.ts' else value
            assert actual[name]==expected,name
    assert digest(ROOT/'.runtime/cli-device.json')==plan['cli_runtime_registry_sha256']
    assert digest(ROOT/'.runtime/acos-python-runtime.json')==plan['python_pin_sha256']
    previous=(install/'env-before.private').read_bytes().replace(b'\r\n',b'\n')
    current=(ROOT/'.env').read_bytes().replace(b'\r\n',b'\n')
    assert current.replace(b'CLI_BROWSER_LOGIN_ENABLED=true\n',b'')==previous
    regression=folder(Path(plan['full']),'codex-login-regression-')
    counts=verified_coverage(regression,entries(ROOT/'.runtime/codex-login-candidate-20261019'))
    frontend=read(Path(plan['frontend'])/'receipt.json')
    assert frontend['pass'] and frontend['frontend_unchanged_during_build']
    codex=folder(args.codex_browser,'codex-login-browser-')
    client=folder(args.core_browser,'model-provider-tabs-browser-')
    for path in (codex,client):
        value=read(path/'receipt.json')
        assert value['pass'] and value['fixture_only']
    assert read(codex/'receipt.json')['backend_forwarded']==0
    assert read(codex/'receipt.json')['real_provider_calls']==0 and not read(codex/'receipt.json')['real_login']
    assert read(client/'receipt.json')['backend_requests_forwarded']==0
    assert read(client/'receipt.json')['real_mutations']==0 and read(client/'receipt.json')['external_provider_calls']==0
    result={'date':'2026-10-19','pass':True,'state':'local_browser_login_installed_awaiting_owner',
        'install':str(install),'binding':installed['binding'],'schema':'0072','operations':416,'physical_tables':155,
        'backend_coverage':counts,'backend_evidence':str(regression),'single_full_run_passed':False,
        'historical_failed_full_preserved':True,'frontend':plan['frontend'],
        'installed_codex_browser':str(codex),'installed_core_browser':str(client),
        'primary_installed':True,'old_rows_exact':True,'archive_replays':3,
        'browser_login_enabled':True,'scope':'local_personal_self_only',
        'real_owner_login':False,'grant_activated':False,'provider_inference':False,'native_job_tested':False,
        'phase_C_complete':False,'phase_E_complete':False,'S6_complete':False,'production_accepted':False}
    if args.observe_user_activity:
        observed=folder(args.observe_user_activity,'codex-login-user-activity-')
        activity=read(observed/'receipt.json');profile=activity['profile_metadata_only']
        assert activity['user_confirmed_activity'] and not activity['primary_restored'] and not activity['row_contents_logged']
        assert any(item['method']=='POST' and item['route'].endswith('/login') and item['status']==200 for item in activity['write_request_metadata'])
        authenticated=profile['status']=='connected' and profile['auth_recorded'] and not profile['operation_pending']
        result.update(state='local_installed_owner_auth_observed' if authenticated else 'local_installed_owner_active',
            real_owner_login=authenticated,owner_profile_metadata_observed=profile,
            user_activity_evidence=str(observed),user_confirmed_activity=True,
            old_rows_exact_scope='initial_post_install_check_only',
            post_browser_snapshot_equal=activity['comparison_pass'],
            post_browser_check_passed=False,
            post_browser_failed_check_preserved=str(install/'post-browser-check.log'))
    for target in ('codex-login-completion.json','codex-login-current-status.json'):
        (ROOT/'.runtime'/target).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('install','codex-browser','core-browser'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--observe-user-activity',type=Path)
    main(parser.parse_args())
