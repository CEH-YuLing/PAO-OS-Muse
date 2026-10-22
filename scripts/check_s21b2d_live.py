"""Read-only installed source/contract/DB verification; no provider calls."""
import asyncio,json
from uuid import uuid4
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
import httpx
from pao.auth import issue_token
from pao.config import settings,ROOT
from pao.db import Session,engine
from pao.models import ConnectionReadActivation,Member,User,TenantConnectionReference
from pao.skills import execution_binding
from check_m2_restore import inspect


async def main():
    assert str(ROOT)=='F:\\PAO-ACOS' and settings().database_url.endswith('/pao_acos_local')
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0052'
            for model in (ConnectionReadActivation,TenantConnectionReference):
                assert await db.scalar(select(model.id).limit(1)) is None
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            ops=sum(m in ('get','post','put','patch','delete','head','options') for value in saved['paths'].values() for m in value)
            assert ops==327
            rows=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(
                Member.role.in_(('owner','admin')),User.active.is_(True))))
            assert rows
            for member in rows:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)}
                base=f'/v1/workspaces/{member.workspace_id}/connection-inventory'
                response=await client.get(base+'/ads-grants',headers=headers)
                assert response.status_code==200 and response.json()['items']==[] and response.headers['cache-control']=='no-store'
                assert (await client.get(base+'/ads-grants')).status_code==401
                bad=await client.post(base+f'/references/{uuid4()}/grants/{uuid4()}/activate-ads',headers=headers,
                    json={'token':'redaction-marker-not-credential'})
                assert bad.status_code==422 and 'redaction-marker-not-credential' not in bad.text
                skills=await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})
                assert skills.status_code==200 and all(row['execution_binding']==execution_binding() for row in skills.json())
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archive=await inspect(make_url(settings().database_url));assert len(archive['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0052','operations':ops,'manager_scopes':len(rows),
            'binding':execution_binding(),'m2_replay':'3/3','live_grants':0,'external_calls':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
