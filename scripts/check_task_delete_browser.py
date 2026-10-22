"""M6: real production UI + native business API in a disposable DB; no provider calls."""
import asyncio,hashlib,json,os,re,secrets,socket,subprocess,sys,time,urllib.request
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from cryptography.fernet import Fernet
from pao.config import ROOT,settings
from pao.models import Workspace,Member,User,Brand
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import frontend_supplements
from check_p11_migration import snapshot
from run_s3_browser import seed

WEB=Path('F:/Apex/task-delete-candidate')
CONTAINER='pao-acos-local-postgres-1'
def frontend(root):
 return {k:v for k,v in {**entries(root),**frontend_supplements(root)}.items() if k.startswith('apps/web/') and not k.endswith('next-env.d.ts')}
async def extra_seed(target):
 engine=create_async_engine(target);session=async_sessionmaker(engine,expire_on_commit=False)
 try:
  async with session.begin() as db:
   from sqlalchemy import select
   user=await db.scalar(select(User).where(User.email=='owner@example.test'))
   third=Workspace(name='Doanh nghiệp thử C');db.add(third);await db.flush()
   db.add(Member(workspace_id=third.id,user_id=user.id,role='owner'))
  return third.id
 finally:await engine.dispose()
def main():
 cfg=settings();url=make_url(cfg.database_url)
 assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
 assert WEB.resolve()==Path('F:/Apex/task-delete-candidate')
 for port in (18102,13200):
  with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0,'Test port occupied'
 before=asyncio.run(snapshot(url));env_hash=digest(ROOT/'.env');binding=execution_binding();files=frontend(WEB);installed=frontend(ROOT)
 name='pao_s5_browser_'+uuid4().hex
 assert re.fullmatch(r'pao_s5_browser_[0-9a-f]{32}',name)
 folder=ROOT/'.runtime/task-delete-browser-runs'/name;folder.mkdir(parents=True)
 (folder/'primary-before.json').write_text(json.dumps(before),encoding='utf-8')
 owned=[];handles=[];created=False
 try:
  subprocess.run(['docker','exec',CONTAINER,'createdb','-U','pao',name],check=True,timeout=60);created=True
  target=url.set(database=name).render_as_string(hide_password=False)
  env={**os.environ,'PAO_ROOT':str(WEB),'PYTHONPATH':str(WEB/'apps/api'),'DATABASE_URL':target,
   'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
   'JWT_SECRET':'m6-synthetic-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
   'BUSINESS_PLANNING_ENABLED':'true','STUDIO_ENABLED':'true','ENGINE_CONTRACT_ENABLED':'true','CHAT_FEATURES_ENABLED':'true',
   'PAO_S5_BROWSER_TEST':'1','PAO_S5_BROWSER_KEY':secrets.token_urlsafe(32),'PAO_BUILD_CHECK':'1','PAO_API_URL':'http://127.0.0.1:18102'}
  for key in ('META_ENABLED','GOOGLE_ADS_ENABLED','META_WRITE_ENABLED','META_AUTOPILOT_ENABLED','ADS_AUTOPILOT_GLOBAL_ENABLED',
   'TELEGRAM_ENABLED','TELEGRAM_SCOPED_RUNTIME_ENABLED','CHANNELS_ENABLED','CHANNEL_AUTOREPLY_ENABLED','CHANNEL_RETENTION_ENABLED',
   'TEMPORAL_ENABLED','MEMORY_ENABLED','TOOLS_ENABLED','AGENT_RUNTIME_ENABLED','WORKFLOW_DISPATCH_ENABLED','WORKFLOW_WORKER_ENABLED',
   'GOAL_RUNNER_ENABLED','STUDIO_SCHEDULE_DISPATCH_ENABLED','BUSINESS_EVENTS_ENABLED','BUSINESS_EVENT_DELIVERY_ENABLED'):
   env[key]='false'
  subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=WEB,env=env,check=True,timeout=120)
  a,b=asyncio.run(seed(target));third=asyncio.run(extra_seed(target))
  fixture={'api':'http://127.0.0.1:18102','web':'http://127.0.0.1:13200','workspace':a,'second':b,'third':third,
   'fixture_key':env['PAO_S5_BROWSER_KEY'],'screenshot':str(folder/'mobile.png'),'folder':str(folder)}
  env['PAO_S5_BROWSER']=json.dumps(fixture)
  for title,command,cwd in (
   ('api',[sys.executable,str(WEB/'scripts/s5_browser_api.py')],ROOT),
   ('web',['node',str(ROOT/'node_modules/next/dist/bin/next'),'start','apps/web','--hostname','127.0.0.1','--port','13200'],WEB)):
   handle=(folder/(title+'.log')).open('w',encoding='utf-8');handles.append(handle)
   owned.append(subprocess.Popen(command,cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW))
  for endpoint in (fixture['api']+'/ready',fixture['web']+'/'):
   for attempt in range(80):
    assert all(p.poll() is None for p in owned),'Owned service exited'
    try:
     with urllib.request.urlopen(endpoint,timeout=1) as response:
      if response.status==200:break
    except Exception:time.sleep(.5)
   else:raise AssertionError('Owned service not ready')
  checked=subprocess.run(['node',str(WEB/'scripts/task_delete_browser.cjs')],cwd=WEB,env=env,capture_output=True,text=True,encoding='utf-8',timeout=420)
  (folder/'browser.log').write_text(checked.stdout+checked.stderr,encoding='utf-8')
  print(checked.stdout,end='');print(checked.stderr,end='',file=sys.stderr);checked.check_returncode()
  result=json.loads((folder/'task-delete-browser.json').read_text());assert result['pass']
  assert binding==execution_binding() and installed==frontend(ROOT) and files==frontend(WEB)
  assert before==asyncio.run(snapshot(url)) and digest(ROOT/'.env')==env_hash
  receipt={**result,'binding':binding,'frontend_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
   'primary_unchanged':True,'environment_unchanged':True,'production_build':True,'production_accepted':False}
  (folder/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
  print('M6 browser artifacts: '+str(folder))
 finally:
  for process in reversed(owned):
   if process.poll() is None:
    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
    process.wait(timeout=15)
  for handle in handles:handle.close()
  if created:
   subprocess.run(['docker','exec',CONTAINER,'dropdb','-U','pao',name],check=True,timeout=120)
   checked=subprocess.run(['docker','exec',CONTAINER,'psql','-U','pao','-d','postgres','-Atc',"SELECT count(*) FROM pg_database WHERE datname='"+name+"'"],check=True,capture_output=True,text=True,encoding='utf-8',timeout=30)
   assert checked.stdout.strip()=='0','Owned test DB cleanup failed'
  for port in (18102,13200):
   with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0,'Owned process cleanup failed'
  (folder/'cleanup.json').write_text(json.dumps({'pass':True,'database_absent':True,'test_ports_free':True}),encoding='utf-8')
  print('M6 isolated cleanup passed.')
if __name__=='__main__':
 from local_cycle_test_lock import isolated_test_slot
 with isolated_test_slot():main()

