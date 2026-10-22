"""Focused existing business regression; never points tests at the primary DB."""
import asyncio,json,os,subprocess,sys
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from xml.etree import ElementTree
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot

def main():
 cfg=settings();assert ROOT.resolve()==Path('F:/PAO-ACOS') and cfg.database_url.endswith('/pao_acos_local')
 assert sys.version_info[:3]==(3,12,14)
 for filename in ('requirements.lock','requirements-dev.lock'):
  for line in (ROOT/filename).read_text().splitlines():
   if '==' in line and not line.startswith(('#','-')):
    name,locked=line.split('==',1);assert version(name.strip())==locked.strip(), 'Test dependency differs from lock: '+name
 before=asyncio.run(snapshot(cfg.database_url));binding=execution_binding();environment=digest(ROOT/'.env')
 folder=ROOT/'.runtime'/('local-cycle-focused-'+uuid4().hex);folder.mkdir()
 target=cfg.database_url.rsplit('/',1)[0]+'/pao_test'
 env={**os.environ,'PAO_ROOT':str(ROOT),'PYTHONPATH':str(ROOT/'apps/api'),
  'DATABASE_URL':target,'PAO_TEST_DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),'PAO_ARQ_WALL_CLOCK_TESTS':'1'}
 subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=ROOT,env=env,check=True,timeout=120)
 tests=['test_business_planning.py','test_business_plan_review.py','test_business_routing.py','test_business_operations.py']
 with (folder/'pytest.log').open('wb') as log:
  env['PYTHONPATH']+=os.pathsep+str(Path(__file__).resolve().parent)
  result=subprocess.run([sys.executable,'-m','pytest','-q','-p','local_cycle_network_guard',*[str(ROOT/'apps/api/tests'/n) for n in tests],'--junitxml='+str(folder/'junit.xml')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
 counts={k:0 for k in ('tests','failures','errors','skipped')}
 if (folder/'junit.xml').exists():
  for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
   for k in counts:counts[k]+=int(suite.attrib.get(k,0))
 unchanged=before==asyncio.run(snapshot(cfg.database_url)) and binding==execution_binding() and environment==digest(ROOT/'.env')
 receipt={**counts,'pass':result.returncode==0 and counts['tests']>0 and not any(counts[k] for k in ('failures','errors','skipped')) and unchanged,
  'binding':binding,'primary_env_backend_unchanged':unchanged,'full_backend_regression':False,'evidence':str(folder)}
 (folder/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 print(json.dumps(receipt));raise SystemExit(0 if receipt['pass'] else 1)
if __name__=='__main__':
 from local_cycle_test_lock import isolated_test_slot
 with isolated_test_slot():main()
