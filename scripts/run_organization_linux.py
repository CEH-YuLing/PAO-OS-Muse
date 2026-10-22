"""Disposable Linux full regression using source-only ZIP and isolated services.

No host ports, host bind mounts, Docker socket, production credentials or data.
Retains logs/source evidence; removes only UUID-labelled containers it created.
"""
import asyncio,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.modules.operations.checkpoint import digest
from backup_acos_checkpoint import source_archive
from check_p11_migration import snapshot


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',action='store_true');options=parser.parse_args()
    source_root=Path('F:/Apex/enterprise-knowledge-candidate');assert options.candidate
    assert source_root.is_dir() and not source_root.is_symlink() and not source_root.is_junction()
    config=settings();url=make_url(config.database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    before=asyncio.run(snapshot(url));env_hash=digest(ROOT/'.env')
    rid=uuid4().hex;folder=ROOT/'.runtime'/('s6-linux-'+rid);folder.mkdir()
    (folder/'primary-before.json').write_text(json.dumps(before),encoding='utf-8')
    files=source_archive(source_root,folder/'source.zip')
    shutil.copy2(source_root/'infra/s6-linux.Dockerfile',folder/'Dockerfile')
    for name in ('requirements.lock','requirements-dev.lock','package.json','package-lock.json'):shutil.copy2(source_root/name,folder/name)
    shutil.copy2(source_root/'apps/web/package.json',folder/'web.package.json')
    image='pao-s6-linux:'+rid;db='pao-s6-db-'+rid;redis='pao-s6-redis-'+rid;runner='pao-s6-runner-'+rid
    owned=[];result={'run_id':rid,'folder':str(folder),'pass':False,'linux_execution':False,
        'github_remote_executed':False,'production_accepted':False,'provider_calls':False,'source_root':str(source_root)}
    def docker(*args, timeout=90):
        return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,timeout=timeout).stdout.strip()
    def create(*args):
        cid=docker(*args);assert re.fullmatch('[a-f0-9]{64}',cid);owned.append(cid);return cid
    def logged(args,name,limit):
        with (folder/name).open('wb') as log:
            process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            start=time.monotonic()
            try:
                while True:
                    try:
                        code=process.wait(timeout=40)
                        if code:raise RuntimeError('isolated_stage_failed:'+name)
                        return
                    except subprocess.TimeoutExpired:
                        print(json.dumps({'stage':name,'elapsed_seconds':int(time.monotonic()-start),'evidence':str(folder/name)}),flush=True)
                        if time.monotonic()-start>limit:raise RuntimeError('isolated_stage_timeout:'+name)
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=15)
    try:
        print(json.dumps({'stage':'source_pack_verified','files':len(files),'source_sha256':digest(folder/'source.zip'),'run_id':rid}),flush=True)
        logged(['docker','build','--label','pao.s6.runid='+rid,'-t',image,str(folder)],'build.log',1200)
        print('Linux runner image built; starting isolated test services.',flush=True)
        create('run','-d','--name',db,'--label','pao.s6.runid='+rid,'--memory','512m',
            '-e','POSTGRES_USER=pao','-e','POSTGRES_PASSWORD=synthetic-s6-only','-e','POSTGRES_DB=pao_test','pgvector/pgvector:pg17')
        create('run','-d','--name',redis,'--label','pao.s6.runid='+rid,'--memory','128m','--network','container:'+db,'redis:7.4-alpine')
        for attempt in range(40):
            check=subprocess.run(['docker','exec',db,'pg_isready','-U','pao','-d','pao_test'],capture_output=True,timeout=5)
            if check.returncode==0:break
            time.sleep(.5)
        else:raise RuntimeError('test_postgres_not_ready')
        values={'DATABASE_URL':'postgresql+asyncpg://pao:synthetic-s6-only@127.0.0.1:5432/pao_test',
            'PAO_TEST_DATABASE_URL':'postgresql+asyncpg://pao:synthetic-s6-only@127.0.0.1:5432/pao_test',
            'REDIS_URL':'redis://127.0.0.1:6379/15','JWT_SECRET':'synthetic-linux-ci-only-key-not-production-0001',
            'PAO_ARQ_WALL_CLOCK_TESTS':'1','PAO_S6_LINUX_RUN':rid,'PAO_LINUX_LOCAL_RESTORE':'1',
            'PYTEST_ADDOPTS':'--maxfail=1',
            'INTEGRATION_ENCRYPTION_KEY':'','BUSINESS_PLANNING_ENABLED':'false',
            **{key:'false' for key in ('META_ENABLED','META_WRITE_ENABLED','GOOGLE_ADS_ENABLED','TELEGRAM_ENABLED',
                'TELEGRAM_SCOPED_RUNTIME_ENABLED','TEMPORAL_ENABLED','ADS_AUTOPILOT_GLOBAL_ENABLED','META_AUTOPILOT_ENABLED','META_INSTALLATION_CONFIG_ENABLED')}}
        args=['create','--name',runner,'--label','pao.s6.runid='+rid,'--memory','4g','--cpus','4',
            '--tmpfs','/tmp:rw,nosuid,size=384m,mode=1777',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--network','container:'+db]
        for key,value in values.items():args.extend(['-e',key+'='+value])
        create(*args,image)
        try:
            result['linux_execution']=True
            logged(['docker','start','-a',runner],'runner.log',4500)
        finally:
            for artifact in ('backend-full.xml','s6-linux-result.json','ci-result.json','js-security.json','python-security.json'):
                subprocess.run(['docker','cp',runner+':/workspace/.runtime/'+artifact,str(folder/artifact)],capture_output=True,timeout=30)
        outcome=json.loads((folder/'s6-linux-result.json').read_text(encoding='utf-8'))
        assert outcome['pass'] is True and outcome['linux_execution'] is True and outcome['run_id']==rid
        import xml.etree.ElementTree as ET
        suite=ET.parse(folder/'backend-full.xml').getroot().find('testsuite')
        counts={key:int(suite.get(key,'0')) for key in ('tests','failures','errors','skipped')}
        assert counts['tests']>=2258 and counts['failures']==counts['errors']==counts['skipped']==0
        result.update({'pass':True,'linux_execution':True,'backend':counts,'source_sha256':digest(folder/'source.zip'),
            'dockerfile_sha256':digest(folder/'Dockerfile'),'image_id':docker('image','inspect',image,'--format','{{.Id}}'),
            'python':outcome['python'],'node_and_typecheck_and_build':True})
    finally:
        for cid in reversed(owned):
            label=docker('inspect',cid,'--format','{{index .Config.Labels "pao.s6.runid"}}')
            if label!=rid:raise RuntimeError('owned_container_identity_changed')
            docker('rm','-f','-v',cid)
        after=asyncio.run(snapshot(url))
        (folder/'primary-after.json').write_text(json.dumps(after),encoding='utf-8')
        result['primary_unchanged']=after==before
        result['primary_changed_tables']=[name for name in sorted(set(before[1])|set(after[1])) if before[1].get(name)!=after[1].get(name)]
        result['primary_drift_cause']='not_confirmed' if before!=after else None
        result['env_unchanged']=digest(ROOT/'.env')==env_hash
        result['owned_containers_removed']=True
        result['pass']=result['pass'] and result['primary_unchanged'] and result['env_unchanged']
        if (folder/'backend-full.xml').is_file():
            import xml.etree.ElementTree as ET
            suite=ET.parse(folder/'backend-full.xml').getroot().find('testsuite')
            result['backend']={key:int(suite.get(key,'0')) for key in ('tests','failures','errors','skipped')}
        (folder/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
        assert result['primary_unchanged'] and result['env_unchanged']


if __name__=='__main__':main()
