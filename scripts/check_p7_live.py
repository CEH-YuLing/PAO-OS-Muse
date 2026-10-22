"""Read-only installed local contract/flags/schema/archive gate, reviewed through S1.1."""
import asyncio,json
from uuid import uuid4
from pathlib import Path
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
import httpx
from pao.config import ROOT,settings
from pao.models import Member,User
from pao.auth import issue_token
from pao.db import Session,engine
from pao.skills import execution_binding
from check_m2_restore import inspect

async def main():
    c=settings();assert ROOT.resolve()==Path('F:/PAO-ACOS') and c.database_url.endswith('/pao_acos_local')
    flags=('channels_enabled','channel_autoreply_enabled','voice_turns_enabled','voice_enabled','telegram_enabled','meta_enabled','meta_write_enabled',
        'goal_runner_enabled','goal_admission_enabled','goal_iterations_enabled','studio_schedule_manager_enabled','studio_schedule_dispatch_enabled',
        'workflow_worker_enabled','workflow_durable_enabled','workflow_dispatch_enabled','business_events_enabled','business_event_delivery_enabled','unified_approvals_enabled')
    assert not any(getattr(c,n) for n in flags)
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0048'
            counts={n:await db.scalar(text('SELECT count(*) FROM '+n)) for n in ('channel_bindings','channel_inbounds','channel_outbox','channel_audits','voice_turns')}
            assert not any(counts.values())
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)}
            context_path=f'/v1/workspaces/{owner.workspace_id}/context'
            r=await client.get(context_path,headers=headers)
            assert r.status_code==200 and r.json()['id']==owner.workspace_id and r.json()['role']=='owner'
            assert r.headers.get('cache-control')=='no-store'
            assert (await client.get(context_path)).status_code==401
            assert (await client.get(f'/v1/workspaces/{uuid4()}/context',headers=headers)).status_code==404
            for path in ('/health','/ready'):
                r=await client.get(path);assert r.status_code==200
            r=await client.get('/v1/channels/status',headers=headers,params={'workspace_id':owner.workspace_id});assert r.status_code==200 and r.json()['enabled'] is False
            r=await client.get('/v1/channels/bindings',headers=headers,params={'workspace_id':owner.workspace_id});assert r.status_code==200 and r.json()==[]
            r=await client.get('/v1/voice/status',headers=headers);assert r.status_code==200 and r.json()['enabled'] is False and r.json()['turns_enabled'] is False
            assert r.json()['stt_ready'] is True and r.json()['tts_ready'] is True
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            r=await client.get('/openapi.json');assert r.json()==saved
            # S1.1 adds one read-only membership context endpoint; schema stays0048.
            ops=sum(m in ('get','post','put','patch','delete','head','options') for v in saved['paths'].values() for m in v);assert ops==309
            r=await client.get('/v1/skills',headers=headers,params={'workspace_id':owner.workspace_id});assert r.status_code==200
            skills=r.json();assert skills and all(s['execution_binding']==execution_binding() for s in skills)
        async with httpx.AsyncClient(timeout=30) as web:
            assert (await web.get('http://127.0.0.1:3200/channels')).status_code==200
        archives=await inspect(make_url(c.database_url));assert len(archives['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0048','new_tables':counts,'live_contract_operations':ops,'source_binding':execution_binding(),'m2_archive_replay':'3/3',
            'voice_engine_files_ready':True,'flags_off':list(flags),'external_send':False,'real_microphone_accepted':False,'live_channel_accepted':False,'production_accepted':False,'read_only':True}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
