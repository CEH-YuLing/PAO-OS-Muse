"""Read-only local planning acceptance; never create business plans or runs."""
import asyncio,json
from pathlib import Path
import httpx
from sqlalchemy import select,text
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User

async def main():
    c=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and c.database_url.endswith('/pao_acos_local')
    assert c.workflow_planning_enabled and c.studio_enabled
    assert not any((c.meta_enabled,c.meta_write_enabled,c.meta_autopilot_enabled,
                   c.ads_autopilot_global_enabled,c.business_events_enabled,
                   c.business_event_delivery_enabled,c.unified_approvals_enabled))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10) as client:
            revision=await db.scalar(text('SELECT version_num FROM alembic_version'));assert revision in ('0037','0038')
            active_runs=await db.scalar(text("SELECT count(*) FROM runs WHERE status IN ('queued','running','waiting_approval')"));assert active_runs==0
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert member
            response=await client.get('/v1/studio/planning/status',params={'workspace_id':member.workspace_id},headers={'Authorization':'Bearer '+issue_token(member.user_id)})
            response.raise_for_status();value=response.json()
            assert value['enabled'] is True and value['execution_enabled'] is False
            plans=await db.scalar(text("SELECT count(*) FROM studio_events WHERE action='p61_plan_created'"))
            print(json.dumps({'revision':revision,'planning':value,'active_runs':active_runs,
                              'saved_plans':plans,'meta_enabled':False,'m4_flags_enabled':False,'read_only_check':True}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
