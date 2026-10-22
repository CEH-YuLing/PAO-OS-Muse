"""Browser acceptance on a new owned DB/API, independent from pao_test."""
import asyncio,json,os,re,secrets,socket,subprocess,sys,time,urllib.request
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from sqlalchemy.engine import make_url
from cryptography.fernet import Fernet
from pao.config import ROOT,settings
from check_p11_migration import CONTAINER
from run_s3_browser import seed


def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',18101))==0:raise RuntimeError('Owned API port occupied; refuse reuse')
    name='pao_s4_browser_'+uuid4().hex;assert re.fullmatch('pao_s4_browser_[0-9a-f]{32}',name)
    created=False;process=None
    def docker(*args):subprocess.run(['docker','exec',CONTAINER,*args],check=True,timeout=90)
    try:
        docker('createdb','-U','pao',name);created=True
        target=url.set(database=name).render_as_string(hide_password=False)
        env={**os.environ,'DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(settings().redis_url)._replace(path='/15')),'JWT_SECRET':'synthetic-browser-'+secrets.token_hex(24),
            'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),'PAO_S4_BROWSER_TEST':'1','PAO_S4_FIXTURE_KEY':secrets.token_urlsafe(32),
            'META_ENABLED':'true','META_APP_ID':'123','META_APP_SECRET':'synthetic-host-secret','META_GRAPH_API_VERSION':'v26.0',
            'META_REDIRECT_URI':'http://127.0.0.1:3200/v1/integrations/meta/callback','GOOGLE_ADS_ENABLED':'false',
            'GOOGLE_ADS_REDIRECT_URI':'http://127.0.0.1:3200/v1/integrations/google-ads/callback',
            'META_WRITE_ENABLED':'false','META_AUTOPILOT_ENABLED':'false','ADS_AUTOPILOT_GLOBAL_ENABLED':'false',
            'TELEGRAM_ENABLED':'false','TELEGRAM_SCOPED_RUNTIME_ENABLED':'false','CHANNELS_ENABLED':'false',
            'TEMPORAL_ENABLED':'false','MEMORY_ENABLED':'false','TOOLS_ENABLED':'false','AGENT_RUNTIME_ENABLED':'false'}
        subprocess.run([sys.executable,'-m','alembic','upgrade','0065'],cwd=ROOT,env=env,check=True,timeout=120)
        a,b=asyncio.run(seed(target))
        env['PAO_S4_BROWSER']=json.dumps({'api':'http://127.0.0.1:18101','web':'http://127.0.0.1:3200','workspace':a,'second':b,'fixtureKey':env['PAO_S4_FIXTURE_KEY'],'screenshot':str(ROOT/'.runtime/s4-apps-mobile.png')})
        with (ROOT/'.runtime/s4-browser-api.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,'scripts/s4_browser_api.py'],cwd=ROOT,env=env,stdout=log,stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            for attempt in range(40):
                if process.poll() is not None:raise RuntimeError('Owned browser API exited')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:18101/ready',timeout=2) as response:
                        if response.status==200:break
                except Exception:pass
                time.sleep(.5)
            else:raise RuntimeError('Owned browser API not ready')
            checked=subprocess.run(['node','scripts/verify_s4_browser.cjs'],cwd=ROOT,env=env,capture_output=True,text=True,check=False,timeout=240)
            print(checked.stdout,end='');print(checked.stderr,end='',file=sys.stderr)
            checked.check_returncode()
            result=json.loads(next(line for line in checked.stdout.splitlines() if line.startswith('{"pass":true')))
            assert result['pass'] and result['real_api_db'] and result['synthetic_oauth']
            (ROOT/'.runtime/s4-browser.json').write_text(json.dumps(result),encoding='utf-8')
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=15)
        if created:docker('dropdb','-U','pao',name);print('Stopped only owned test API; removed only owned browser DB; primary untouched.')


if __name__=='__main__':main()
