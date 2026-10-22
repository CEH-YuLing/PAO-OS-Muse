"""Installed model resource metadata only; no inference/credential/provider calls."""
import asyncio,json
from uuid import uuid4
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import Member,User
from pao.skills import execution_binding
from pao.modules.connections.resources import DEFAULTS
from check_m2_restore import inspect


async def main():
    assert str(ROOT)=='F:\\PAO-ACOS' and settings().database_url.endswith('/pao_acos_local')
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0054'
            for table in ('tenant_resource_policies','tenant_model_leases','tenant_connection_references'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            ops=sum(m in ('get','post','put','patch','delete','head','options') for value in saved['paths'].values() for m in value);assert ops==330
            rows=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(
                Member.role.in_(('owner','admin')),User.active.is_(True))))
            assert rows
            for member in rows:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)}
                route=f'/v1/workspaces/{member.workspace_id}/resources/models'
                result=await client.get(route,headers=headers)
                assert result.status_code==200 and result.headers['cache-control']=='no-store'
                body=result.json();assert body['model_policy']=={'version':0,**DEFAULTS}
                assert body['usage']['billing_amount'] is None and body['usage']['provider_subscription_remaining'] is None
                assert (await client.get(route)).status_code==401
                assert (await client.get(f'/v1/workspaces/{uuid4()}/resources/models',headers=headers)).status_code==404
                bad=await client.put(route,headers=headers,json={'api_key':'fixture-redaction-marker-not-key'})
                assert bad.status_code==422 and 'fixture-redaction-marker-not-key' not in bad.text
                skills=await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})
                assert skills.status_code==200 and all(row['execution_binding']==execution_binding() for row in skills.json())
            for route in ('/health','/ready'):assert (await client.get(route)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archive=await inspect(make_url(settings().database_url));assert len(archive['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0054','operations':ops,'manager_scopes':len(rows),
            'binding':execution_binding(),'m2_replay':'3/3','live_policy_or_lease':0,'external_calls':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
