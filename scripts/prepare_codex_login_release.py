"""Verified source-only release plan; does not copy, log in or change settings."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.modules.operations.checkpoint import digest,entries
from backup_acos_checkpoint import frontend_supplements
from prepare_p84_native_release import unlinked

CANDIDATE=ROOT/'.runtime/codex-login-candidate-20261019'
CHECKPOINT=ROOT/'.runtime/codex-login-checkpoint-fdf781535d1c43f09f6de7c0f6cff9ef/checkpoint.json'
TARGETS=('apps/api/pao/app.py','apps/api/pao/config.py','apps/api/pao/modules/cli_connections/api.py',
 'apps/api/pao/modules/cli_connections/login_transport.py','apps/api/pao/modules/cli_connections/login_manager.py',
 'apps/api/tests/test_cli_login.py','apps/api/tests/test_cli_login_transport.py','apps/api/tests/test_app_factory.py',
 'packages/contracts/openapi.json','apps/web/components/workspace/ClientModelSettings.tsx',
 'apps/web/components/workspace/CodexConnect.tsx','apps/web/components/workspace/codex-connect.css',
 'apps/web/lib/codex-login.mjs','apps/web/lib/codex-login.d.mts','apps/web/lib/codex-login.test.mjs',
 'scripts/windows_candidate_restore.py')

def proof(folder,prefix):
    folder=unlinked(folder,ROOT)
    assert folder.parent==ROOT/'.runtime' and folder.name.startswith(prefix)
    value=json.loads((folder/'receipt.json').read_text())
    assert value.get('pass') is True
    return value

def backend(values):return {k:v for k,v in values.items() if k.startswith(('apps/api/','packages/cli-runtime/','packages/contracts/','scripts/')) or k in ('requirements.lock','pyproject.toml','alembic.ini')}
def web(values):return {k:v for k,v in values.items() if k.startswith('apps/web/') and not k.endswith('/next-env.d.ts')}

def main(args):
    assert ROOT==Path('F:/PAO-ACOS')
    if args.full.name.startswith('codex-login-regression-'):
        from codex_login_regression import verified_coverage
        full=proof(args.full,'codex-login-regression-')
        counts=verified_coverage(args.full,entries(CANDIDATE))
        full_source=entries(CANDIDATE)
    else:
        full=proof(args.full,'codex-login-tests-')
        assert full.get('full_backend_regression') is True and full.get('candidate_unchanged_during_tests') is True and full.get('primary_source_env_unchanged') is True and full.get('provider_calls')==0
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        for suite in ElementTree.parse(args.full/'junit.xml').getroot().iter('testsuite'):
            for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        assert counts['tests']>=2356 and not any(counts[k] for k in ('failures','errors','skipped')) and all(full[k]==v for k,v in counts.items())
        full_source=full['candidate_source']
    current={**entries(CANDIDATE),**frontend_supplements(CANDIDATE)}
    assert backend(entries(CANDIDATE))==backend(full_source)
    front=proof(args.frontend,'model-provider-tabs-frontend-')
    assert front['stages']==['contracts','node','typegen','typecheck','build'] and front['frontend_unchanged_during_build']
    built=unlinked(args.frontend/'source',ROOT)
    built_files={**entries(built),**frontend_supplements(built)}
    assert web(built_files)==web(current)
    for name in ('package.json','package-lock.json','packages/contracts/openapi.json'):assert built_files[name]==current[name]
    browser=proof(args.browser,'codex-login-browser-')
    assert browser['fixture_only'] and browser['real_provider_calls']==0 and not browser['real_login']
    rpc=proof(args.rpc,'codex-login-rpc-')
    assert rpc['network']=='none' and rpc['cleanup_verified'] and not rpc['primary_profiles_mounted']
    original=json.loads(CHECKPOINT.read_text())
    primary={**entries(ROOT),**frontend_supplements(ROOT)}
    assert digest(ROOT/'.env')==original['env_sha256']
    for name,value in primary.items():
        if name.startswith(('apps/api/','packages/cli-runtime/')):assert original['source_manifest'].get(name)==value
    for name in set(current)|set(original['source_manifest']):
        if name.startswith('apps/api/') and current.get(name)!=original['source_manifest'].get(name):assert name in TARGETS
    changes={}
    for name in TARGETS:
        source=unlinked(CANDIDATE/name,ROOT);target=unlinked(ROOT/name,ROOT)
        before=digest(target) if target.exists() else None
        assert before==original['source_manifest'].get(name),'Overlapping source change: '+name
        if before!=current[name]:changes[name]={'source':str(source),'before':before,'after':current[name]}
    name='packages/contracts/schema.d.ts'
    changes[name]={'source':str(unlinked(built/name,ROOT)),'before':primary[name],'after':digest(built/name)}
    folder=ROOT/'.runtime'/('codex-login-install-'+uuid4().hex);folder.mkdir()
    plan={'source_plan_ready':True,'primary_installed':False,'schema':'0072','operations':416,'counts':counts,
          'changes':changes,'env_before_sha256':original['env_sha256'],'checkpoint':str(CHECKPOINT),
          'full':str(args.full),'frontend':str(args.frontend),'browser':str(args.browser),'rpc':str(args.rpc),
          'candidate_backend':backend(entries(CANDIDATE)),'cli_runtime_registry_sha256':digest(ROOT/'.runtime/cli-device.json'),
          'python_pin_sha256':digest(ROOT/'.runtime/acos-python-runtime.json')}
    (folder/'source-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(folder),'files':len(changes),'ready':True,'installed':False}))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('full','frontend','browser','rpc'):parser.add_argument('--'+name,type=Path,required=True)
    main(parser.parse_args())
