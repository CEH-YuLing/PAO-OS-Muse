"""Focused native task regression on pao_test, with primary/source guards."""
import asyncio,json,os,secrets,subprocess,sys
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from urllib.parse import urlsplit,urlunsplit
from cryptography.fernet import Fernet
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import entries,digest
from check_p11_migration import snapshot

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    candidate=Path('F:/Apex/task-delete-candidate');cfg=settings()
    assert cfg.database_url.endswith('/pao_acos_local')
    before=asyncio.run(snapshot(cfg.database_url));environment=digest(ROOT/'.env')
    folder=candidate/'.runtime'/('backend-'+uuid4().hex);folder.mkdir()
    (folder/'primary-before.json').write_text(json.dumps(before),encoding='utf-8')
    def tested_source():
        return {n:h for n,h in entries(candidate).items() if n.startswith('apps/api/') or n in ('requirements.lock','requirements-dev.lock')}
    source=tested_source();target=cfg.database_url.rsplit('/',1)[0]+'/pao_test'
    env={**os.environ,'PAO_ROOT':str(candidate),'PYTHONPATH':str(candidate/'apps/api')+os.pathsep+str(ROOT/'scripts'),
         'DATABASE_URL':target,'PAO_TEST_DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
         'JWT_SECRET':'synthetic-delete-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
         'PAO_ARQ_WALL_CLOCK_TESTS':'1'}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=candidate,env=env,check=True,timeout=120)
    tests=['test_task_deletion.py','test_tasks.py','test_task_domain_characterization.py','test_task_values_boundary.py',
           'test_goal_projection.py','test_goal_first_projection.py','test_business_events.py','test_unified_approvals.py','test_business_plan_review.py',
           'test_business_operations.py','test_business_planning.py','test_s62_lifecycle.py','test_app_factory.py']
    tests=[str(candidate/'apps/api/tests'/name) for name in tests if (candidate/'apps/api/tests'/name).exists()]
    with (folder/'pytest.log').open('wb') as log:
        result=subprocess.run([sys.executable,'-m','pytest','-q','-p','local_cycle_network_guard',*tests,
             '--junitxml='+str(folder/'junit.xml')],cwd=candidate,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    counts={k:0 for k in ('tests','failures','errors','skipped')}
    if (folder/'junit.xml').exists():
        for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
            for k in counts:counts[k]+=int(suite.attrib.get(k,0))
    unchanged=before==asyncio.run(snapshot(cfg.database_url)) and environment==digest(ROOT/'.env')
    receipt={**counts,'pass':result.returncode==0 and counts['tests']>0 and not any(counts[k] for k in ('failures','errors','skipped')) and unchanged and source==tested_source(),
             'primary_environment_unchanged':unchanged,'source_unchanged':source==tested_source(),'tested_source':source,'full_regression':False}
    (folder/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(str(folder));print(json.dumps(receipt))
    raise SystemExit(0 if receipt['pass'] else 1)

if __name__=='__main__':
    from local_cycle_test_lock import isolated_test_slot
    with isolated_test_slot():main()
