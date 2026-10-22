"""Isolated real API+production frontend browser gate, synthetic data only."""
import asyncio,hashlib,json,os,socket,subprocess,sys,time,urllib.request
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from cryptography.fernet import Fernet
from sqlalchemy.engine import make_url

sys.path[:0]=['F:/PAO-ACOS/apps/api','F:/PAO-ACOS/scripts']
from pao.config import settings

ROOT=Path('F:/PAO-ACOS')
BASE=Path(__file__).parent
CONTAINER='pao-acos-local-postgres-1'


def main():
    from pao.skills import execution_binding,_execution_digest
    from pao.modules.operations.checkpoint import entries
    from backup_acos_checkpoint import frontend_supplements
    def frontend_files(root):
        return {k:v for k,v in {**entries(root),**frontend_supplements(root)}.items()
                if k.startswith('apps/web/') and not k.endswith('next-env.d.ts')}
    config=settings();url=make_url(config.database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432 and url.username=='pao'
    web_root=Path(os.environ.get('PAO_S62_WEB_ROOT',str(ROOT))).resolve()
    assert web_root in (ROOT.resolve(),Path('F:/Apex/s62-candidate').resolve())
    binding=execution_binding();primary_files=frontend_files(ROOT)
    if web_root!=ROOT.resolve():
        candidate_files=frontend_files(web_root)
        assert primary_files==candidate_files,'Frontend candidate/source mismatch'
    for port in (18100,13200):
        with socket.socket() as check:assert check.connect_ex(('127.0.0.1',port))!=0,'Test port occupied'
    name='pao_s62_browser_'+uuid4().hex
    parent=ROOT/'.runtime/s62-browser-runs';parent.mkdir(exist_ok=True)
    folder=parent/name;folder.mkdir()
    subprocess.run(['docker','exec',CONTAINER,'createdb','-U','pao',name],check=True)
    redis=urlsplit(config.redis_url)
    env={**os.environ,'PAO_ROOT':str(ROOT),'PYTHONPATH':str(ROOT/'apps/api'),
        'DATABASE_URL':config.database_url.rsplit('/',1)[0]+'/'+name,
        'REDIS_URL':urlunsplit((redis.scheme,redis.netloc,'/14','','')),
        'JWT_SECRET':'s62-synthetic-browser-key-not-production-0123456789',
        'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
        'PAO_BUILD_CHECK':'1','PAO_API_URL':'http://127.0.0.1:18100','BRAIN_MANAGER_ENABLED':'1'}
    for key in ('META_ENABLED','META_WRITE_ENABLED','GOOGLE_ADS_ENABLED','TELEGRAM_ENABLED','TELEGRAM_SCOPED_RUNTIME_ENABLED',
        'TEMPORAL_ENABLED','WORKFLOW_DISPATCH_ENABLED','WORKFLOW_WORKER_ENABLED','GOAL_RUNNER_ENABLED','CHANNELS_ENABLED',
        'CHANNEL_AUTOREPLY_ENABLED','CHANNEL_RETENTION_ENABLED','STUDIO_SCHEDULE_DISPATCH_ENABLED','META_INSTALLATION_CONFIG_ENABLED',
        'VOICE_ENABLED','BUSINESS_EVENTS_ENABLED','BUSINESS_EVENT_DELIVERY_ENABLED','BUSINESS_PLANNING_ENABLED'):
        env[key]='0'
    owned=[];handles=[]
    try:
        subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=ROOT,env=env,check=True)
        seed="""import asyncio,json,sys
from pao.auth import passwords
from pao.models import User,Workspace,Member,Brand
from pao.db import Session,engine
async def main():
 async with Session.begin() as db:
  user=User(email='owner-s62@example.test',password_hash=passwords.hash('synthetic-browser-password-123'))
  alpha=Workspace(name='S62 Alpha');beta=Workspace(name='S62 Beta');db.add_all([user,alpha,beta]);await db.flush()
  db.add_all([Member(workspace_id=alpha.id,user_id=user.id,role='owner'),Member(workspace_id=beta.id,user_id=user.id,role='owner'),Brand(workspace_id=alpha.id,name='Alpha brand'),Brand(workspace_id=beta.id,name='Beta brand')])
  value={'owner':user.email,'password':'synthetic-browser-password-123','alpha':alpha.id,'beta':beta.id,'web':'http://127.0.0.1:13200'}
 with open(sys.argv[1],'x',encoding='utf-8') as out:json.dump(value,out)
 await engine.dispose()
asyncio.run(main())"""
        fixture=folder/'synthetic-fixture.json'
        subprocess.run([sys.executable,'-c',seed,str(fixture)],cwd=ROOT,env=env,check=True)
        for title,command,cwd in (
            ('api',[sys.executable,'-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','18100','--no-access-log'],ROOT),
            ('web',['node',str(ROOT/'node_modules/next/dist/bin/next'),'start','apps/web','--hostname','127.0.0.1','--port','13200'],web_root)):
            handle=(folder/(title+'.log')).open('w',encoding='utf-8');handles.append(handle)
            owned.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW))
        for url in ('http://127.0.0.1:18100/ready','http://127.0.0.1:13200/join'):
            for _ in range(60):
                if any(process.poll() is not None for process in owned):raise RuntimeError('Owned test service exited')
                try:
                    with urllib.request.urlopen(url,timeout=1) as response:
                        if response.status==200:break
                except Exception:time.sleep(.5)
            else:raise RuntimeError('Test service not ready')
        subprocess.run(['node',str(BASE/'s62_browser_acceptance.cjs'),str(fixture)],cwd=BASE,env=env,check=True,timeout=240)
        result=json.loads((folder/'browser-result.json').read_text(encoding='utf-8'))
        assert result.get('pass') is True and _execution_digest()==binding['sha256'] and frontend_files(ROOT)==primary_files
        receipt={**result,'binding':binding,'backend_binding_unchanged':True,
                 'frontend_sha256':hashlib.sha256(json.dumps(primary_files,sort_keys=True).encode()).hexdigest(),
                 'production_accepted':False}
        (folder/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print('Browser artifacts: '+str(folder))
    finally:
        for process in reversed(owned):
            if process.poll() is None:
                # Windows venv/Next launchers can own native child processes.
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
        for handle in handles:handle.close()
        cleanup_timeout=False
        try:subprocess.run(['docker','exec',CONTAINER,'dropdb','-U','pao',name],check=True,timeout=120)
        except subprocess.TimeoutExpired:cleanup_timeout=True
        check=subprocess.run(['docker','exec',CONTAINER,'psql','-U','pao','-d','postgres','-Atc',
            "SELECT count(*) FROM pg_database WHERE datname='"+name+"'"],capture_output=True,text=True,check=True,timeout=30)
        assert check.stdout.strip()=='0','Test database cleanup incomplete'
        for port in (18100,13200):
            with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0,'Test service cleanup incomplete'
        (folder/'cleanup.json').write_text(json.dumps({'pass':True,'database_absent':True,'test_ports_free':True,
            'cleanup_command_timed_out':cleanup_timeout},indent=2)+'\n',encoding='utf-8')
        print('Stopped owned test processes and removed only the generated browser database.')


if __name__=='__main__':main()
