"""Real HTTP + UI write acceptance on pao_test/Redis15 only. No provider.

Run AFTER regression, never concurrently (dedicated test DB is cleared).
Starts/stops only its own hidden test API process on18100. No local data writes.
--sources also starts/stops an own Source-only ARQ worker on a unique test queue.
"""
import asyncio,os,secrets,subprocess,sys,time,urllib.request
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.auth import passwords
from pao.models import User,Workspace,Member
from uuid import uuid4

async def seed(url,password):
    if not url.endswith('/pao_test'):raise SystemExit('Test database only')
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with engine.begin() as db:await db.execute(text('TRUNCATE users,workspaces RESTART IDENTITY CASCADE'))
        async with factory.begin() as db:
            user=User(email='brain-ui@example.test',password_hash=passwords.hash(password));workspace=Workspace(name='Brain UI Acceptance')
            db.add_all([user,workspace]);await db.flush();db.add(Member(workspace_id=workspace.id,user_id=user.id,role='owner'))
    finally:await engine.dispose()

def main():
    meta_app='--meta-app' in sys.argv
    p61='--p61' in sys.argv
    m4='--m4' in sys.argv
    events='--events' in sys.argv or m4
    connectors='--connectors' in sys.argv
    studio='--studio' in sys.argv
    engines='--engines' in sys.argv
    chat='--chat' in sys.argv
    knowledge='--knowledge' in sys.argv
    sources='--sources' in sys.argv or knowledge
    config=settings()
    if not config.database_url.endswith('/pao_acos_local'):raise SystemExit('ACOS runner only')
    url=config.database_url.rsplit('/',1)[0]+'/pao_test';redis=urlsplit(config.redis_url)
    password=secrets.token_urlsafe(24)
    env={**os.environ,'DATABASE_URL':url,'PAO_TEST_DATABASE_URL':url,
        'REDIS_URL':urlunsplit((redis.scheme,redis.netloc,'/15','','')),
        'JWT_SECRET':'synthetic-p1-browser-only-'+secrets.token_hex(16),
        'BRAIN_MANAGER_ENABLED':'true','KNOWLEDGE_SOURCES_ENABLED':'true' if sources else 'false',
        'KNOWLEDGE_ENABLED':'true' if knowledge else 'false','KNOWLEDGE_EMBEDDINGS_ENABLED':'false',
        'ENGINE_CONTRACT_ENABLED':'true' if studio or engines or chat or '--engine-contract' in sys.argv else 'false','PAO_P31_BROWSER_TEST':'1' if engines else '0',
        'CHAT_FEATURES_ENABLED':'true' if studio or chat else 'false','PAO_P3_BROWSER_TEST':'1' if chat else '0',
        'STUDIO_ENABLED':'true' if studio or p61 else 'false','PAO_P4_BROWSER_TEST':'1' if studio else '0',
        'WORKFLOW_PLANNING_ENABLED':'true' if p61 else 'false',
        'CONNECTORS_ENABLED':'true' if connectors else 'false',
        'BUSINESS_EVENTS_ENABLED':'true' if events else 'false',
        'BUSINESS_EVENT_DELIVERY_ENABLED':'true' if m4 else 'false',
        'UNIFIED_APPROVALS_ENABLED':'true' if m4 else 'false',
        'PAO_M4_BROWSER_QUEUE':'pao-test:m4-browser:'+str(uuid4()),
        'PAO_P2_BROWSER_TEST':'1' if knowledge else '0',
        'MEMORY_ENABLED':'false','TOOLS_ENABLED':'false','AGENT_RUNTIME_ENABLED':'true' if studio or chat else 'false',
        'META_ENABLED':'false','META_WRITE_ENABLED':'false','GOOGLE_ADS_ENABLED':'false','TELEGRAM_ENABLED':'false',
        'TEMPORAL_ENABLED':'false','ADS_AUTOPILOT_GLOBAL_ENABLED':'false','META_AUTOPILOT_ENABLED':'false',
        'PAO_P1_BROWSER_PASSWORD':password,'PAO_P1_BROWSER_API':'http://127.0.0.1:18100',
        'PAO_FRONTEND_URL':'http://127.0.0.1:3200/',
        'PAO_P21_BROWSER_TEST':'1' if sources else '0','PAO_P21_BROWSER_QUEUE':'pao-test:sources-browser:'+str(uuid4())}
    # Refuse an existing listener rather than stopping or reusing someone else's API.
    if connectors:
        from cryptography.fernet import Fernet
        env['INTEGRATION_ENCRYPTION_KEY']=Fernet.generate_key().decode()
    import socket
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',18100))==0:raise SystemExit('Port18100 occupied; refuse reuse')
    asyncio.run(seed(url,password))
    api_log=(ROOT/'.runtime'/('p31-browser-api.stderr.log' if engines else 'p2-browser-api.stderr.log')).open('wb') if knowledge or engines else None
    command=[sys.executable,str(ROOT/'scripts/meta_settings_browser_api.py')] if meta_app else [sys.executable,'-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','18100','--no-access-log']
    process=subprocess.Popen(command,
        env=env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=api_log or subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    source_worker=None
    try:
        ready=False
        for _ in range(20):
            if process.poll() is not None:raise SystemExit('Test API exited; no acceptance')
            try:
                with urllib.request.urlopen('http://127.0.0.1:18100/ready',timeout=2) as response:ready=response.status==200
            except Exception:pass
            if ready:break
            time.sleep(.5)
        if not ready:raise SystemExit('Test API readiness failed')
        if m4 or studio or sources or engines or chat:
            source_worker=subprocess.Popen([sys.executable,str(ROOT/('scripts/m4_browser_worker.py' if m4 else 'scripts/p4_browser_worker.py' if studio else 'scripts/p3_browser_worker.py' if chat else 'scripts/p31_browser_worker.py' if engines else 'scripts/p2_browser_worker.py' if knowledge else 'scripts/p21_browser_worker.py'))],env=env,cwd=ROOT,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        subprocess.run(['node',str(ROOT/('scripts/verify_p61_ui.cjs' if p61 else 'scripts/verify_meta_app_ui.cjs' if meta_app else 'scripts/verify_m4_ui.cjs' if m4 else 'scripts/verify_m41_task_ui.cjs' if events else 'scripts/verify_p5_live_ui.cjs' if connectors else 'scripts/verify_p4_live_ui.cjs' if studio else 'scripts/verify_p3_live_ui.cjs' if chat else 'scripts/verify_p31_live_ui.cjs' if engines else 'scripts/verify_p2_live_ui.cjs' if knowledge else 'scripts/verify_p21_live_ui.cjs' if sources else 'scripts/verify_p1_live_ui.cjs'))],env=env,cwd=ROOT,check=True,timeout=180)
        if source_worker and source_worker.poll() is not None:raise SystemExit('Test source worker exited')
        if p61:
            subprocess.run([sys.executable,str(ROOT/'scripts/check_p61_restore.py')],cwd=ROOT,check=True,timeout=90)
        elif not meta_app:  # This acceptance writes only a temporary .env; no business DB writes.
            subprocess.run([sys.executable,str(ROOT/('scripts/check_m4_test_restore.py' if m4 else 'scripts/check_m41_test_restore.py' if events else 'scripts/check_p5_test_restore.py' if connectors else 'scripts/check_p4_test_restore.py' if studio else 'scripts/check_p3_test_restore.py' if chat else 'scripts/check_p31_test_restore.py' if engines else 'scripts/check_p2_test_restore.py' if knowledge else 'scripts/check_p21_test_restore.py' if sources else 'scripts/check_p1_test_restore.py'))],cwd=ROOT,check=True,timeout=90)
    finally:
        if source_worker and source_worker.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(source_worker.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=True)
            else:source_worker.terminate()
            source_worker.wait(timeout=10)
        if os.name=='nt' and process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=True)
        elif process.poll() is None:process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
        print('Stopped only own test API/source worker process trees; local DB untouched')
        if api_log:api_log.close()
if __name__=='__main__':main()
