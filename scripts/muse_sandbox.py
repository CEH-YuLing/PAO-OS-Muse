"""Independent development installer/launcher. Never reads the original .env/DB."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = Path('G:/PAO OS Muse')
if ROOT != EXPECTED or any(p.is_symlink() or p.is_junction() for p in (ROOT, *ROOT.parents)):
    raise SystemExit('This launcher only operates in the independent G:/PAO OS Muse directory')
if json.loads((ROOT/'.pao-muse-sandbox.json').read_text())['root'] != str(ROOT):
    raise SystemExit('Sandbox marker mismatch')
os.environ['PAO_ROOT'] = str(ROOT)
os.environ['PYTHONPATH'] = os.pathsep.join(str(ROOT/p) for p in ('apps/api','packages/cli-runtime','scripts'))
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PAO_API_URL'] = 'http://127.0.0.1:8200'
sys.path[:0] = [str(ROOT/p) for p in ('apps/api','packages/cli-runtime','scripts')]
RUNTIME = ROOT/'.runtime'
RUNTIME.mkdir(exist_ok=True)
PYTHON = ROOT/'.venv/Scripts/python.exe'
COMPOSE = ['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'infra/compose.muse-local.yaml')]


def run(argv, **kwargs):
    return subprocess.run([str(v) for v in argv], cwd=ROOT, check=True, **kwargs)


def guard():
    from pao.config import settings
    from sqlalchemy.engine import make_url
    from urllib.parse import urlsplit
    cfg = settings(); db = make_url(cfg.database_url); redis = urlsplit(cfg.redis_url)
    if (db.host, db.port, db.database) != ('127.0.0.1',25432,'pao_muse_local'):
        raise RuntimeError('Refusing a database outside the Muse sandbox')
    if (redis.hostname,redis.port,redis.path) != ('127.0.0.1',26379,'/0'):
        raise RuntimeError('Refusing a queue outside the Muse sandbox')
    return cfg


def create_environment():
    if (ROOT/'.env').exists():
        guard(); return
    from cryptography.fernet import Fernet
    pg, redis, jwt, channel = [secrets.token_hex(32) for _ in range(4)]
    enabled = ['BRAIN_MANAGER','KNOWLEDGE_SOURCES','KNOWLEDGE','ENGINE_CONTRACT',
        'CHAT_FEATURES','STUDIO','BUSINESS_PLANNING','WORKFLOW_PLANNING','CONNECTORS',
        'BUSINESS_EVENTS','UNIFIED_APPROVALS','CHANNELS','RESULT_INBOX','LEARNING_REVIEW',
        'OUTCOME_OBSERVATIONS','INSTALLATION_AI','CLI_CONNECTIONS','CLI_BROWSER_LOGIN']
    lines = [f'DATABASE_URL=postgresql+asyncpg://pao:{pg}@127.0.0.1:25432/pao_muse_local',
        f'POSTGRES_PASSWORD={pg}',f'REDIS_PASSWORD={redis}',
        f'REDIS_URL=redis://:{redis}@127.0.0.1:26379/0',f'JWT_SECRET={jwt}',
        'INTEGRATION_ENCRYPTION_KEY='+Fernet.generate_key().decode(),f'CHANNEL_IDENTITY_KEY={channel}',
        'POSTGRES_USER=pao','POSTGRES_DB=pao_muse_local','PROVIDER_MANAGED_TOKENS=true',
        'RUN_TIMEOUT_SECONDS=600','INSTALLATION_AI_MANAGER_IDS=[]',
        'OLLAMA_URL=http://127.0.0.1:21434','MEMORY_ENABLED=false','KNOWLEDGE_EMBEDDINGS_ENABLED=false',
        'TOOLS_ENABLED=false','SEARXNG_URL=http://127.0.0.1:28888',
        'TEMPORAL_ENABLED=false','TELEGRAM_ENABLED=false','TELEGRAM_SCOPED_RUNTIME_ENABLED=false',
        'META_ENABLED=false','META_WRITE_ENABLED=false','GOOGLE_ADS_ENABLED=false',
        'ADS_AUTOPILOT_GLOBAL_ENABLED=false','META_AUTOPILOT_ENABLED=false',
        'CHANNEL_AUTOREPLY_ENABLED=false','CHANNEL_RETENTION_ENABLED=false',
        'WORKFLOW_DURABLE_ENABLED=false','WORKFLOW_DISPATCH_ENABLED=false','WORKFLOW_WORKER_ENABLED=false']
    lines += [name+'_ENABLED=true' for name in enabled]
    with (ROOT/'.env').open('x',encoding='utf-8') as file:
        file.write('\n'.join(lines)+'\n')
    print('Created fresh sandbox keys; no keys imported or printed.')


async def bootstrap_owner():
    from sqlalchemy import select
    from pao.db import Session,engine
    from pao.models import User,Workspace,Member
    from pao.auth import passwords
    async with Session.begin() as db:
        owner = await db.scalar(select(User).where(User.email=='owner@muse.pao.local'))
        if owner:
            await engine.dispose(); return
        password = secrets.token_urlsafe(20)
        owner = User(email='owner@muse.pao.local',password_hash=passwords.hash(password))
        workspace = Workspace(name='PAO OS Muse - Local Development')
        db.add_all([owner,workspace]); await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=owner.id,role='owner'))
        uid = owner.id
        with (RUNTIME/'first-login.txt').open('x',encoding='utf-8') as file:
            file.write('Local sandbox only - do not commit or share\nURL: http://127.0.0.1:3300/\n'
                'Email: owner@muse.pao.local\nPassword: '+password+'\n')
    env = (ROOT/'.env').read_text(encoding='utf-8')
    (ROOT/'.env').write_text(env.replace('INSTALLATION_AI_MANAGER_IDS=[]',
        'INSTALLATION_AI_MANAGER_IDS='+json.dumps([uid])),encoding='utf-8')
    await engine.dispose()
    print('Created independent owner. Read .runtime/first-login.txt locally; do not send its password to an agent.')


def setup():
    create_environment(); guard()
    run(COMPOSE+['up','-d','--wait'],timeout=180)
    # A fresh installation gets its own pre-migration DB dump; never restore primary.
    checkpoint = RUNTIME/'bootstrap-before-migration.dump'
    if not checkpoint.exists():
        with checkpoint.open('xb') as output:
            run(COMPOSE+['exec','-T','postgres','pg_dump','-U','pao','-d','pao_muse_local','-Fc'],stdout=output,timeout=60)
        with checkpoint.open('rb') as saved:
            run(COMPOSE+['exec','-T','postgres','pg_restore','--list'],stdin=saved,stdout=subprocess.DEVNULL,timeout=60)
    run([PYTHON,'-B','-m','alembic','upgrade','0077'],timeout=180)
    # An independent disposable DB, never the source pao_test.
    check = run(COMPOSE+['exec','-T','postgres','psql','-U','pao','-d','postgres','-Atc',
        "SELECT 1 FROM pg_database WHERE datname='pao_test'"],capture_output=True,text=True,timeout=20)
    if check.stdout.strip() != '1':
        run(COMPOSE+['exec','-T','postgres','createdb','-U','pao','pao_test'],timeout=20)
    asyncio.run(bootstrap_owner())


def observed(pid):
    script = f'Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}" | Select-Object ProcessId,ExecutablePath,CreationDate | ConvertTo-Json -Compress'
    result = subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,text=True,check=True,timeout=20)
    return json.loads(result.stdout) if result.stdout.strip() else None


def start():
    guard(); run(COMPOSE+['up','-d','--wait'],timeout=180)
    state_path = RUNTIME/'muse-processes.json'
    records = json.loads(state_path.read_text()) if state_path.exists() else {}
    node = shutil.which('node')
    commands = {'api':[str(PYTHON),'-B','-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8200','--no-access-log'],
        'worker':[str(PYTHON),'-B','-m','arq','pao.runtime.WorkerSettings'],
        'web':[node,str(ROOT/'node_modules/next/dist/bin/next'),'dev',str(ROOT/'apps/web'),'--hostname','127.0.0.1','--port','3300']}
    import socket
    for name,argv in commands.items():
        old = records.get(name)
        if old and observed(old['pid'])==old['identity']:
            print(name+' already running');continue
        if name in ('api','web'):
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1',8200 if name=='api' else 3300))==0:
                    raise RuntimeError(name+' port occupied by an unverified process; no process stopped')
        with (RUNTIME/(name+'.stdout.log')).open('ab') as out,(RUNTIME/(name+'.stderr.log')).open('ab') as err:
            child = subprocess.Popen(argv,cwd=ROOT,env=os.environ.copy(),stdout=out,stderr=err,
                creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(.5)
        identity=observed(child.pid)
        if child.poll() is not None or identity is None:raise RuntimeError(name+' exited; inspect sandbox logs')
        records[name]={'pid':child.pid,'identity':identity,'argv':argv}
        state_path.write_text(json.dumps(records,indent=2),encoding='utf-8')
        print('Started sandbox '+name)


def stop():
    path = RUNTIME/'muse-processes.json'
    if not path.exists():return
    records=json.loads(path.read_text())
    for name,row in list(records.items()):
        actual=observed(row['pid'])
        if actual is None:records.pop(name);continue
        if actual!=row['identity']:raise RuntimeError('Process identity changed; refusing to stop '+name)
        if Path(row['argv'][0]).resolve() not in (PYTHON.resolve(),Path(shutil.which('node')).resolve()):
            raise RuntimeError('Unexpected process executable')
        run(['taskkill','/PID',str(row['pid']),'/T','/F'],timeout=30)
        records.pop(name)
    path.write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Stopped only recorded Muse sandbox trees; Docker data retained.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','start','stop'])
    {'setup':setup,'start':start,'stop':stop}[parser.parse_args().action]()
