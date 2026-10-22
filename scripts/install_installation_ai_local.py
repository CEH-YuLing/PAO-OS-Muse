"""Bounded local backend install, no CLI runtime swap or provider activation."""
import asyncio,contextlib,io,json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.config import settings
from check_installation_ai_migration import signatures
from check_m2_restore import inspect
from check_p84_foundation import binding,health
from pao.modules.operations.checkpoint import digest
import read_owned_pao_processes as owned


async def preflight():
    url=make_url(settings().database_url)
    assert ROOT==Path('F:/PAO-ACOS') and (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    engine=create_async_engine(url,connect_args={'server_settings':{'default_transaction_read_only':'on','statement_timeout':'5000'}})
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) in ('0074','0075')
            assert await db.scalar(text("SELECT count(*) FROM cli_model_dispatches WHERE status IN ('dispatched','unknown')"))==0
            assert await db.scalar(text('SELECT count(*) FROM cli_model_connections WHERE setup_operation_id IS NOT NULL'))==0
    finally:await engine.dispose()
    subprocess.run([sys.executable,'-B','scripts/check_acos_idle.py','--safe-repair'],cwd=ROOT,check=True,timeout=30)
    output=io.StringIO()
    with contextlib.redirect_stdout(output):owned.main()
    return json.loads(output.getvalue())


def main():
    assert sys.argv[1:]==['--install']
    checkpoint=ROOT/'.runtime/checkpoints/p0-20261020T132233-b4755cb9/manifest.json'
    manifest=json.loads(checkpoint.read_text())
    assert manifest['database']['revision_before']=='0074'
    assert digest(Path(manifest['database']['backup']))==manifest['database']['sha256']
    schema_probe=json.loads((ROOT/'.runtime/installation-ai-migration-0a58453fb696403e877e0b8c8c231b48/receipt.json').read_text())
    assert schema_probe['pass'] and schema_probe['old_tables_unchanged'] and schema_probe['archive_count']==3
    identities=asyncio.run(preflight())
    folder=ROOT/'.runtime'/('installation-ai-install-'+uuid4().hex);folder.mkdir()
    records_path=ROOT/'.runtime/acos-processes.json'
    records=json.loads(records_path.read_text())
    before_env=digest(ROOT/'.env');before_cli=digest(ROOT/'.runtime/cli-device.json');source=binding()
    state={'pass':False,'binding':source,'provider_calls':0,'runtime_swap':False,'checkpoint':str(checkpoint)}
    env={**os.environ,'PAO_ROOT':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1',
         'PYTHONPATH':os.pathsep.join(str(ROOT/p) for p in ('apps/api','packages/cli-runtime','scripts'))}
    try:
        # Both root identities were verified. Recheck each creation time and full
        # command immediately before terminating its owned process tree only.
        for name in ('api','worker'):
            current=owned.metadata(identities[name]['id'])
            assert current==identities[name] and current['started']==records[name]['started']
            subprocess.run(['taskkill','/PID',str(current['id']),'/T','/F'],check=True,capture_output=True,timeout=15)
        state['stopped_owned_api_worker']=True
        url=make_url(settings().database_url)
        before=asyncio.run(signatures(url));archive_before=asyncio.run(inspect(url))
        with (folder/'migration.log').open('wb') as log:
            subprocess.run([sys.executable,'-B','-m','alembic','upgrade','0075'],cwd=ROOT,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=90,check=True)
        after=asyncio.run(signatures(url));archive_after=asyncio.run(inspect(url))
        state['old_tables_unchanged']=all(after.get(k)==v for k,v in before.items() if k!='alembic_version')
        state['archives_unchanged']=archive_before['artifact_hashes']==archive_after['artifact_hashes']
        assert state['old_tables_unchanged'] and state['archives_unchanged'] and archive_after['revision']=='0075'
        state.update(schema='0075',physical_tables=len(after),archive_count=len(archive_after['artifact_hashes']))
        for name,args in [('api',['-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8100','--no-access-log']),
                          ('worker',['-m','arq','pao.runtime.WorkerSettings'])]:
            with (folder/(name+'.stdout.log')).open('xb') as out,(folder/(name+'.stderr.log')).open('xb') as err:
                process=subprocess.Popen([sys.executable,*args],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
                    stdout=out,stderr=err,creationflags=0x08000000|0x00000008)
            value=owned.metadata(process.pid)
            records[name]={'id':value['id'],'started':value['started']}
            records_path.write_text(json.dumps(records,indent=2),encoding='utf-8')
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            if health()['api']==200:break
            time.sleep(.5)
        with (folder/'health.log').open('wb') as log:
            subprocess.run([sys.executable,'-B','scripts/check_acos_health.py'],cwd=ROOT,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=50,check=True)
        from urllib.request import build_opener,ProxyHandler
        opener=build_opener(ProxyHandler({}))
        with opener.open('http://127.0.0.1:8100/openapi.json',timeout=10) as response:live=json.load(response)
        from pao.main import app
        state['contract_match']=live==app.openapi()
        state['operations']=sum(k.lower() in ('get','post','put','patch','delete','head','options','trace') for p in live['paths'].values() for k in p)
        state['health']=health()
        state['env_unchanged']=before_env==digest(ROOT/'.env')
        state['cli_registry_unchanged']=before_cli==digest(ROOT/'.runtime/cli-device.json')
        state['binding_unchanged_during_install']=source==binding()
        state['pass']=all(state[k] for k in ('contract_match','env_unchanged','cli_registry_unchanged','binding_unchanged_during_install')) and all(v==200 for v in state['health'].values())
    finally:
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**state}))
    assert state['pass']


if __name__=='__main__':main()
