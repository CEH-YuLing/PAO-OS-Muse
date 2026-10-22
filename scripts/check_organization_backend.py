"""Focused existing business regression; never points tests at the primary DB."""
import asyncio,json,os,subprocess,sys,secrets
from cryptography.fernet import Fernet
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from xml.etree import ElementTree
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from pao.modules.operations.checkpoint import entries
from check_p11_migration import snapshot

def main():
 cfg=settings();assert ROOT.resolve()==Path('F:/PAO-ACOS') and cfg.database_url.endswith('/pao_acos_local')
 assert sys.version_info[:3]==(3,12,14)
 for filename in ('requirements.lock','requirements-dev.lock'):
  for line in (ROOT/filename).read_text().splitlines():
   if '==' in line and not line.startswith(('#','-')):
    name,locked=line.split('==',1);assert version(name.strip())==locked.strip(), 'Test dependency differs from lock: '+name
 before=asyncio.run(snapshot(cfg.database_url));binding=execution_binding();environment=digest(ROOT/'.env')
 candidate=Path('F:/Apex/enterprise-knowledge-candidate');assert candidate.is_dir()
 folder=ROOT/'.runtime'/('organization-focused-'+uuid4().hex);folder.mkdir()
 target=cfg.database_url.rsplit('/',1)[0]+'/pao_test'
 env={**os.environ,'PAO_ROOT':str(candidate),'PYTHONPATH':str(candidate/'apps/api'),
  'DATABASE_URL':target,'PAO_TEST_DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),'PAO_ARQ_WALL_CLOCK_TESTS':'1',
  'JWT_SECRET':'synthetic-organization-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode()}
 (folder/'primary-before.json').write_text(json.dumps(before),encoding='utf-8')
 tested_files={n:h for n,h in entries(candidate).items() if n.startswith(('apps/api/','packages/contracts/')) or n in ('requirements.lock','requirements-dev.lock')}
 def tested_binding():
  result=subprocess.run([sys.executable,'-c','import json;from pao.skills import execution_binding;print(json.dumps(execution_binding()))'],cwd=candidate,env=env,check=True,capture_output=True,text=True,timeout=30)
  return json.loads(result.stdout)
 candidate_binding=tested_binding()
 subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=candidate,env=env,check=True,timeout=120)
 tests=['test_organization_catalog.py','test_studio.py','test_s62_lifecycle.py','test_app_factory.py','test_business_planning.py','test_business_plan_review.py','test_business_routing.py','test_business_operations.py']
 assert all((candidate/'apps/api/tests'/n).exists() for n in tests)
 with (folder/'pytest.log').open('wb') as log:
  env['PYTHONPATH']+=os.pathsep+str(Path(__file__).resolve().parent)
  result=subprocess.run([sys.executable,'-m','pytest','-q','-p','local_cycle_network_guard',*[str(candidate/'apps/api/tests'/n) for n in tests],'--junitxml='+str(folder/'junit.xml')],cwd=candidate,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
 counts={k:0 for k in ('tests','failures','errors','skipped')}
 if (folder/'junit.xml').exists():
  for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
   for k in counts:counts[k]+=int(suite.attrib.get(k,0))
 source_same=tested_files=={n:h for n,h in entries(candidate).items() if n.startswith(('apps/api/','packages/contracts/')) or n in ('requirements.lock','requirements-dev.lock')} and candidate_binding==tested_binding()
 unchanged=before==asyncio.run(snapshot(cfg.database_url)) and binding==execution_binding() and environment==digest(ROOT/'.env')
 receipt={**counts,'pass':result.returncode==0 and counts['tests']>0 and not any(counts[k] for k in ('failures','errors','skipped')) and unchanged and source_same,'tested_binding':candidate_binding,'tested_files':tested_files,'candidate_source_unchanged':source_same,
  'binding':binding,'primary_env_backend_unchanged':unchanged,'full_backend_regression':False,'evidence':str(folder)}
 (folder/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 print(json.dumps(receipt));raise SystemExit(0 if receipt['pass'] else 1)
if __name__=='__main__':
 from local_cycle_test_lock import isolated_test_slot
 with isolated_test_slot():main()
