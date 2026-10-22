"""Read-only drift inventory, without row contents, credentials or device codes."""
import asyncio,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from sqlalchemy.engine import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import settings
from check_p11_migration import snapshot

async def main():
    assert ROOT==Path('F:/PAO-ACOS')
    url=make_url(settings().database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    install=ROOT/'.runtime/codex-login-install-99c13e0f331d49919c4cb90890a86aea'
    before=json.loads((install/'before.json').read_text())
    columns,old=before['snapshot'];_,current=await snapshot(url,columns)
    differences={name:{'before_count':old[name]['count'],'current_count':value['count']}
        for name,value in current.items() if value!=old[name]}
    events=[]
    for line in (install/'api.stderr.log').read_text(encoding='utf-8').splitlines():
        try:value=json.loads(line)
        except (ValueError,TypeError):continue
        if (value.get('event')=='http.request' and value.get('method') not in ('GET','HEAD','OPTIONS')
                and value.get('started_at','')>='2026-10-19T09:26:50'):
            events.append({key:value.get(key) for key in ('started_at','method','route','status')})
    dbengine=create_async_engine(url)
    try:
        async with dbengine.connect() as db:
            profile=(await db.execute(text("SELECT status,version,auth_checked_at IS NOT NULL AS auth_recorded,setup_operation_id IS NOT NULL AS operation_pending FROM cli_model_connections WHERE id='398aa03c-0465-426c-ad95-12d1d1cc475d' AND workspace_id='ef221310-5afc-4c21-9f9e-4aa9bf4b3e79' AND owner_id='165b1fa6-f443-4f66-bddb-51eb5b6e6fa5'"))).mappings().one()
            profile=dict(profile)
    finally:await dbengine.dispose()
    result={'comparison_pass':not differences,'changed_tables':differences,'write_request_metadata':events,
        'profile_metadata_only':profile,
        'user_confirmed_activity':True,'primary_restored':False,'row_contents_logged':False}
    folder=ROOT/'.runtime'/('codex-login-user-activity-'+uuid4().hex);folder.mkdir()
    (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(folder),**result}))

if __name__=='__main__':asyncio.run(main())
