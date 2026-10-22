"""Installed S6.2 read-only check; no invites/login/data-request mutations."""
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
    url=make_url(settings().database_url);cfg=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert cfg.business_planning_enabled
    assert not cfg.channel_retention_enabled
    assert not any(getattr(cfg,k) for k in ('meta_enabled','google_ads_enabled','meta_write_enabled',
        'meta_autopilot_enabled','ads_autopilot_global_enabled','telegram_enabled','telegram_scoped_runtime_enabled','meta_installation_config_enabled'))
    before=await snapshot(url);env=digest(ROOT/'.env');binding=execution_binding()
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=30) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0071'
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            operations=sum(k in ('get','post','put','patch','delete','head','options') for methods in saved['paths'].values() for k in methods)
            assert operations==406
            # A newly created SME has no historical archives. Select the active
            # owner with replay evidence deterministically, not an arbitrary
            # first membership; still require all three archives below.
            replay_count=text("((SELECT count(*) FROM runs r JOIN sessions s ON s.id=r.session_id AND s.workspace_id=r.workspace_id WHERE r.workspace_id=workspace_members.workspace_id AND s.user_id=workspace_members.user_id AND r.status='completed' AND r.execution_plan->'skill_artifact' IS NOT NULL) + (SELECT count(*) FROM task_attempts a JOIN tasks t ON t.id=a.task_id WHERE a.workspace_id=workspace_members.workspace_id AND a.skill_artifact IS NOT NULL)) DESC")
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).order_by(replay_count,Member.workspace_id,Member.user_id))
            assert member
            user=await db.get(User,member.user_id)
            headers={'Authorization':'Bearer '+issue_token(member.user_id,user.auth_version)}
            lifecycle='/v1/workspaces/'+member.workspace_id+'/lifecycle'
            for suffix in ('/members','/invitations','/data/requests'):
                response=await client.get(lifecycle+suffix,headers=headers)
                assert response.status_code==200 and response.headers.get('cache-control')=='no-store'
                assert (await client.get(lifecycle+suffix)).status_code==401
            response=await client.get('/v1/auth/sessions',headers=headers)
            assert response.status_code==200 and 'token_hash' not in response.text
            base='/v1/workspaces/'+member.workspace_id+'/business-planning'
            for suffix in ('/status','/profile','/routing'):
                response=await client.get(base+suffix,headers=headers)
                assert response.status_code==200 and response.headers.get('cache-control')=='no-store', (suffix,response.status_code,response.headers.get('cache-control'))
                assert (await client.get(base+suffix)).status_code==401
                if suffix=='/status':
                    state=response.json()
                    assert state['available'] and state['can_manage'] and state['execution_enabled'] and not state['external_actions_enabled']
            profile=(await client.get(base+'/profile',headers=headers)).json()['item']
            # Listing plans requires an existing scoped profile_id, not a month.
            # Do not invent primary business data just to satisfy a smoke test.
            response=await client.get(base+'/plans',params={'profile_id':profile['id']} if profile else {},headers=headers)
            assert response.status_code==(200 if profile else 422)
            assert response.headers.get('cache-control')=='no-store'
            assert (await client.get(base+'/plans')).status_code==401
            skills=(await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})).json()
            assert all(row['execution_binding']==binding for row in skills)
            replays=0
            for rid,plan in await db.execute(text("SELECT r.id,r.execution_plan FROM runs r JOIN sessions s ON s.id=r.session_id AND s.workspace_id=r.workspace_id WHERE r.workspace_id=:wid AND s.user_id=:uid AND r.status='completed'"),{'wid':member.workspace_id,'uid':member.user_id}):
                if not (plan or {}).get('skill_artifact'):continue
                response=await client.get('/v1/runs/'+str(rid)+'/skill-replay',headers=headers)
                assert response.status_code==200 and response.json()['hash']==plan['skill_artifact']['hash'] and response.json()['tools_reexecuted'] is False
                replays+=1
            for aid,tid,archive in await db.execute(text('SELECT a.id,a.task_id,a.skill_artifact FROM task_attempts a JOIN tasks t ON t.id=a.task_id WHERE a.workspace_id=:wid AND a.skill_artifact IS NOT NULL'),{'wid':member.workspace_id}):
                response=await client.get('/v1/tasks/'+str(tid)+'/attempts/'+str(aid)+'/skill-replay',headers=headers)
                assert response.status_code==200 and response.json()['hash']==archive['hash'] and response.json()['tools_reexecuted'] is False
                replays+=1
            assert replays==3
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        async with httpx.AsyncClient(timeout=30) as client:
            assert (await client.get('http://127.0.0.1:3200/business-planning')).status_code==200
        archives=await inspect(url)
        assert archives['revision']=='0071' and len(archives['counts'])==153 and len(archives['artifact_hashes'])==3
        assert await snapshot(url)==before and digest(ROOT/'.env')==env
        result={'pass':True,'revision':'0071','operations':operations,'binding':binding,'physical_tables':153,
            'read_only_replays':replays,'business_hashes_unchanged':True,'env_unchanged':True,'empty_profile':profile is None,
            'provider_calls':False,'real_oauth_accepted':False,'production_accepted':False}
        (ROOT/'.runtime/organization-live.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
