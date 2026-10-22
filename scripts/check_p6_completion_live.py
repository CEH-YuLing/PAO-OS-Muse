"""Read-only installed P6.1–P6.7 local gate, never enables external execution."""
import asyncio,json
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
    flags=('studio_schedule_manager_enabled','studio_schedule_dispatch_enabled','goal_runner_enabled','goal_admission_enabled',
        'goal_iterations_enabled','workflow_worker_enabled','workflow_durable_enabled','workflow_dispatch_enabled','temporal_enabled',
        'meta_enabled','meta_write_enabled','telegram_enabled','meta_autopilot_enabled','ads_autopilot_global_enabled',
        'business_events_enabled','business_event_delivery_enabled','unified_approvals_enabled','result_inbox_enabled',
        'learning_review_enabled','outcome_observations_enabled')
    assert not any(getattr(c,n) for n in flags)
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0046'
            names=('studio_schedules','studio_schedule_events','studio_schedule_slots','goal_schedule_slots','goal_executions',
                'goal_commands','goal_events','studio_executions','studio_commands','goal_result_receipts','goal_result_deliveries',
                'artifact_learning_proposals','artifact_learning_audits','outcome_observations')
            counts={n:await db.scalar(text('SELECT count(*) FROM '+n)) for n in names};assert not any(counts.values())
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)};params={'workspace_id':owner.workspace_id}
            async def get(path,scoped=True):
                r=await client.get(path,headers=headers,params=params if scoped else None);r.raise_for_status();return r.json()
            for path in ('/v1/results/status','/v1/ads/outcome-observations/status'):
                assert (await get(path))['enabled'] is False
            r=await client.get('/v1/learning/brains/00000000-0000-0000-0000-000000000000/proposals',headers=headers)
            assert r.status_code==409 and r.json()['detail']=='learning_review_disabled'
            status=await get('/v1/schedules/goals/status')
            assert status['manager_enabled'] is False and status['dispatch_enabled'] is False and status['dry_run_only'] is True
            assert await get('/v1/schedules/goals')==[] and await get('/v1/schedules/workflows')==[]
            owners=(await get('/v1/schedules/owners'))['owners']
            assert owners['bounded_goal']==owners['studio_workflow']=='runtime.dispatch_studio_schedules.v1'
            assert await get('/openapi.json',False)==json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            skills=await get('/v1/skills');assert skills and all(s['execution_binding']==execution_binding() for s in skills)
        archives=await inspect(make_url(c.database_url));assert len(archives['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0046','counts':counts,'live_contract_equal':True,'live_binding':execution_binding(),
            'm2_archive_replay':'3/3','feature_flags_off':list(flags),'read_only':True,'real_meta_accepted':False,'production_accepted':False}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
