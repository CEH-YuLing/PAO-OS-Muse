"""Post-rollout0060/338/current binding; GET-only, never choose/apply a legacy mapping."""
import asyncio,json
from pathlib import Path
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
    before=await snapshot(url);env=digest(ROOT/'.env');binding=execution_binding()
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0060'
            for table in ('telegram_legacy_mappings','telegram_legacy_peer_maps','telegram_legacy_mapping_audits'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0,'Owner must choose mapping explicitly, not rollout'
            assert await db.scalar(text("SELECT count(*) FROM telegram_connections WHERE kind='legacy'"))==0
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            operations=sum(key in ('get','post','put','patch','delete','head','options') for methods in saved['paths'].values() for key in methods)
            assert operations==338
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)))
            assert member;headers={'Authorization':'Bearer '+issue_token(member.user_id)}
            base='/v1/telegram/legacy/'+member.workspace_id
            for endpoint in ('preview','mapping'):
                result=await client.get(base+'/'+endpoint,headers=headers);assert result.status_code==200 and result.headers['cache-control']=='no-store'
                if endpoint=='mapping':assert result.json() is None
                else:assert result.json()['workspace_id']==member.workspace_id and result.json()['provider_calls'] is False
                denied=await client.get(base+'/'+endpoint);assert denied.status_code==401 and denied.headers['cache-control']=='no-store'
                foreign=await client.get('/v1/telegram/legacy/00000000-0000-0000-0000-000000000000/'+endpoint,headers=headers)
                assert foreign.status_code==404 and foreign.headers['cache-control']=='no-store'
            telegram=await client.get('/v1/telegram/status',headers=headers);assert telegram.status_code==200 and telegram.json()['enabled'] is False
            skills=await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})
            assert skills.status_code==200 and all(row['execution_binding']==binding for row in skills.json())
            write=(await client.get('/v1/ads/write-status',headers=headers)).json();autopilot=(await client.get('/v1/ads/autopilot/status',headers=headers)).json()
            assert write['enabled'] is False and autopilot['global_enabled'] is autopilot['meta_enabled'] is False
            for route in ('/health','/ready'):assert (await client.get(route)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archived=await inspect(url);assert archived['revision']=='0060' and len(archived['counts'])==129 and len(archived['artifact_hashes'])==3
        assert await snapshot(url)==before and digest(ROOT/'.env')==env and execution_binding()==binding
        print(json.dumps({'pass':True,'revision':'0060','operations':operations,'binding':binding,'physical_tables':129,'m2_archives_verified':3,
            'business_hashes_unchanged':True,'env_unchanged':True,'automatic_mapping':False,'provider_calls':False,'production_accepted':False}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
