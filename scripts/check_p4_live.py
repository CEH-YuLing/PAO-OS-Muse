"""Bootstrap immutable seed mirrors on approved local workspace, then verify."""
import asyncio,json
from pathlib import Path
import httpx
from sqlalchemy import select,text
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User

async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    assert settings().studio_enabled and settings().engine_contract_enabled and settings().chat_features_enabled
    assert not any(getattr(settings(),key) for key in ('meta_enabled','meta_write_enabled','google_ads_enabled','telegram_enabled','temporal_enabled','ads_autopilot_global_enabled'))
    async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=20) as client:
        owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1))
        assert owner
        headers={'Authorization':'Bearer '+issue_token(owner.user_id)}
        body={'workspace_id':owner.workspace_id}
        first=await client.post('/v1/studio/bootstrap',json=body,headers=headers)
        assert first.status_code==200
        second=await client.post('/v1/studio/bootstrap',json=body,headers=headers)
        assert second.status_code==200 and second.json()['imported']==0
        catalog=await client.get('/v1/studio/definitions',params=body,headers=headers)
        assert catalog.status_code==200 and catalog.json()['workflow_execution_enabled'] is False
        seeds=[row for row in catalog.json()['definitions'] if row['seed']]
        assert len(seeds)==8
        assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0033'
        print(json.dumps({'pass':True,'studio_enabled':True,'immutable_seeds':len(seeds),'bootstrap_idempotent':True,
            'revision':'0033','workflow_execution':False,'external_integrations':False}))
    await engine.dispose()
if __name__=='__main__':asyncio.run(main())
