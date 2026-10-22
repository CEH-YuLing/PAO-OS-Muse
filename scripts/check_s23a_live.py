"""Nine installed GET snapshots through the same UI validator, no provider probe."""
import asyncio,json,subprocess
from pathlib import Path
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import Member,User,ModelProviderConnection,MetaConnection,GoogleAdsConnection,ConnectorConnection
from pao.modules.operations.checkpoint import digest
from pao.skills import execution_binding
from check_p11_migration import snapshot


async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    assert digest(ROOT/'.env')=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    models=(ModelProviderConnection,MetaConnection,GoogleAdsConnection,ConnectorConnection)
    columns={model.__tablename__:[column.name for column in model.__table__.columns] for model in models}
    paths=('/v1/integrations/meta/connection','/v1/integrations/google-ads/connection','/v1/telegram/status','/v1/voice/status','/v1/automation/status','/v1/ads/write-status','/v1/ads/autopilot/status','/v1/platform/catalog','/v1/model-providers')
    try:
        before=await snapshot(make_url(settings().database_url),columns)
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0058'
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)))
            assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)};samples={}
            for index,path in enumerate(paths):
                route=path+('?workspace_id='+owner.workspace_id if index in (0,1,7,8) else '')
                response=await client.get(route,headers=headers);assert response.status_code==200
                samples[route]=response.json()
            check="import {collectSettingsStatus} from './apps/web/lib/settings-status.mjs'; let input='';for await(const chunk of process.stdin)input+=chunk;const x=JSON.parse(input);const r=await collectSettingsStatus(x.workspace,async path=>x.samples[path]);if(r.failed.length)throw new Error('Installed snapshot failed: '+r.failed.join(','));console.log(r.responding);"
            result=await asyncio.to_thread(subprocess.run,['node','--input-type=module','-e',check],cwd=ROOT,input=json.dumps({'workspace':owner.workspace_id,'samples':samples}),text=True,capture_output=True,timeout=15)
            assert result.returncode==0,'Installed status snapshot failed validation'
            assert result.stdout.strip()=='9'
            source=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==source
            operations=sum(method in ('get','post','put','patch','delete','head','options') for methods in source['paths'].values() for method in methods)
            assert operations==334
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        assert await snapshot(make_url(settings().database_url),columns)==before
        print(json.dumps({'pass':True,'revision':'0058','operations':operations,'binding':execution_binding(),
            'validated_observations':9,'native_connection_hashes_unchanged':True,'env_unchanged':True,
            'external_calls':False,'full_S23_accepted':False,'full_S2_accepted':False,'production_accepted':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
