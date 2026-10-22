"""Disposable private Compose/TLS/least-privilege drill. No host reboot/live credentials."""
import asyncio,json,os,re,secrets,socket,ssl,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
from cryptography.fernet import Fernet
import httpx
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from backup_acos_checkpoint import source_archive
from check_p11_migration import snapshot

def main():
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--candidate',action='store_true');options=parser.parse_args()
 source_root=Path('F:/Apex/phase3-candidate') if options.candidate else ROOT
 assert source_root.is_dir() and not source_root.is_symlink() and not source_root.is_junction()
 cfg=settings();url=make_url(cfg.database_url)
 assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
 with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',18443))!=0,'Private test port occupied'
 rid=uuid4().hex;project='pao-release-'+rid[:16]
 folder=ROOT/'.runtime'/('phase3-private-'+rid);folder.mkdir()
 source_archive(source_root,folder/'source.zip')
 from zipfile import ZipFile
 with ZipFile(folder/'source.zip') as archive:archive.extractall(folder/'source')
 source=folder/'source';compose=source/'infra/production/compose.private.yaml'
 empty=folder/'empty.env';empty.write_text('',encoding='utf-8')
 database='pao_service_'+rid[:12];app_password=secrets.token_hex(24);migration_password=secrets.token_hex(24);redis_password=secrets.token_hex(24)
 runtime={'DATABASE_URL':f'postgresql+asyncpg://pao_app:{app_password}@postgres:5432/{database}',
  'REDIS_URL':f'redis://:{redis_password}@redis:6379/0','JWT_SECRET':secrets.token_hex(40),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode()}
 for name,value in [('runtime.json',runtime),('migration.json',{**runtime,'DATABASE_URL':f'postgresql+asyncpg://pao_migrator:{migration_password}@postgres:5432/{database}'})]:
  (folder/name).write_text(json.dumps(value),encoding='utf-8')
 (folder/'postgres-password').write_text(secrets.token_hex(24),encoding='utf-8');(folder/'redis-password').write_text(redis_password,encoding='utf-8')
 env={**os.environ,'PAO_API_IMAGE':'pao-release-api:'+rid,'PAO_WEB_IMAGE':'pao-release-web:'+rid,'PAO_PROXY_IMAGE':'pao-release-proxy:'+rid,
  'PAO_POSTGRES_ADMIN_FILE':str(folder/'postgres-password'),'PAO_REDIS_PASSWORD_FILE':str(folder/'redis-password'),
  'PAO_RUNTIME_CONFIG_FILE':str(folder/'runtime.json'),'PAO_MIGRATION_CONFIG_FILE':str(folder/'migration.json')}
 before=asyncio.run(snapshot(url));env_hash=digest(ROOT/'.env');binding=execution_binding()
 result={'pass':False,'project':project,'production_accepted':False,'host_reboot_tested':False,'provider_calls':False}
 def call(args,*,input=None):return subprocess.run(args,cwd=source,env=env,input=input,capture_output=True,text=True,encoding='utf-8',errors='replace',check=True,timeout=180).stdout.strip()
 def docker(*args,**kw):return call(['docker',*args],**kw)
 def dc(*args,**kw):return docker('compose','--env-file',str(empty),'-p',project,'-f',str(compose),*args,**kw)
 def logged(args,title,limit=1000):
  with (folder/(title+'.log')).open('wb') as log:
   process=subprocess.Popen(args,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
   start=time.monotonic()
   try:
    while True:
     try:code=process.wait(timeout=35);assert code==0,title+' failed; inspect retained log';return
     except subprocess.TimeoutExpired:
      print(json.dumps({'stage':title,'seconds':int(time.monotonic()-start)}),flush=True)
      if time.monotonic()-start>limit:raise RuntimeError('private_stage_timeout')
   finally:
    if process.poll() is None:process.terminate();process.wait(timeout=15)
 def container(service):
  cid=dc('ps','-q',service);assert re.fullmatch('[a-f0-9]{64}',cid)
  assert docker('inspect',cid,'--format','{{index .Config.Labels "com.docker.compose.project"}}')==project
  return cid
 try:
  model=json.loads(dc('config','--format','json'))
  assert model['services']['proxy']['ports'][0]['host_ip']=='127.0.0.1'
  for service in ('api','worker','web','postgres','redis'):assert not model['services'][service].get('ports')
  for component in ('api','web','proxy'):
   print('Building private '+component+' image.',flush=True)
   logged(['docker','build','--label','pao.release.runid='+rid,'-f',str(source/f'infra/production/{component}.Dockerfile'),'-t',env['PAO_'+component.upper()+'_IMAGE'],str(source)],'build-'+component)
  dc('up','-d','--wait','postgres','redis')
  pg=container('postgres')
  docker('exec','-i',pg,'psql','-U','pao_admin','-d','postgres','-v','ON_ERROR_STOP=1','-v','database='+database,
   '-v','migrator_password='+migration_password,'-v','app_password='+app_password,input=(source/'infra/production/roles.sql').read_text())
  for mode in ('migrate','grant'):
   outcome=dc('--profile','operations','run','--rm','--no-deps',mode);(folder/(mode+'.log')).write_text(outcome,encoding='utf-8')
  dc('up','-d','--wait','api','worker','web','proxy')
  proxy=container('proxy')
  for _ in range(40):
   try:docker('cp',proxy+':/data/caddy/pki/authorities/local/root.crt',str(folder/'private-ca.crt'));break
   except subprocess.CalledProcessError:time.sleep(.5)
  else:raise AssertionError('Private CA not provisioned; inspect proxy log')
  context=ssl.create_default_context(cafile=str(folder/'private-ca.crt'))
  with httpx.Client(base_url='https://localhost:18443',verify=context,trust_env=False,timeout=20) as client:
   for _ in range(60):
    try:
     if client.get('/ready').status_code==200:break
    except httpx.TransportError:time.sleep(.5)
   else:raise AssertionError('TLS ready failed')
   for endpoint in ('/health','/ready','/settings','/business-planning','/'):
    response=client.get(endpoint);assert response.status_code==200
    assert response.headers.get('x-content-type-options')=='nosniff' and response.headers.get('x-frame-options')=='DENY'
   assert client.get('/v1/me').status_code==401
   html=client.get('/settings').text
   assets=re.findall(r'(?:src|href)="([^\"]+/_next/[^\"]+|/_next/[^\"]+)"',html)
   assert assets
   for asset in assets:assert client.get(asset.replace('&amp;','&')).status_code==200
   # Native app DML/permission checks; values stay in the test container/process.
   check_code='''import asyncio,json,os
from pathlib import Path
os.environ.update(json.loads(Path('/run/secrets/pao_config').read_text()))
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from pao.db import engine,Session
from pao.models import User,Workspace,Member
from pao.auth import passwords
async def main():
 async with Session.begin() as db:
  user=User(email='release-owner@example.test',password_hash=passwords.hash('synthetic-release-password-123'));a=Workspace(name='Release A');b=Workspace(name='Release B');db.add_all([user,a,b]);await db.flush();db.add_all([Member(workspace_id=a.id,user_id=user.id,role='owner'),Member(workspace_id=b.id,user_id=user.id,role='viewer')])
 for sql in ('CREATE TABLE public.forbidden_test(id int)','TRUNCATE users','UPDATE alembic_version SET version_num=version_num','SET ROLE pao_migrator'):
  try:
   async with engine.begin() as db:await db.execute(text(sql))
  except DBAPIError:pass
  else:raise AssertionError('runtime privilege escalation permitted')
 await engine.dispose()
asyncio.run(main())
print('least-privilege app CRUD/DDL/TRUNCATE/migration ledger/role checks passed')'''
   app=container('api');call(['docker','exec','-i',app,'python'],input=check_code)
   signed=client.post('/v1/auth/token',json={'email':'release-owner@example.test','password':'synthetic-release-password-123'});assert signed.status_code==200
   headers={'Authorization':'Bearer '+signed.json()['access_token']}
   me=client.get('/v1/me',headers=headers);assert me.status_code==200 and len(me.json()['workspaces'])==2
   status=client.get('/v1/ads/write-status',headers=headers);assert status.status_code==200 and status.json()['enabled'] is False
   assert client.get('/v1/auth/sessions',headers=headers).status_code==200
   for service in ('api','worker','web','proxy'):
    details=json.loads(docker('inspect',container(service)))[0]
    assert details['Config']['User'] not in ('','root','0') and details['HostConfig']['ReadonlyRootfs']
    assert not any(v.startswith(('DATABASE_URL=','JWT_SECRET=','INTEGRATION_ENCRYPTION_KEY=')) for v in details['Config']['Env'])
   # Container-only restart, not host reboot/failover.
   docker('restart',container('api'));docker('restart',container('worker'))
   for _ in range(80):
    try:
     if client.get('/ready').status_code==200 and client.get('/v1/me',headers=headers).status_code==200:break
    except httpx.TransportError:pass
    time.sleep(.5)
   else:raise AssertionError('private restart recovery failed')
  installed_next=docker('exec',container('web'),'node','-p',"require('next/package.json').version")
  assert installed_next=='15.5.28','Private Web must use the reviewed security release'
  result.update(pass_=True,tls_private_ca_verified=True,least_privilege=True,api_login_two_smes=True,static_assets=True,
   file_secrets_not_docker_env=True,nonroot_readonly=True,container_restart=True,primary_backend_binding=binding,
   images={name:docker('image','inspect',env['PAO_'+name.upper()+'_IMAGE'],'--format','{{.Id}}') for name in ('api','web','proxy')},
   web_next_version=installed_next)
  result['pass']=result.pop('pass_')
 finally:
  # Only resources with the generated project's exact ownership label may be removed.
  ids=dc('ps','-aq').splitlines()
  for cid in ids:assert docker('inspect',cid,'--format','{{index .Config.Labels "com.docker.compose.project"}}')==project
  try:
   for service in ('postgres','redis','api','worker','web','proxy'):
    logs=subprocess.run(['docker','compose','--env-file',str(empty),'-p',project,'-f',str(compose),'logs','--no-color',service],cwd=source,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    (folder/(service+'.log')).write_text((logs.stdout or '')+(logs.stderr or ''),encoding='utf-8')
  finally:dc('down','--volumes','--remove-orphans')
  assert not docker('ps','-aq','--filter','label=com.docker.compose.project='+project)
  assert not docker('volume','ls','-q','--filter','label=com.docker.compose.project='+project)
  result.update(primary_unchanged=before==asyncio.run(snapshot(url)),env_unchanged=env_hash==digest(ROOT/'.env'),backend_unchanged=binding==execution_binding(),owned_resources_removed=True)
  (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
  print(json.dumps({**result,'evidence':str(folder)}),flush=True)
  assert result['primary_unchanged'] and result['env_unchanged'] and result['backend_unchanged']
if __name__=='__main__':main()
