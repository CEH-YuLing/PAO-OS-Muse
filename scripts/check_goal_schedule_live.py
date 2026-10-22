"""Authenticated read-only installed-but-disabled Goal schedule gate."""
import asyncio,json
from pathlib import Path
from sqlalchemy import select,text
import httpx
from pao.config import ROOT,settings
from pao.models import Member,User
from pao.auth import issue_token
from pao.db import Session,engine
from pao.skills import execution_binding

async def main():
    c=settings();assert ROOT.resolve()==Path('F:/PAO-ACOS') and c.database_url.endswith('/pao_acos_local')
    assert not any((c.studio_schedule_manager_enabled,c.studio_schedule_dispatch_enabled,c.goal_runner_enabled,
        c.goal_admission_enabled,c.goal_iterations_enabled,c.workflow_durable_enabled,c.workflow_dispatch_enabled,
        c.workflow_worker_enabled,c.temporal_enabled,c.meta_enabled,c.meta_write_enabled,c.telegram_enabled,
        c.meta_autopilot_enabled,c.ads_autopilot_global_enabled,c.business_event_delivery_enabled))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=15) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0043'
            tables=('studio_schedules','studio_schedule_events','studio_schedule_slots','goal_schedule_slots',
                'goal_executions','goal_commands','goal_events','studio_executions','studio_commands')
            counts={t:await db.scalar(text('SELECT count(*) FROM '+t)) for t in tables};assert not any(counts.values())
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)};params={'workspace_id':owner.workspace_id}
            async def get(path,scoped=True):
                r=await client.get(path,params=params if scoped else None,headers=headers);r.raise_for_status();return r.json()
            status=await get('/v1/schedules/goals/status')
            assert status=={'manager_enabled':False,'dispatch_enabled':False,'owner':'runtime.dispatch_studio_schedules.v1',
                'kind':'bounded_goal','runner_profile':'p63-runner-v1','dry_run_only':True,'model_calls':False,
                'iteration_approval_required':True,'step_approval_required':True}
            assert await get('/v1/schedules/goals')==[] and await get('/v1/schedules/workflows')==[]
            owners=(await get('/v1/schedules/owners'))['owners']
            assert owners['bounded_goal']==owners['studio_workflow']==status['owner']
            assert owners['ads_report']=='business.report_scheduler' and owners['ads_sync']=='business.warehouse_scheduler'
            assert owners['automation_follow_up']=='automation.PaoAutomationWorkflow'
            assert await get('/openapi.json',False)==json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            skills=await get('/v1/skills');assert skills and all(row['execution_binding']==execution_binding() for row in skills)
            print(json.dumps({'pass':True,'revision':'0043','counts':counts,'status':status,'read_only':True,
                'live_contract_equal':True,'live_binding':execution_binding(),'external_flags_off':True}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
