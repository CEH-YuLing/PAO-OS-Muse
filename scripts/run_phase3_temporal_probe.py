"""Read-only frozen-image diagnosis using a fresh UUID test DB/Redis only."""
import asyncio,json,re,subprocess,time
from pathlib import Path
from uuid import uuid4
from pao.config import ROOT,settings
from sqlalchemy.engine import make_url
from check_p11_migration import snapshot

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    url=make_url(settings().database_url)
    assert url.host=='127.0.0.1' and url.port==15432 and url.database=='pao_acos_local'
    rid=uuid4().hex;folder=ROOT/'.runtime'/('phase3-temporal-probe-'+rid);folder.mkdir()
    image='pao-s6-linux:baca7f8b6cb54f6ba5acbe7d9d578cc7'
    def docker(*args):return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,encoding='utf-8',timeout=90).stdout.strip()
    assert docker('image','inspect',image,'--format','{{index .Config.Labels "pao.s6.runid"}}')=='baca7f8b6cb54f6ba5acbe7d9d578cc7'
    before=asyncio.run(snapshot(url));(folder/'primary-before.json').write_text(json.dumps(before),encoding='utf-8')
    owned=[];result={'pass':False,'run_id':rid,'primary_repair_attempted':False}
    def create(*args):
        cid=docker(*args);assert re.fullmatch('[a-f0-9]{64}',cid);owned.append(cid);return cid
    try:
        db=create('run','-d','--label','pao.phase3.probe='+rid,'--memory','512m','-e','POSTGRES_USER=pao','-e','POSTGRES_PASSWORD=synthetic-probe-only','-e','POSTGRES_DB=pao_test','pgvector/pgvector:pg17')
        create('run','-d','--label','pao.phase3.probe='+rid,'--memory','128m','--network','container:'+db,'redis:7.4-alpine')
        for _ in range(40):
            if subprocess.run(['docker','exec',db,'pg_isready','-U','pao','-d','pao_test'],capture_output=True).returncode==0:break
            time.sleep(.5)
        else:raise RuntimeError('test_database_not_ready')
        code="import subprocess,sys; p=sys.executable; subprocess.run([p,'scripts/bootstrap_temporal_test.py'],check=True); subprocess.run([p,'-m','alembic','upgrade','head'],check=True); [subprocess.run([p,'-m','pytest','-q','apps/api/tests/test_studio_connection_recovery.py','--junitxml=.runtime/probe-'+str(i)+'.xml'],check=True) for i in range(3)]"
        args=['create','--label','pao.phase3.probe='+rid,'--memory','4g','--cpus','4','--tmpfs','/tmp:rw,nosuid,size=384m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges','--network','container:'+db,
              '-e','DATABASE_URL=postgresql+asyncpg://pao:synthetic-probe-only@127.0.0.1:5432/pao_test','-e','PAO_TEST_DATABASE_URL=postgresql+asyncpg://pao:synthetic-probe-only@127.0.0.1:5432/pao_test','-e','REDIS_URL=redis://127.0.0.1:6379/15','-e','JWT_SECRET=synthetic-probe-only-key-000000000000000000000000',
              '-e','PAO_LINUX_LOCAL_RESTORE=1','-e','META_ENABLED=false','-e','META_WRITE_ENABLED=false','-e','GOOGLE_ADS_ENABLED=false','-e','TELEGRAM_ENABLED=false','--entrypoint','python',image,'-c',code]
        runner=create(*args)
        print(json.dumps({'stage':'focused-probe','run_id':rid,'folder':str(folder)}),flush=True)
        with (folder/'runner.log').open('wb') as log:
            process=subprocess.Popen(['docker','start','-a',runner],stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(30):
                    try:result['pass']=process.wait(timeout=30)==0;break
                    except subprocess.TimeoutExpired:print('Focused native Temporal probe still running.',flush=True)
                else:raise RuntimeError('focused_probe_timeout')
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=10)
        for i in range(3):subprocess.run(['docker','cp',runner+':/workspace/.runtime/probe-'+str(i)+'.xml',str(folder)],capture_output=True)
    finally:
        for cid in reversed(owned):
            assert docker('inspect',cid,'--format','{{index .Config.Labels "pao.phase3.probe"}}')==rid
            docker('rm','-f','-v',cid)
        after=asyncio.run(snapshot(url));(folder/'primary-after.json').write_text(json.dumps(after),encoding='utf-8')
        result.update(owned_containers_removed=True,primary_unchanged=before==after)
        (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
    if not result['pass']:raise SystemExit(1)

if __name__=='__main__':main()
