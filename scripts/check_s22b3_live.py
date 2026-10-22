"""Installed three Settings pools; read-only, no discovery/provider execution."""
import asyncio,json,subprocess
from pathlib import Path
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User,TenantResourcePolicy,TenantReadPolicy,TenantMetadataPolicy
from pao.modules.operations.checkpoint import digest
from pao.skills import execution_binding
from check_p11_migration import snapshot


async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    assert digest(ROOT/'.env')=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    models=(TenantResourcePolicy,TenantReadPolicy,TenantMetadataPolicy)
    columns={model.__tablename__:[column.name for column in model.__table__.columns] for model in models}
    try:
        before=await snapshot(make_url(settings().database_url),columns)
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0058'
            source=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==source
            members=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(Member.role.in_(('owner','admin')),User.active.is_(True))))
            assert members
            samples=[]
            for member in members:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)}
                for pool in ('models','reads','metadata'):
                    response=await client.get(f'/v1/workspaces/{member.workspace_id}/resources/{pool}',headers=headers)
                    assert response.status_code==200 and response.headers['cache-control']=='no-store'
                    samples.append({'pool':pool,'workspace':member.workspace_id,'data':response.json()})
            check="import {validateResourceSnapshot} from './apps/web/lib/resource-quota.mjs'; let input=''; for await(const chunk of process.stdin)input+=chunk; for(const x of JSON.parse(input))validateResourceSnapshot(x.pool,x.data,x.workspace);"
            result=await asyncio.to_thread(subprocess.run,['node','--input-type=module','-e',check],cwd=ROOT,input=json.dumps(samples),text=True,capture_output=True,timeout=15)
            assert result.returncode==0,'Installed Settings snapshot failed strict frontend validation'
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        assert await snapshot(make_url(settings().database_url),columns)==before
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        print(json.dumps({'pass':True,'revision':'0058','operations':334,'binding':execution_binding(),
            'settings_pool_snapshots':len(samples),'strict_frontend_validation':True,
            'policies_hashes_unchanged':True,'policy_rows':{key:value['count'] for key,value in before[1].items()},
            'external_calls':False,'production_accepted':False,'full_S2_accepted':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
