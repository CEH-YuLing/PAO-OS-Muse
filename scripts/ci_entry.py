"""One Linux gate shared by hosted CI and the disposable local runner."""
import json,os,platform,subprocess,sys,time
from pathlib import Path
from sqlalchemy.engine import make_url

def main():
    root=Path.cwd();url=make_url(os.environ['DATABASE_URL'])
    assert sys.platform=='linux'
    assert url.drivername=='postgresql+asyncpg' and url.host=='127.0.0.1' and url.port==5432 and url.database=='pao_test' and url.username=='pao'
    assert os.environ.get('REDIS_URL','').endswith('/15')
    hosted=os.environ.get('GITHUB_ACTIONS')=='true'
    assert (hosted and os.environ.get('PAO_CI_RESTORE')=='1') or (root==Path('/workspace') and os.environ.get('PAO_LINUX_LOCAL_RESTORE')=='1')
    runtime=root/'.runtime';runtime.mkdir(exist_ok=True)
    result={'pass':False,'linux_execution':True,'remote_github_ci':hosted,'production_accepted':False,
        'python':platform.python_version(),'system':platform.system(),'run_id':os.environ.get('PAO_S6_LINUX_RUN'), 'stages':[]}
    def run(name,*command):
        start=time.monotonic();print(json.dumps({'stage':name,'state':'running'}),flush=True)
        subprocess.run(list(command),check=True)
        result['stages'].append({'stage':name,'pass':True,'seconds':round(time.monotonic()-start,2)})
    py=sys.executable
    try:
        run('offline-readiness',py,'scripts/test_s6_readiness.py')
        run('current-release-readiness',py,'scripts/test_current_readiness.py')
        run('cli-foundation-offline',py,'-B','scripts/test_p84_cli_foundation.py')
        run('codex-protocol-offline',py,'-B','scripts/test_p84_codex_protocol.py')
        run('codex-docker-transport-offline',py,'-B','scripts/test_p84_docker_transport.py')
        run('codex-host-runtime-pin-offline',py,'-B','scripts/test_p84_runtime_pin.py')
        run('windows-candidate-restore-profile-offline',py,'-B','scripts/test_windows_candidate_restore.py')
        run('lifecycle-readiness',py,'-m','pytest','-q','scripts/test_s62_readiness.py')
        run('production-config-and-archive-guards',py,'-m','pytest','-q','scripts/test_production_profile.py','scripts/test_acos_checkpoint.py','scripts/test_phase3_readiness.py')
        run('security-gate-unit','node','--test','scripts/test_js_dependencies.cjs')
        run('runtime-advisories','node','scripts/check_js_dependencies.cjs')
        run('python-security-unit',py,'scripts/test_python_dependencies.py')
        run('python-runtime-advisories',py,'scripts/check_python_dependencies.py')
        run('patched-native-image-css-compatibility','node','--test','scripts/test_security_compat.cjs')
        run('hosted-restore-guards',py,'scripts/test_ci_restore_profile.py')
        run('local-restore-guards',py,'scripts/test_linux_local_restore.py')
        run('temporal-native-guards',py,'scripts/test_temporal_fixture.py')
        run('temporal-namespace-readiness-guards',py,'scripts/test_temporal_namespace.py')
        run('explicit-temporal-bootstrap',py,'scripts/bootstrap_temporal_test.py')
        run('schema',py,'-m','alembic','upgrade','head')
        run('portability-smoke',py,'-m','pytest','-q','-x',
            'apps/api/tests/test_goal_dispatcher.py::test_real_parent_pre_child_cancel_outbox_replay',
            'apps/api/tests/test_studio_arq_bridge.py','apps/api/tests/test_temporal_queue_cancel.py','apps/api/tests/test_p7_restore.py',
            'apps/api/tests/test_studio_connection_recovery.py')
        run('route-types','node','node_modules/next/dist/bin/next','typegen','apps/web')
        run('full-backend-node-types-contract-restore',py,'scripts/run_p0_checks.py')
        import xml.etree.ElementTree as ET
        suite=ET.parse(runtime/'backend-full.xml').getroot().find('testsuite')
        counts={k:int(suite.get(k,'0')) for k in ('tests','failures','errors','skipped')}
        assert counts['tests']>=2258 and counts['failures']==counts['errors']==counts['skipped']==0
        result['backend']=counts
        run('production-web-build','node','node_modules/next/dist/bin/next','build','apps/web')
        result['pass']=True
    finally:
        for name in ('ci-result.json','s6-linux-result.json'):(runtime/name).write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
if __name__=='__main__':main()
