"""Installed Team Settings metadata; read-only, no secrets/provider or grants."""
import asyncio,json,subprocess
from pathlib import Path
import httpx
from sqlalchemy import select
from sqlalchemy.engine import make_url
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import Member,User,Brand,TenantConnectionGrant,TenantConnectionReference
from check_p11_migration import snapshot

async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    models=(Member,User,Brand,TenantConnectionGrant,TenantConnectionReference)
    columns={model.__tablename__:[column.name for column in model.__table__.columns] for model in models}
    try:
        before=await snapshot(make_url(settings().database_url),columns)
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)))
            assert owner
            response=await client.get(f'/v1/workspaces/{owner.workspace_id}/connection-inventory/options',headers={'Authorization':'Bearer '+issue_token(owner.user_id)})
            assert response.status_code==200 and response.headers['cache-control']=='no-store'
            check="import {settingsTeam} from './apps/web/lib/settings-team.mjs';let x='';for await(const c of process.stdin)x+=c;const v=settingsTeam(JSON.parse(x));console.log(JSON.stringify({members:v.members.length,brands:v.brands.length,has_more:v.has_more}));"
            result=await asyncio.to_thread(subprocess.run,['node','--input-type=module','-e',check],cwd=ROOT,input=response.text,text=True,capture_output=True,timeout=15)
            assert result.returncode==0,'Installed team snapshot failed profile validation'
        assert await snapshot(make_url(settings().database_url),columns)==before
        print(json.dumps({'pass':True,'native_team_snapshot':json.loads(result.stdout),'team_and_grant_hashes_unchanged':True,'external_calls':False,'mutation_applied':False}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
