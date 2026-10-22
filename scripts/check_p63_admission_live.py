"""Read-only primary gate: admission installed and disabled, no goal jobs."""
import asyncio,json
from pathlib import Path
from sqlalchemy import select,text
import httpx
from pao.config import ROOT,settings
from pao.models import Member,User
from pao.auth import issue_token
from pao.db import Session,engine


async def main():
    c=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and c.database_url.endswith('/pao_acos_local')
    assert not any((c.goal_admission_enabled,c.goal_iterations_enabled,c.workflow_worker_enabled,c.workflow_durable_enabled,
        c.workflow_dispatch_enabled,c.temporal_enabled,c.meta_enabled,c.meta_write_enabled,
        c.meta_autopilot_enabled,c.ads_autopilot_global_enabled,c.business_events_enabled,
        c.business_event_delivery_enabled,c.unified_approvals_enabled))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            counts={n:await db.scalar(text('SELECT count(*) FROM '+n)) for n in ('goal_executions','goal_commands','goal_events')}
            assert not any(counts.values())
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1))
            assert owner
            response=await client.get('/v1/goal-executions/status',params={'workspace_id':owner.workspace_id},
                headers={'Authorization':'Bearer '+issue_token(owner.user_id)})
            response.raise_for_status()
            value=response.json()
            assert value=={'admission_enabled':False,'execution_enabled':False,'implementation':'admission_ledger_only','dry_run_only':True,'model_calls':False}
            print(json.dumps({'pass':True,'revision':'0041','counts':counts,'status':value,'read_only':True}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
