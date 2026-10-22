"""S5 source verification; migrates pao_test only, never the primary."""
import os,subprocess,sys
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings

if __name__=='__main__':
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    test=url.set(database='pao_test').render_as_string(hide_password=False)
    env={**os.environ,'DATABASE_URL':test,'PAO_TEST_DATABASE_URL':test,
        'REDIS_URL':urlunsplit(urlsplit(settings().redis_url)._replace(path='/15')),'BUSINESS_PLANNING_ENABLED':'false','PYTHONUTF8':'1'}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0070'],cwd=ROOT,env=env,check=True,timeout=120)
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
    targets=sys.argv[1:] or ['apps/api/tests/test_business_planning.py']
    full=targets==['apps/api/tests']
    if full:env['PAO_ARQ_WALL_CLOCK_TESTS']='1'
    from pao.skills import execution_binding,_execution_digest
    binding=execution_binding()
    report='.runtime/s5-full.xml' if full else '.runtime/s5-focused.xml'
    code=subprocess.run([sys.executable,'-m','pytest',*targets,'-q','--tb=line','-o','faulthandler_timeout=180','--junitxml='+report],cwd=ROOT,env=env).returncode
    if full:
        import json,xml.etree.ElementTree as ET
        suite=ET.parse(ROOT/report).getroot().find('testsuite')
        unchanged=_execution_digest()==binding['sha256']
        result={'pass':code==0 and unchanged,'binding_unchanged':unchanged,
            'binding':binding,**{key:int(suite.get(key,'0')) for key in ('tests','failures','errors','skipped')}}
        (ROOT/'.runtime/s5-backend.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    raise SystemExit(code)
