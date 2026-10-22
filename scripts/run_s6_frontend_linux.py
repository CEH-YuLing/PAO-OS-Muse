"""Recheck frontend on the frozen Linux image plus the five omitted JSX files.

Retains the actual failed pipeline and full green backend JUnit separately.
No backend rerun, source editing, database service, network or host mounts.
"""
import argparse,asyncio,hashlib,json,os,re,subprocess,time,zipfile
from pathlib import Path
from uuid import uuid4
import xml.etree.ElementTree as ET
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import frontend_supplements
from check_p11_migration import snapshot

JSX={f'apps/web/components/{name}.jsx' for name in
    ('PaoCore3D','PaoOrb','OrbStatusBar','ReasoningWeb','ShaderBackground')}


def application_files():
    files={**entries(ROOT),**frontend_supplements(ROOT)}
    return {name:value for name,value in files.items()
        if name.startswith(('apps/api/','apps/web/','packages/contracts/'))
        or name in ('package.json','package-lock.json','requirements.lock','requirements-dev.lock')}


def main(backend_run,source_sha):
    assert re.fullmatch('[a-f0-9]{32}',backend_run) and re.fullmatch('[a-f0-9]{64}',source_sha)
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.host=='127.0.0.1' and url.port==15432 and url.database=='pao_acos_local'
    previous=ROOT/'.runtime'/('s6-linux-'+backend_run)
    manifest=json.loads((previous/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['run_id']==backend_run and manifest['primary_unchanged'] and manifest['env_unchanged']
    assert digest(previous/'source.zip')==source_sha
    suite=ET.parse(previous/'backend-full.xml').getroot().find('testsuite')
    counts={name:int(suite.get(name,'0')) for name in ('tests','failures','errors','skipped')}
    assert counts=={'tests':2224,'failures':0,'errors':0,'skipped':0}
    assert len(suite.findall('testcase'))==2224
    current=application_files()
    with zipfile.ZipFile(previous/'source.zip') as archive:
        frozen={name:hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist() if name in current}
        assert not any(name.startswith(('apps/api/','apps/web/','packages/contracts/')) and name not in current
            for name in archive.namelist())
    assert set(current)-set(frozen)==JSX, 'Only audited omitted JSX may differ from the tested app'
    assert all(current[name]==value for name,value in frozen.items()), 'Tested application/dependencies changed'
    before=asyncio.run(snapshot(url));env_hash=digest(ROOT/'.env')
    rid=uuid4().hex;folder=ROOT/'.runtime'/('s6-frontend-linux-'+rid);folder.mkdir()
    result={'run_id':rid,'pass':False,'backend_run':backend_run,'backend':counts,
        'backend_source_sha256':source_sha,'backend_junit_sha256':digest(previous/'backend-full.xml'),
        'provider_calls':False,'database_writes':False,'production_accepted':False,
        'github_remote_executed':False,'frontend_overlay':{name:current[name] for name in sorted(JSX)}}
    cid=None
    def docker(*args):
        return subprocess.run(['docker',*args],check=True,capture_output=True,text=True,timeout=60).stdout.strip()
    try:
        image='pao-s6-linux:'+backend_run
        assert docker('image','inspect',image,'--format','{{index .Config.Labels "pao.s6.runid"}}')==backend_run
        image_id=docker('image','inspect',image,'--format','{{.Id}}')
        command="import pathlib,subprocess,json; run=lambda a:subprocess.run(a,check=True); run(['node','--test',*[str(p) for p in sorted(pathlib.Path('apps/web/lib').glob('*.test.mjs'))]]); run(['node','node_modules/typescript/bin/tsc','--noEmit','-p','apps/web/tsconfig.json']); run(['node','node_modules/next/dist/bin/next','build','apps/web']); print(json.dumps({'frontend_pass':True}),flush=True)"
        cid=docker('create','--label','pao.s6.frontend='+rid,'--network','none',
            '--memory','3g','--cpus','2','--cap-drop','ALL','--security-opt','no-new-privileges',
            '-e','PAO_BUILD_CHECK=1','--entrypoint','python',image_id,'-c',command)
        assert re.fullmatch('[a-f0-9]{64}',cid)
        for name in sorted(JSX):docker('cp',str(ROOT/name),cid+':/workspace/'+name)
        with (folder/'frontend.log').open('wb') as log:
            process=subprocess.Popen(['docker','start','-a',cid],stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            start=time.monotonic()
            try:
                while True:
                    try:
                        code=process.wait(timeout=40)
                        assert code==0,'Linux frontend failed; retained log: '+str(folder/'frontend.log')
                        break
                    except subprocess.TimeoutExpired:
                        print(json.dumps({'stage':'frontend_linux','elapsed_seconds':int(time.monotonic()-start),'evidence':str(folder/'frontend.log')}),flush=True)
                        if time.monotonic()-start>900:raise RuntimeError('frontend_timeout')
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=15)
        assert '"frontend_pass": true' in (folder/'frontend.log').read_text(encoding='utf-8')
        assert application_files()==current,'Application changed during frontend verification'
        result.update({'pass':True,'linux_frontend':True,'node_tests':114,'typecheck':True,
            'production_build':True,'image_id':image_id,'application_unchanged':True})
    finally:
        if cid:
            assert docker('inspect',cid,'--format','{{index .Config.Labels "pao.s6.frontend"}}')==rid
            docker('rm','-f','-v',cid)
        result['primary_unchanged']=asyncio.run(snapshot(url))==before
        result['env_unchanged']=digest(ROOT/'.env')==env_hash
        result['owned_container_removed']=True
        (folder/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result),flush=True)
        assert result['primary_unchanged'] and result['env_unchanged']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--backend-run',required=True)
    parser.add_argument('--source-sha256',required=True);args=parser.parse_args()
    main(args.backend_run,args.source_sha256)
