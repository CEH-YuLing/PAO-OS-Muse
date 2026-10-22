"""Installed S2 GET-only gate; no consent, jobs, secrets, probe or provider calls."""
import asyncio,json
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import Member,User
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_m2_restore import inspect

async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    env=digest(ROOT/'.env');binding=execution_binding();before=await snapshot(url)
    checked=0
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0058'
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            operations=sum(key in ('get','post','put','patch','delete','head','options') for methods in saved['paths'].values() for key in methods)
            assert operations==334
            members=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(Member.role.in_(('owner','admin')),User.active.is_(True))))
            assert members
            for member in members:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)};base=f'/v1/workspaces/{member.workspace_id}'
                routes=[base+'/connection-inventory',base+'/connection-inventory/options',base+'/connection-inventory/references',base+'/model-grants',base+'/connection-inventory/ads-grants']+[base+'/resources/'+pool for pool in ('models','reads','metadata')]
                for route in routes:
                    response=await client.get(route,headers=headers)
                    assert response.status_code==200 and response.headers['cache-control']=='no-store'
                    assert (await client.get(route)).status_code==401
                    checked+=1
                inventory=(await client.get(routes[0],headers=headers)).json()
                assert inventory['external_calls'] is inventory['credentials_loaded'] is inventory['mutation_applied'] is False
                assert all(row['identity']['workspace_id']==member.workspace_id for row in inventory['items'])
                unknown=f'/v1/workspaces/{uuid4()}/connection-inventory'
                assert (await client.get(unknown,headers=headers)).status_code==404
                skills=await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})
                assert skills.status_code==200 and all(row['execution_binding']==binding for row in skills.json())
                write=(await client.get('/v1/ads/write-status',headers=headers)).json()
                autopilot=(await client.get('/v1/ads/autopilot/status',headers=headers)).json()
                assert write['enabled'] is False and autopilot['global_enabled'] is autopilot['meta_enabled'] is False
            for route in ('/health','/ready'):assert (await client.get(route)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archived=await inspect(url)
        assert archived['revision']=='0058' and len(archived['counts'])==125 and len(archived['artifact_hashes'])==3
        assert await snapshot(url)==before and digest(ROOT/'.env')==env and execution_binding()==binding
        print(json.dumps({'pass':True,'revision':'0058','operations':operations,'manager_scopes':len(members),'scoped_gets':checked,'binding':binding,'m2_archives_verified':3,'physical_tables':125,'all_business_hashes_unchanged':True,'env_unchanged':True,'write_gates_off':True,'external_calls':False,'production_accepted':False,'full_regression_gate':'separate evidence required'}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
