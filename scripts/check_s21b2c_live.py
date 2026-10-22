"""Installed 0051 contract/scoped metadata, no consent or provider calls."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import ConnectionReadActivation,Member,ModelGrantActivation,TenantConnectionAudit,TenantConnectionGrant,TenantConnectionReference,User
from pao.skills import execution_binding
from check_m2_restore import inspect


async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    checked=0
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0051'
            for model in (ConnectionReadActivation,ModelGrantActivation,TenantConnectionReference,TenantConnectionGrant,TenantConnectionAudit):
                assert await db.scalar(select(model.id).limit(1)) is None
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            ops=sum(m in ('get','post','put','patch','delete','head','options') for value in saved['paths'].values() for m in value)
            assert ops==323
            rows=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(
                Member.role.in_(('owner','admin')),User.active.is_(True))))
            assert rows
            for member in rows:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)}
                base=f'/v1/workspaces/{member.workspace_id}/connection-inventory'
                response=await client.get(base+'/references',headers=headers)
                assert response.status_code==200 and response.json()['items']==[]
                options=await client.get(base+'/options',headers=headers)
                assert options.status_code==200 and options.headers['cache-control']=='no-store'
                catalog='/v1/connectors/grants'
                values=await client.get(catalog,headers=headers,params={'workspace_id':member.workspace_id})
                if settings().connectors_enabled:
                    assert values.status_code==200 and values.json()['items']==[] and values.headers['cache-control']=='no-store'
                else:assert values.status_code==503 and values.json()['detail']=='connectors_disabled'
                assert (await client.get(catalog,params={'workspace_id':member.workspace_id})).status_code==401
                bad=await client.post(base+f'/references/{uuid4()}/grants/{uuid4()}/activate-mcp',headers=headers,
                                     json={'token':'redaction-marker-not-credential'})
                assert bad.status_code==422 and 'redaction-marker-not-credential' not in bad.text
                skills=await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})
                assert skills.status_code==200 and all(row['execution_binding']==execution_binding() for row in skills.json())
                checked+=1
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archived=await inspect(make_url(settings().database_url));assert len(archived['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0051','operations':ops,'manager_scopes':checked,'binding':execution_binding(),
            'm2_replay':'3/3','live_consents':0,'connectors_enabled':settings().connectors_enabled,'external_calls':False,
            'external_server_accepted':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
