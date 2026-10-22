"""Read-only final M4 gate: additive schema, source binding, all live flags off."""
import asyncio,json
from pathlib import Path
import httpx
from sqlalchemy import select,text
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User

async def main():
    config=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and config.database_url.endswith('/pao_acos_local')
    flags=('business_events_enabled','business_event_delivery_enabled','unified_approvals_enabled',
           'meta_enabled','meta_write_enabled','google_ads_enabled','telegram_enabled','temporal_enabled',
           'ads_autopilot_global_enabled','meta_autopilot_enabled')
    assert not any(getattr(config,flag) for flag in flags)
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0037'
            for table in ('business_events','business_outbox','business_receipts'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1))
            assert member;headers={'Authorization':'Bearer '+issue_token(member.user_id)}
            response=await client.get('/v1/business-events/status',headers=headers)
            assert response.status_code==200 and response.json()=={
                'enabled':False,'producer_enabled':False,'delivery_enabled':False,'consumer':'internal.audit.v1'}
            for path in ('approvals','diagnostics','ledger'):
                response=await client.get('/v1/business-events/'+path,params={'workspace_id':member.workspace_id},headers=headers)
                assert response.status_code==409,path
            response=await client.get('/v1/tasks',params={'workspace_id':member.workspace_id},headers=headers)
            assert response.status_code==200
        print(json.dumps({'pass':True,'revision':'0037','all_m4_flags_off':True,'zero_live_events_receipts':True,
                          'disabled_endpoints_enforced':True,'legacy_tasks_200':True}))
    finally:await engine.dispose()
if __name__=='__main__':asyncio.run(main())
