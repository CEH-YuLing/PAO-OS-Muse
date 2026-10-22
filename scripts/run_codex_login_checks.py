"""Serial candidate-only auth/regression checks. Never migrate the primary DB."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from xml.etree import ElementTree
from cryptography.fernet import Fernet

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.config import settings
from pao.modules.operations.checkpoint import entries,digest
from check_p84_foundation import binding

def main():
    candidate=ROOT/'.runtime/codex-login-candidate-20261019'
    assert ROOT==Path('F:/PAO-ACOS') and candidate.is_dir()
    before={'backend':{k:v for k,v in entries(ROOT).items() if k.startswith(('apps/api/','packages/cli-runtime/'))},'binding':binding(),'env':digest(ROOT/'.env')}
    cfg=settings();assert cfg.database_url.endswith(':15432/pao_acos_local')
    folder=ROOT/'.runtime'/('codex-login-tests-'+uuid4().hex);folder.mkdir()
    env={**os.environ,'PAO_ROOT':str(candidate),'DATABASE_URL':cfg.database_url.rsplit('/',1)[0]+'/pao_test',
        'PAO_TEST_DATABASE_URL':cfg.database_url.rsplit('/',1)[0]+'/pao_test',
        'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
        'PYTHONPATH':os.pathsep.join(map(str,(ROOT/'.runtime/p84-native-test-deps',candidate/'apps/api',candidate/'packages/cli-runtime',ROOT/'scripts'))),
        'JWT_SECRET':'synthetic-login-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
        'PYTHONDONTWRITEBYTECODE':'1','CLI_BROWSER_LOGIN_ENABLED':'false','PAO_ARQ_WALL_CLOCK_TESTS':'1'}
    container=subprocess.check_output(['docker','inspect','pao-acos-local-postgres-1','--format','{{.Id}}'],timeout=15).decode().strip()
    assert len(container)==64 and all(x in '0123456789abcdef' for x in container)
    env.update(PAO_WINDOWS_CANDIDATE_RESTORE='1',PAO_WINDOWS_CANDIDATE_PG_CONTAINER=container)
    full='--full' in sys.argv
    resume=Path(sys.argv[sys.argv.index('--resume-prefix')+1]).resolve() if '--resume-prefix' in sys.argv else None
    assert not (full and resume)
    if resume:assert resume.parent==ROOT/'.runtime' and resume.name.startswith('codex-login-tests-')
    if full:
        sys.path.insert(0,str(ROOT/'apps/api/tests'))
        from temporal_fixture import cached_binary
        cached=Path(cached_binary(ROOT));target=candidate/'.runtime/p62-temporal-bootstrap';target.mkdir(parents=True,exist_ok=True);shutil.copyfile(cached,target/cached.name)
    stages={
        'contract':[sys.executable,'-B','scripts/export_openapi.py'],
        'migration':[sys.executable,'-B','-m','alembic','upgrade','0072'],
        'schema':[sys.executable,'-B','-m','alembic','check'],
        'pytest':[sys.executable,'-B','-m','pytest','-q','--maxfail=1','-p','local_cycle_network_guard',
                  *(['-p','codex_login_resume_plugin'] if resume else []),
                  *(['apps/api/tests'] if full or resume else ['apps/api/tests/test_cli_login.py','apps/api/tests/test_cli_login_transport.py','apps/api/tests/test_cli_connections.py','apps/api/tests/test_app_factory.py']),
                  '--junitxml='+str(folder/'junit.xml')],
    }
    print(folder,flush=True)
    result={'pass':False,'full_backend_regression':full,'stages':[],'provider_calls':0,'primary_migrated':False}
    try:
        for name,command in stages.items():
            print(name,flush=True)
            if name=='pytest':
                if resume:
                    from codex_login_regression import prefix_manifest
                    with (folder/'restore-scope.log').open('xb') as output:
                        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/test_codex_login_restore_scope.py')],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=30)
                    collect=subprocess.run([sys.executable,'-B','-m','pytest','--collect-only','-q','apps/api/tests'],cwd=candidate,env=env,capture_output=True,text=True,encoding='utf-8',check=True,timeout=120)
                    (folder/'collection.log').write_text(collect.stdout,encoding='utf-8')
                    nodes=[line for line in collect.stdout.splitlines() if line.startswith('apps/api/tests/') and '::' in line]
                    assert len(nodes)==2356
                    manifest=prefix_manifest(resume,nodes,entries(candidate))
                    (folder/'resume-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
                    env['PAO_CODEX_LOGIN_RESUME']=str(folder/'resume-manifest.json')
                frozen={k:v for k,v in entries(candidate).items() if k.startswith(('apps/api/','packages/cli-runtime/','packages/contracts/','scripts/')) or k in ('requirements.lock','pyproject.toml','alembic.ini')}
                (folder/'test-input.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
            with (folder/(name+'.log')).open('xb') as output:
                done=subprocess.run(command,cwd=candidate,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=6000 if name=='pytest' and (full or resume) else 1200)
            if done.returncode:break
            result['stages'].append(name)
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        if (folder/'junit.xml').exists():
            for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
                for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        result.update(counts)
        after={'backend':{k:v for k,v in entries(ROOT).items() if k.startswith(('apps/api/','packages/cli-runtime/'))},'binding':binding(),'env':digest(ROOT/'.env')}
        result['primary_source_env_unchanged']=after==before
        result['candidate_source']=entries(candidate)
        result['candidate_unchanged_during_tests']={k:v for k,v in result['candidate_source'].items() if k.startswith(('apps/api/','packages/cli-runtime/','packages/contracts/','scripts/')) or k in ('requirements.lock','pyproject.toml','alembic.ini')}==locals().get('frozen')
        result['pass']=len(result['stages'])==len(stages) and counts['tests']>0 and not any(counts[k] for k in ('failures','errors','skipped')) and before==after and result['candidate_unchanged_during_tests']
    finally:
        (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='candidate_source'}),flush=True)
    raise SystemExit(0 if result['pass'] else 1)

if __name__=='__main__':
    from local_cycle_test_lock import isolated_test_slot
    with isolated_test_slot():main()
