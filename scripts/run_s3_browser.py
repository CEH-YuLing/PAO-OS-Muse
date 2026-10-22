"""Own empty DB + private API process; can run beside pao_test without collision."""
import asyncio,json,os,re,secrets,socket,subprocess,sys,time,urllib.request
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,Member
from pao.auth import passwords
from check_p11_migration import CONTAINER
from cryptography.fernet import Fernet


async def seed(url):
    db=create_async_engine(url);session=async_sessionmaker(db,expire_on_commit=False)
    try:
        async with session.begin() as s:
            user=User(email='owner@example.test',password_hash=passwords.hash('test-password-123'))
            a=Workspace(name='Doanh nghiệp thử A');b=Workspace(name='Doanh nghiệp thử B');s.add_all([user,a,b]);await s.flush()
            s.add_all([Member(workspace_id=a.id,user_id=user.id,role='owner'),Member(workspace_id=b.id,user_id=user.id,role='operator')])
        return a.id,b.id
    finally:await db.dispose()


def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',18100))==0:raise SystemExit('Port18100 occupied; refuse reuse')
    name='pao_s3_browser_'+uuid4().hex;assert re.fullmatch('pao_s3_browser_[0-9a-f]{32}',name)
    created=False;process=None
    def docker(*args):subprocess.run(['docker','exec',CONTAINER,*args],check=True,timeout=90)
    try:
        docker('createdb','-U','pao',name);created=True
        target=url.set(database=name).render_as_string(hide_password=False)
        env={**os.environ,'DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(settings().redis_url)._replace(path='/15')),
            'JWT_SECRET':'synthetic-browser-only-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
            'TELEGRAM_ENABLED':'false','TELEGRAM_SCOPED_RUNTIME_ENABLED':'true','CHANNELS_ENABLED':'true','BRAIN_MANAGER_ENABLED':'true',
            'TELEGRAM_PUBLIC_BASE_URL':'https://pao.fixture.invalid','META_ENABLED':'false','META_WRITE_ENABLED':'false','GOOGLE_ADS_ENABLED':'false',
            'ADS_AUTOPILOT_GLOBAL_ENABLED':'false','META_AUTOPILOT_ENABLED':'false','MEMORY_ENABLED':'false','TOOLS_ENABLED':'false','AGENT_RUNTIME_ENABLED':'false',
            'PAO_S3_BROWSER_TEST':'1','PAO_S3_BROWSER_KEY':secrets.token_urlsafe(32)}
        subprocess.run([sys.executable,'-m','alembic','upgrade','0065'],cwd=ROOT,env=env,check=True,timeout=120)
        a,b=asyncio.run(seed(target))
        fixture={'api':'http://127.0.0.1:18100','web':'http://127.0.0.1:3200','workspace':a,'second':b,
            'fixtureKey':env['PAO_S3_BROWSER_KEY'],'screenshot':str(ROOT/'.runtime/s3-telegram-mobile.png')}
        env['PAO_S3_BROWSER']=json.dumps(fixture)
        with (ROOT/'.runtime/s3-browser-api.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,'scripts/s3_browser_api.py'],cwd=ROOT,env=env,stdout=log,stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            for attempt in range(40):
                if process.poll() is not None:raise RuntimeError('Owned browser API exited')
                try:
                    with urllib.request.urlopen(fixture['api']+'/ready',timeout=2) as r:
                        if r.status==200:break
                except Exception:pass
                time.sleep(.5)
            else:raise RuntimeError('Owned browser API not ready')
            subprocess.run(['node','scripts/verify_s3_browser.cjs'],cwd=ROOT,env=env,check=True,timeout=240)
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=15)
        if created:docker('dropdb','-U','pao',name);print('Removed only owned empty browser DB; stopped only owned test API; primary untouched.')


if __name__=='__main__':main()
