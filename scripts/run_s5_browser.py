"""S5 candidate UI acceptance in an owned database/API; flag process-only."""
import asyncio,json,os,re,secrets,socket,subprocess,sys,time,urllib.request
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from check_p11_migration import CONTAINER
from run_s3_browser import seed
from check_p11_migration import snapshot
from check_s03_restore import schema
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import DBAPIError


async def restored_candidate(original,target):
    assert await snapshot(original)==await snapshot(target)
    assert await schema(original)==await schema(target)
    engine=create_async_engine(target)
    try:
        try:
            async with engine.begin() as db:await db.execute(text("UPDATE business_plan_reviews SET decision='reject'"))
        except DBAPIError:pass
        else:raise AssertionError('Restored review ledger lost immutable trigger')
        try:
            async with engine.begin() as db:await db.execute(text("UPDATE business_routing_versions SET content_hash=repeat('0',64)"))
        except DBAPIError:pass
        else:raise AssertionError('Restored routing history lost immutable trigger')
        for table in ('business_jobs','business_plan_events','business_budgets','business_actions','business_budget_entries'):
            async with engine.connect() as db:assert await db.scalar(text('SELECT count(*) FROM '+table))>0
            try:
                async with engine.begin() as db:await db.execute(text('DELETE FROM '+table))
            except DBAPIError:pass
            else:raise AssertionError('Restored S5 operations lost immutable trigger')
        assert await snapshot(original)==await snapshot(target)
    finally:await engine.dispose()


def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',18102))==0:raise RuntimeError('Test API port occupied; refuse reuse')
    name='pao_s5_browser_'+uuid4().hex;assert re.fullmatch('pao_s5_browser_[0-9a-f]{32}',name)
    created=False;restored=False;restore_name='pao_s5_restore_'+uuid4().hex;process=None
    def docker(*args):subprocess.run(['docker','exec',CONTAINER,*args],check=True,timeout=90)
    try:
        docker('createdb','-U','pao',name);created=True
        target=url.set(database=name).render_as_string(hide_password=False)
        env={**os.environ,'DATABASE_URL':target,'REDIS_URL':urlunsplit(urlsplit(settings().redis_url)._replace(path='/15')),
            'JWT_SECRET':'synthetic-browser-'+secrets.token_hex(24),'BUSINESS_PLANNING_ENABLED':'true',
            'META_ENABLED':'false','GOOGLE_ADS_ENABLED':'false','META_WRITE_ENABLED':'false','META_AUTOPILOT_ENABLED':'false',
            'ADS_AUTOPILOT_GLOBAL_ENABLED':'false','TELEGRAM_ENABLED':'false','TELEGRAM_SCOPED_RUNTIME_ENABLED':'false',
            'CHANNELS_ENABLED':'false','TEMPORAL_ENABLED':'false','MEMORY_ENABLED':'false','TOOLS_ENABLED':'false','AGENT_RUNTIME_ENABLED':'false',
            'STUDIO_ENABLED':'true','ENGINE_CONTRACT_ENABLED':'true','CHAT_FEATURES_ENABLED':'true',
            'PAO_S5_BROWSER_TEST':'1','PAO_S5_BROWSER_KEY':secrets.token_urlsafe(32)}
        subprocess.run([sys.executable,'-m','alembic','upgrade','0070'],cwd=ROOT,env=env,check=True,timeout=120)
        a,b=asyncio.run(seed(target))
        env['PAO_S5_BROWSER']=json.dumps({'api':'http://127.0.0.1:18102','web':'http://127.0.0.1:3200','workspace':a,'second':b,
            'fixture_key':env['PAO_S5_BROWSER_KEY'],'screenshot':str(ROOT/'.runtime/s5-authoring-mobile.png')})
        with (ROOT/'.runtime/s5-browser-api.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,'scripts/s5_browser_api.py'],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            for attempt in range(40):
                if process.poll() is not None:raise RuntimeError('Owned API exited')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:18102/ready',timeout=2) as response:
                        if response.status==200:break
                except Exception:pass
                time.sleep(.5)
            else:raise RuntimeError('Owned API not ready')
            checked=subprocess.run(['node','scripts/verify_s5_browser.cjs'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=300)
            print(checked.stdout,end='');print(checked.stderr,end='',file=sys.stderr);checked.check_returncode()
            result=json.loads(next(line for line in checked.stdout.splitlines() if line.startswith('{"pass":true')))
            assert result['pass']
            assert re.fullmatch('pao_s5_restore_[0-9a-f]{32}',restore_name)
            backup=ROOT/'.runtime'/('s5-browser-populated-'+uuid4().hex+'.dump')
            with backup.open('xb') as saved:
                subprocess.run(['docker','exec',CONTAINER,'pg_dump','-U','pao','-d',name,'-Fc'],stdout=saved,check=True,timeout=90)
            docker('createdb','-U','pao',restore_name);restored=True
            with backup.open('rb') as saved:
                subprocess.run(['docker','exec','-i',CONTAINER,'pg_restore','-U','pao','-d',restore_name,'--no-owner','--exit-on-error'],stdin=saved,check=True,timeout=90)
            asyncio.run(restored_candidate(url.set(database=name),url.set(database=restore_name)))
            result.update(populated_restore=True,restored_review_immutable=True,restored_routing_immutable=True,backup=str(backup))
            (ROOT/'.runtime/s5-browser.json').write_text(json.dumps(result),encoding='utf-8')
            print(json.dumps({'pass':True,'populated_restore':True,'restored_review_immutable':True,'primary_unchanged':True}))
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=15)
        if restored:docker('dropdb','-U','pao',restore_name)
        if created:docker('dropdb','-U','pao',name);print('Removed only owned S5 browser/restore databases and API; backup retained; primary untouched.')


if __name__=='__main__':main()
