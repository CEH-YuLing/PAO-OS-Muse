"""Read-only P5 local rollout snapshot; no connection creation/provider request."""
import asyncio,json
from pathlib import Path
import httpx
from sqlalchemy import select,text
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import Member,User,ConnectorConnection
from pao.auth import issue_token
async def main():
    config=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and config.database_url.endswith('/pao_acos_local')
    assert config.connectors_enabled and config.studio_enabled
    assert not any(getattr(config,key) for key in ('meta_enabled','meta_write_enabled','google_ads_enabled','telegram_enabled','temporal_enabled','ads_autopilot_global_enabled'))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0034'
            assert not list(await db.scalars(select(ConnectorConnection.id)))
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)}
            catalog=await client.get('/v1/connectors/templates',params={'workspace_id':owner.workspace_id},headers=headers)
            assert catalog.status_code==200 and catalog.json()['available'] and catalog.json()['external_smoke']=='not_verified'
            assert not catalog.json()['templates'][0]['connected']
            rows=await client.get('/v1/connectors/connections',params={'workspace_id':owner.workspace_id},headers=headers)
            assert rows.status_code==200 and rows.json()==[]
            print(json.dumps({'pass':True,'revision':'0034','connector_adapter':True,'actual_connections':0,'external_smoke':'not_verified',
                'credential_key_configured':bool(config.integration_encryption_key),'provider_calls':0,'business_writes':False}))
    finally:await engine.dispose()
if __name__=='__main__':asyncio.run(main())
