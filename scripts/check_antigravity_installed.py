"""Read-only installation evidence; no native provider/model invocation."""
import argparse,asyncio,hashlib,json,sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import make_url
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.config import settings
from check_p84_foundation import health
from check_m2_restore import inspect

FOLDER=ROOT/'.runtime/antigravity-native-installed-20261020'

async def snapshot():
    cfg=settings();url=make_url(cfg.database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    engine=create_async_engine(url,connect_args={'server_settings':{'default_transaction_read_only':'on','statement_timeout':'10000'}})
    hashes={}
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SHOW transaction_read_only'))=='on'
            for table in await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")):
                name='"'+table.replace('"','""')+'"'
                rows=sorted(await db.scalars(text('SELECT row_to_json(t)::text FROM '+name+' t')))
                hashes[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
    finally:await engine.dispose()
    archive=await inspect(url)
    return {'tables':hashes,'schema':archive['revision'],'archives':archive['artifact_hashes'],
            'env_sha256':hashlib.sha256((ROOT/'.env').read_bytes()).hexdigest(),
            'cli_registry_sha256':hashlib.sha256((ROOT/'.runtime/cli-device.json').read_bytes()).hexdigest()}

async def main(action):
    FOLDER.mkdir(exist_ok=True)
    result=await snapshot()
    if action=='before':
        with (FOLDER/'before.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
        print(json.dumps({'saved':str(FOLDER),'schema':result['schema'],'tables':len(result['tables']),'archives':len(result['archives'])}));return
    before=json.loads((FOLDER/'before.json').read_text())
    result['tables_unchanged']=before['tables']==result['tables']
    result['archives_unchanged']=before['archives']==result['archives']
    result['env_registry_unchanged']=before['env_sha256']==result['env_sha256'] and before['cli_registry_sha256']==result['cli_registry_sha256']
    contract=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    async with httpx.AsyncClient(base_url='http://127.0.0.1:8100',trust_env=False,timeout=10) as client:
        result['live_contract_match']=(await client.get('/openapi.json')).json()==contract
        result['unauthenticated_denied']=(await client.get('/v1/workspaces/ef221310-5afc-4c21-9f9e-4aa9bf4b3e79/antigravity-native')).status_code==401
    result['health']=health();result['provider_calls']=0;result['inference_called']=False
    result['pass']=all(result[k] for k in ('tables_unchanged','archives_unchanged','env_registry_unchanged','live_contract_match','unauthenticated_denied')) and all(v==200 for v in result['health'].values())
    with (FOLDER/'after.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('tables','archives','env_sha256','cli_registry_sha256')}))
    raise SystemExit(0 if result['pass'] else 1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['before','after'])
    asyncio.run(main(parser.parse_args().action))
