"""Operator verification only: literal pao_test/Redis15, serial, no providers."""
import argparse,json,os,secrets,shutil,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from xml.etree import ElementTree
from cryptography.fernet import Fernet

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.config import settings
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import frontend_supplements
from local_cycle_test_lock import isolated_test_slot

def main(stage):
    assert ROOT==Path('F:/PAO-ACOS')
    candidate=ROOT/'.runtime/enterprise-ai-20261019/source'
    assert candidate.is_dir() and not candidate.is_symlink()
    cfg=settings();assert cfg.database_url.endswith(':15432/pao_acos_local')
    folder=ROOT/'.runtime'/('enterprise-ai-check-'+uuid4().hex);folder.mkdir()
    for name in frontend_supplements(ROOT):
        target=candidate/name
        if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    before=entries(ROOT);env_hash=digest(ROOT/'.env');source=entries(candidate)
    env={**os.environ,'PAO_ROOT':str(candidate),'DATABASE_URL':cfg.database_url.rsplit('/',1)[0]+'/pao_test',
        'PAO_TEST_DATABASE_URL':cfg.database_url.rsplit('/',1)[0]+'/pao_test',
        'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
        'JWT_SECRET':'synthetic-enterprise-'+secrets.token_hex(24),
        'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
        'PYTHONPATH':os.pathsep.join(map(str,[ROOT/'.runtime/p84-native-test-deps',candidate/'apps/api',candidate/'packages/cli-runtime',ROOT/'scripts'])),
        'PYTHONDONTWRITEBYTECODE':'1','NEXT_TELEMETRY_DISABLED':'1','PAO_BUILD_CHECK':'1'}
    counts={};stages=[];result={'pass':False,'provider_calls':0,'primary_migrated':False,'candidate':str(candidate)}
    def run(name,args,timeout=180):
        print(name,flush=True)
        with (folder/(name+'.log')).open('xb') as log:
            subprocess.run(args,cwd=candidate,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=timeout)
        stages.append(name)
    try:
        if stage=='backend':
            with isolated_test_slot():
                run('migration',[sys.executable,'-B','-m','alembic','upgrade','0073'])
                run('schema',[sys.executable,'-B','-m','alembic','check'])
                files=['test_enterprise_ai.py','test_cli_connections.py','test_model_grant_activation.py',
                    'test_model_connection_fence.py','test_engine_contract.py','test_chat_management.py',
                    'test_tenant_model_resources.py','test_integration.py','test_brain_manager.py','test_business_routing.py',
                    'test_business_operations.py','test_s62_lifecycle.py','test_organization_catalog.py']
                files=[str(candidate/'apps/api/tests'/f) for f in files]
                assert all(Path(f).is_file() for f in files)
                run('pytest',[sys.executable,'-B','-m','pytest','-q','--maxfail=1','-p','local_cycle_network_guard',
                    *files,'--junitxml='+str(folder/'junit.xml')],1800)
                counts={k:sum(int(s.attrib.get(k,0)) for s in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite')) for k in ('tests','failures','errors','skipped')}
                assert counts['tests'] and not any(counts[k] for k in ('failures','errors','skipped'))
        else:
            node=shutil.which('node');assert node
            modules=ROOT/'node_modules'
            run('contracts-export',[sys.executable,'-B','scripts/export_openapi.py'])
            run('contracts',[node,str(modules/'openapi-typescript/bin/cli.js'),'packages/contracts/openapi.json','-o','packages/contracts/schema.d.ts'])
            run('node',[node,'--test',*[str(p.relative_to(candidate)) for p in sorted((candidate/'apps/web/lib').glob('*.test.mjs'))]])
            run('typegen',[node,str(modules/'next/dist/bin/next'),'typegen','apps/web'])
            run('typecheck',[node,str(modules/'typescript/bin/tsc'),'--noEmit','-p','apps/web/tsconfig.json'])
            run('build',[node,str(modules/'next/dist/bin/next'),'build','apps/web'],600)
        assert entries(ROOT)==before and digest(ROOT/'.env')==env_hash
        result.update({'pass':True,'stages':stages,'counts':counts,'primary_source_env_unchanged':True,
                       'candidate_schema':'0073','source_before':source,'source_after':entries(candidate)})
    finally:
        (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**{k:v for k,v in result.items() if not k.startswith('source_')}}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['backend','frontend']);main(p.parse_args().stage)
