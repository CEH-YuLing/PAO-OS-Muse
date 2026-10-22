"""Read-only live contract/binding and old M2 archive replay; no new jobs."""
import asyncio,json
from pathlib import Path
import httpx
from sqlalchemy import select,text
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Run,ChatSession,TaskAttempt,Member,User,Brain
from pao.skills import execution_binding

async def main():
    if ROOT.resolve()!=Path('F:/PAO-ACOS') or not settings().database_url.endswith('/pao_acos_local'):
        raise SystemExit('ACOS local only')
    replays=0
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10) as client:
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            live=await client.get('/openapi.json'); assert live.status_code==200 and live.json()==saved
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1))
            assert member
            headers={'Authorization':'Bearer '+issue_token(member.user_id)}
            skills=await client.get('/v1/skills',params={'workspace_id':member.workspace_id},headers=headers)
            assert skills.status_code==200
            assert all(row['execution_binding']==execution_binding() for row in skills.json())
            for run,chat in await db.execute(select(Run,ChatSession).join(ChatSession,ChatSession.id==Run.session_id).where(Run.status=='completed')):
                archive=(run.execution_plan or {}).get('skill_artifact')
                if archive:
                    response=await client.get(f'/v1/runs/{run.id}/skill-replay',headers={'Authorization':'Bearer '+issue_token(chat.user_id)})
                    assert response.status_code==200 and response.json()['hash']==archive['hash']
                    replays+=1
            for attempt in await db.scalars(select(TaskAttempt).where(TaskAttempt.skill_artifact.is_not(None))):
                owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.workspace_id==attempt.workspace_id,Member.role=='owner',User.active.is_(True)).limit(1))
                assert owner
                response=await client.get(f'/v1/tasks/{attempt.task_id}/attempts/{attempt.id}/skill-replay',headers={'Authorization':'Bearer '+issue_token(owner.user_id)})
                assert response.status_code==200 and response.json()['hash']==attempt.skill_artifact['hash']
                replays+=1
            revision=await db.scalar(text('SELECT version_num FROM alembic_version'))
            assert replays>=3,'Missing original M2 archives'
            if settings().knowledge_sources_enabled:
                brain=await db.scalar(select(Brain).where(Brain.owner_id==member.user_id,Brain.workspace_id==member.workspace_id,Brain.archived_at.is_(None)).limit(1))
                assert brain
                status=await client.get(f'/v1/brains/{brain.id}/sources/status',headers=headers)
                assert status.status_code==200 and status.json()['enabled'] is True and status.json()['rag_enabled']==settings().knowledge_enabled
                sources=await client.get(f'/v1/brains/{brain.id}/sources',headers=headers)
                assert sources.status_code==200
                if settings().knowledge_enabled:
                    knowledge=await client.get(f'/v1/brains/{brain.id}/knowledge/status',headers=headers)
                    assert knowledge.status_code==200 and knowledge.json()['enabled'] is True
                    assert knowledge.json()['rag_mode']=='grounded_excerpts' and knowledge.json()['cloud_sources_sent'] is False
            print(json.dumps({'pass':True,'full_live_contract':True,'binding':execution_binding(),
                'archive_replays':replays,'revision':revision,'brain_enabled':settings().brain_manager_enabled,
                'sources_enabled':settings().knowledge_sources_enabled,'knowledge_enabled':settings().knowledge_enabled}))
    finally:
        await engine.dispose()
if __name__=='__main__':asyncio.run(main())
