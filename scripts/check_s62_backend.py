"""Full S6.2 regression on pao_test/Redis15; keep every attempt separately."""
import json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from xml.etree import ElementTree
sys.path[:0]=['F:/PAO-ACOS/apps/api','F:/PAO-ACOS/scripts']
from pao.config import ROOT,settings
from pao.skills import execution_binding,_execution_digest
from sqlalchemy.engine import make_url

config=settings()
assert ROOT.resolve()==Path('F:/PAO-ACOS') and config.database_url.endswith('/pao_acos_local')
configured=make_url(config.database_url)
assert configured.host=='127.0.0.1' and configured.port==15432 and configured.username=='pao'
url=config.database_url.rsplit('/',1)[0]+'/pao_test';redis=urlsplit(config.redis_url)
env={**os.environ,'PAO_ROOT':str(ROOT),'PYTHONPATH':str(ROOT/'apps/api'),
    'DATABASE_URL':url,'PAO_TEST_DATABASE_URL':url,
    'REDIS_URL':urlunsplit((redis.scheme,redis.netloc,'/15','','')),'PAO_ARQ_WALL_CLOCK_TESTS':'1'}
folder=ROOT/'.runtime'/('s62-full-'+uuid4().hex);folder.mkdir()
binding=execution_binding()
subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=ROOT,env=env,check=True)
subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True)
with (folder/'pytest.log').open('w',encoding='utf-8') as log:
    result=subprocess.run([sys.executable,'-m','pytest','-q','apps/api/tests','--junitxml='+str(folder/'junit.xml')],
                          cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
counts={'tests':0,'failures':0,'errors':0,'skipped':0}
if (folder/'junit.xml').exists():
    for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
        for key in counts:counts[key]+=int(suite.attrib.get(key,0))
receipt={**counts,'binding':binding,'binding_unchanged':_execution_digest()==binding['sha256'],
    'returncode':result.returncode,'evidence':str(folder),'fail_fast':False,
    'full_suite_requested':True,'provider_calls':False,'primary_migration':False}
receipt['pass']=result.returncode==0 and receipt['binding_unchanged'] and counts['tests']>=2258 and all(counts[k]==0 for k in ('failures','errors','skipped'))
(folder/'result.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
(ROOT/'.runtime/s62-backend.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt))
raise SystemExit(0 if receipt['pass'] else 1)
