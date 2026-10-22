"""Native Windows candidate regression with isolated published-loopback test DBs."""
import asyncio,hashlib,json,os,re,socket,subprocess,time
from pathlib import Path
from uuid import uuid4
from pao.config import ROOT,settings
from check_p11_migration import snapshot

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    candidate=Path('F:/Apex/phase3-candidate');py=candidate/'.runtime/backend-security-venv/Scripts/python.exe'
    assert py.is_file()
    for port in (15435,16381):
        with socket.socket() as s:assert s.connect_ex(('127.0.0.1',port))!=0,'Test port occupied'
    rid=uuid4().hex;folder=ROOT/'.runtime'/('phase3-windows-security-'+rid);folder.mkdir()
    before=asyncio.run(snapshot(settings().database_url));owned=[]
    result={'pass':False,'run_id':rid,'provider_calls':False,'production_accepted':False}
    def docker(*args):return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,timeout=90).stdout.strip()
    def create(*args):
        cid=docker('run','-d','--label','pao.phase3.windows='+rid,*args);assert re.fullmatch('[0-9a-f]{64}',cid);owned.append(cid);return cid
    try:
        pg=create('--memory','512m','-p','127.0.0.1:15435:5432','-e','POSTGRES_USER=pao','-e','POSTGRES_PASSWORD=synthetic-windows-only','-e','POSTGRES_DB=pao_test','pgvector/pgvector:pg17')
        create('--memory','128m','-p','127.0.0.1:16381:6379','redis:7.4-alpine')
        for _ in range(50):
            if subprocess.run(['docker','exec',pg,'pg_isready','-U','pao','-d','pao_test'],capture_output=True).returncode==0:break
            time.sleep(.3)
        else:raise RuntimeError('windows_probe_db_not_ready')
        url='postgresql+asyncpg://pao:synthetic-windows-only@127.0.0.1:15435/pao_test'
        env={**os.environ,'PAO_ROOT':str(candidate),'PYTHONPATH':str(candidate/'apps/api')+os.pathsep+str(candidate/'scripts'),
             'DATABASE_URL':url,'PAO_TEST_DATABASE_URL':url,'REDIS_URL':'redis://127.0.0.1:16381/15',
             'JWT_SECRET':'synthetic-windows-probe-only-'+'0'*48,'INTEGRATION_ENCRYPTION_KEY':'',
             'META_ENABLED':'false','META_WRITE_ENABLED':'false','GOOGLE_ADS_ENABLED':'false','TELEGRAM_ENABLED':'false'}
        def run(name,*args):
            with (folder/(name+'.log')).open('wb') as output:
                subprocess.run([str(py),*args],cwd=candidate,env=env,stdout=output,stderr=subprocess.STDOUT,check=True,timeout=600)
        run('pip-check','-m','pip','check')
        run('crypto-compat','scripts/test_phase3_crypto_compat.py')
        run('schema','-m','alembic','upgrade','head')
        targets=['test_integration.py','test_s62_lifecycle.py','test_s62_metadata_revocation.py','test_model_router.py',
                 'test_meta_app_settings.py','test_meta.py','test_google_ads.py','test_skill_artifacts.py','test_skill_version_guard.py']
        run('focused','-m','pytest','-q','-p','phase3_network_guard',*['apps/api/tests/'+n for n in targets],
            '--junitxml='+str(folder/'focused.xml'))
        from xml.etree import ElementTree as ET
        suite=ET.parse(folder/'focused.xml').getroot().find('testsuite')
        counts={k:int(suite.get(k,'0')) for k in ('tests','failures','errors','skipped')}
        assert counts['tests']>50 and counts['failures']==counts['errors']==counts['skipped']==0
        result.update(pass_=True,backend=counts,network_guard=True,crypto_compatibility=True,
            requirements_sha256=hashlib.sha256((candidate/'requirements.lock').read_bytes()).hexdigest(),
            crypto_compat_source_sha256=hashlib.sha256((candidate/'scripts/test_phase3_crypto_compat.py').read_bytes()).hexdigest())
        result['pass']=result.pop('pass_')
    finally:
        for cid in reversed(owned):
            assert docker('inspect',cid,'--format','{{index .Config.Labels "pao.phase3.windows"}}')==rid
            docker('rm','-f','-v',cid)
        after=asyncio.run(snapshot(settings().database_url));result.update(primary_unchanged=before==after,owned_resources_removed=True)
        (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({**result,'evidence':str(folder)}),flush=True)
    if not result['pass']:raise SystemExit(1)

if __name__=='__main__':main()
