"""Focused local catalog/API regression; native CLI mocked in tests, no model."""
import asyncio,json,os,secrets,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from xml.etree import ElementTree
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from local_cycle_test_lock import isolated_test_slot
from check_pao_mcp_local import digests
from check_p84_foundation import primary_schema,health,binding
from pao.config import settings

def main():
    cfg=settings();pg=urlsplit(cfg.database_url)
    assert ROOT==Path('F:/PAO-ACOS') and (pg.hostname,pg.port,pg.path)==('127.0.0.1',15432,'/pao_acos_local')
    folder=ROOT/'.runtime'/('antigravity-native-tests-'+uuid4().hex);folder.mkdir()
    before=digests();schema=asyncio.run(primary_schema())
    state={'pass':False,'provider_calls':0,'inference_called':False,'schema_before':schema,'binding':binding()}
    env={**os.environ,'DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
         'PAO_TEST_DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
         'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
         'JWT_SECRET':'synthetic-native-'+secrets.token_hex(24),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1',
         'PYTHONPATH':os.pathsep.join(str(ROOT/p) for p in ('.runtime/p84-native-test-deps','apps/api','packages/cli-runtime','scripts'))}
    try:
        files=['test_antigravity_native.py','test_antigravity_smoke.py','test_cli_models.py','test_cli_login.py','test_personal_cli.py','test_mcp_readonly_bridge.py']
        with (folder/'pytest.log').open('wb') as log:
            run=subprocess.run([sys.executable,'-B','-m','pytest','-q','--maxfail=1','-p','local_cycle_network_guard',
                *['apps/api/tests/'+p for p in files],'--junitxml='+str(folder/'junit.xml')],cwd=ROOT,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=600)
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
            for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        state['counts']=counts
        state['pass']=run.returncode==0 and counts['tests']>=17 and not any(counts[k] for k in ('failures','errors','skipped'))
        state['health']=health()
    finally:
        state.update(source_env_pins_unchanged=before==digests(),schema_after=asyncio.run(primary_schema()))
        state['pass']=state['pass'] and state['source_env_pins_unchanged'] and state['schema_after']==schema
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(state,out,indent=2)
        print(json.dumps({'folder':str(folder),**state}))
    raise SystemExit(0 if state['pass'] else 1)

if __name__=='__main__':
    with isolated_test_slot():main()
