"""Read-only P6.4 gate; no admission, provider calls or business jobs."""
import asyncio,json
from pathlib import Path
from sqlalchemy import select,text
import httpx
from pao.config import ROOT,settings
from pao.models import Member,User
from pao.auth import issue_token
from pao.db import Session,engine
from pao.skills import execution_binding
from check_m2_restore import inspect
from sqlalchemy.engine import make_url

async def main():
    c=settings();assert ROOT.resolve()==Path('F:/PAO-ACOS') and c.database_url.endswith('/pao_acos_local')
    assert not any((c.studio_schedule_manager_enabled,c.studio_schedule_dispatch_enabled,c.goal_runner_enabled,
        c.goal_admission_enabled,c.goal_iterations_enabled,c.workflow_worker_enabled,c.workflow_durable_enabled,
        c.workflow_dispatch_enabled,c.temporal_enabled,c.meta_enabled,c.meta_write_enabled,c.telegram_enabled,
        c.meta_autopilot_enabled,c.ads_autopilot_global_enabled,c.business_events_enabled,
        c.business_event_delivery_enabled,c.unified_approvals_enabled))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=15) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0042'
            names=('studio_schedules','studio_schedule_events','studio_schedule_slots','studio_executions',
                'studio_commands','goal_executions','goal_commands','goal_events')
            counts={n:await db.scalar(text('SELECT count(*) FROM '+n)) for n in names};assert not any(counts.values())
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)}
            async def get(path,params=None):
                response=await client.get(path,params=params,headers=headers);response.raise_for_status();return response.json()
            params={'workspace_id':owner.workspace_id}
            status=await get('/v1/schedules/workflows/status',params)
            assert status=={'manager_enabled':False,'dispatch_enabled':False,'owner':'runtime.dispatch_studio_schedules.v1',
                'dry_run_only':True,'model_calls':False,'step_approval_required':True,
                'overlap_policy':'latest_eligible_skip_busy','recovery_horizon_days':7}
            assert await get('/v1/schedules/workflows',params)==[]
            owners=(await get('/v1/schedules/owners',params))['owners']
            assert owners=={'ads_report':'business.report_scheduler','ads_sync':'business.warehouse_scheduler',
                'automation_follow_up':'automation.PaoAutomationWorkflow','studio_workflow':status['owner'],'bounded_goal':'unassigned'}
            goal=await get('/v1/goal-runners/status',params)
            assert goal['execution_enabled'] is False and goal['model_calls'] is False
            assert await get('/openapi.json')==json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            skills=await get('/v1/skills',params);assert skills and all(s['execution_binding']==execution_binding() for s in skills)
        archives=await inspect(make_url(c.database_url));assert len(archives['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0042','read_only':True,'counts':counts,'status':status,
            'live_contract_equal':True,'live_binding':execution_binding(),'m2_archive_file_verify':'3/3',
            'bounded_goal_schedules':'not_implemented','external_flags_off':True}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
