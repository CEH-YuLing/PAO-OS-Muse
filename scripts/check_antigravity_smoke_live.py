"""Bounded native smoke under the user's explicit test instruction.

Uses the same transport as the API, not a diagnostic bearer POST. No retry.
Does not enroll a connection or enable chat. Native tool-gate failure is a
safety pass, NOT a successful model call.
"""
import asyncio, json, sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.config import settings
from pao.modules.cli_connections.antigravity_native import configuration,native_catalog
from pao.modules.cli_connections.antigravity_smoke import native_smoke,SmokeFailure,MODEL
from check_p84_foundation import binding,health

WID='ef221310-5afc-4c21-9f9e-4aa9bf4b3e79'
UID='165b1fa6-f443-4f66-bddb-51eb5b6e6fa5'

async def main():
    assert ROOT==Path('F:/PAO-ACOS')
    folder=ROOT/'.runtime'/('antigravity-native-smoke-'+uuid4().hex);folder.mkdir()
    url=make_url(settings().database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    engine=create_async_engine(url,connect_args={'server_settings':{
        'default_transaction_read_only':'on','statement_timeout':'10000'}})
    cfg,pin=configuration(WID,UID)
    result={'model':MODEL,'binding':binding(),'general_chat_enabled':False,
            'provider_support_confirmed':False,'API_POST_executed':False}
    async def recheck():
        assert configuration(WID,UID)[1]==pin
        async with engine.connect() as db:
            assert await db.scalar(text('SHOW transaction_read_only'))=='on'
            assert await db.scalar(text('SELECT count(*) FROM users u JOIN workspace_members m ON u.id=m.user_id '
                "WHERE u.id=:uid AND m.workspace_id=:wid AND u.active AND m.role IN ('owner','admin')"),
                {'uid':UID,'wid':WID})==1
    try:
        await recheck()
        models=await native_catalog(cfg)
        result['native_catalog_count']=len(models)
        assert MODEL in models
        try:result.update(await native_smoke(cfg,recheck))
        except SmokeFailure as exc:
            result.update(status='blocked',code=exc.code,inference_verified=False)
            # This code can only be raised while checking init, before stdin.write.
            if exc.code=='tools_not_disabled':result.update(prompt_sent=False,model_quota_test_sent=False)
        result['health']=health()
        result['transport_result_recorded']=True
    finally:
        await engine.dispose()
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
        print(json.dumps({'folder':str(folder),**result}))

if __name__=='__main__':asyncio.run(main())
