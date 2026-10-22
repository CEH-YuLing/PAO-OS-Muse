"""Installed0064/349/binding + read-only replay; never configure/send real bot."""
import asyncio,json
import httpx
from pathlib import Path
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
    assert not settings().telegram_enabled and not settings().telegram_scoped_runtime_enabled
    before=await snapshot(url);env=digest(ROOT/'.env');binding=execution_binding()
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0064'
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            operations=sum(k in ('get','post','put','patch','delete','head','options') for methods in saved['paths'].values() for k in methods)
            assert operations==349
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)))
            assert member;headers={'Authorization':'Bearer '+issue_token(member.user_id)}
            for path in ('/v1/telegram/scoped?workspace_id='+member.workspace_id,'/v1/telegram/scoped/destinations?workspace_id='+member.workspace_id):
                r=await client.get(path,headers=headers);assert r.status_code==200 and r.headers['cache-control']=='no-store'
                assert (await client.get(path)).status_code==401
            scoped=(await client.get('/v1/telegram/scoped',params={'workspace_id':member.workspace_id},headers=headers)).json()
            assert scoped['workspace_id']==member.workspace_id and scoped['runtime_available'] is False
            assert (await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})).status_code==200
            skills=(await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})).json()
            assert all(row['execution_binding']==binding for row in skills)
            catalog=(await client.get('/v1/platform/catalog',headers=headers,params={'workspace_id':member.workspace_id})).json()
            assert catalog['operations']['telegram_scoped_worker']['status']=='disabled'
            write=(await client.get('/v1/ads/write-status',headers=headers)).json();auto=(await client.get('/v1/ads/autopilot/status',headers=headers)).json()
            assert write['enabled'] is False and auto['global_enabled'] is auto['meta_enabled'] is False
            replays=0
            for rid,plan in await db.execute(text("SELECT r.id,r.execution_plan FROM runs r JOIN sessions s ON s.id=r.session_id AND s.workspace_id=r.workspace_id WHERE r.workspace_id=:wid AND s.user_id=:uid AND r.status='completed'"),{'wid':member.workspace_id,'uid':member.user_id}):
                if not (plan or {}).get('skill_artifact'):continue
                r=await client.get('/v1/runs/'+str(rid)+'/skill-replay',headers=headers)
                assert r.status_code==200 and r.json()['hash']==plan['skill_artifact']['hash'] and r.json()['tools_reexecuted'] is False
                replays+=1
            for aid,tid,archive in await db.execute(text('SELECT a.id,a.task_id,a.skill_artifact FROM task_attempts a JOIN tasks t ON t.id=a.task_id WHERE a.workspace_id=:wid AND a.skill_artifact IS NOT NULL'),{'wid':member.workspace_id}):
                r=await client.get('/v1/tasks/'+str(tid)+'/attempts/'+str(aid)+'/skill-replay',headers=headers)
                assert r.status_code==200 and r.json()['hash']==archive['hash'] and r.json()['tools_reexecuted'] is False
                replays+=1
            assert replays==3
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archives=await inspect(url);assert archives['revision']=='0064' and len(archives['counts'])==134 and len(archives['artifact_hashes'])==3
        assert await snapshot(url)==before and digest(ROOT/'.env')==env
        result={'pass':True,'revision':'0064','operations':operations,'binding':binding,'physical_tables':134,'read_only_replays':3,
            'business_hashes_unchanged':True,'env_unchanged':True,'real_bot_activated':False,'provider_calls':False,'production_accepted':False}
        (ROOT/'.runtime/s3-live.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
