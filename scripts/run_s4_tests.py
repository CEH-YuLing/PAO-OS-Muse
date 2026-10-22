"""Run sequential tests only against the dedicated pao_test database."""
import json,os,subprocess,sys
from sqlalchemy.engine import make_url
from urllib.parse import urlsplit,urlunsplit
from pao.config import ROOT,settings
from pao.skills import execution_binding

if __name__=='__main__':
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    env={**os.environ,'DATABASE_URL':url.set(database='pao_test').render_as_string(hide_password=False),
        'PAO_TEST_DATABASE_URL':url.set(database='pao_test').render_as_string(hide_password=False),
        'REDIS_URL':urlunsplit(urlsplit(settings().redis_url)._replace(path='/15')),'PYTHONUTF8':'1'}
    subprocess.run([sys.executable,'-m','alembic','upgrade','0065'],cwd=ROOT,env=env,check=True,timeout=120)
    args=sys.argv[1:] or ['apps/api/tests/test_ads_tenant_apps.py','apps/api/tests/test_meta.py','apps/api/tests/test_google_ads.py']
    full=args==['apps/api/tests']
    if full:env['PAO_ARQ_WALL_CLOCK_TESTS']='1'
    report='.runtime/s4-full.xml' if full else '.runtime/s4-focused.xml'
    if args==['apps/api/tests/test_telegram_reports.py']:report='.runtime/s4-report-fixture.xml'
    if 'apps/api/tests/test_reconciliation.py' in args:report='.runtime/s4-recovery.xml'
    elif 'apps/api/tests/test_analysis_tools.py' in args:report='.runtime/s4-fixture-callers.xml'
    binding=execution_binding()
    if full:(ROOT/'.runtime/s4-test-binding.json').write_text(json.dumps(binding),encoding='utf-8')
    code=subprocess.run([sys.executable,'-m','pytest',*args,'-q','--tb=short','-o','faulthandler_timeout=180','--junitxml='+report],cwd=ROOT,env=env).returncode
    if full:
        import xml.etree.ElementTree as ET
        suite=ET.parse(ROOT/report).getroot().find('testsuite')
        result={'pass':code==0 and execution_binding()==binding,'binding_unchanged':execution_binding()==binding,
            'binding':binding,**{key:int(suite.get(key,'0')) for key in ('tests','failures','errors','skipped')}}
        (ROOT/'.runtime/s4-backend.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
        if not result['pass']:code=1
    raise SystemExit(code)
