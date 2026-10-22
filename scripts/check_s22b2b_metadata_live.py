"""Installed metadata contract/redaction only, never catalogue/inference calls."""
import asyncio,json,hashlib
from pathlib import Path
import httpx
from sqlalchemy import select,text,func
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User,ModelProviderConnection
from pao.skills import execution_binding
from check_s22b2a_live import main as native_live


async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    assert hashlib.sha256((ROOT/'.env').read_bytes()).hexdigest()=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    await native_live()
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            count_before=await db.scalar(select(func.count()).select_from(ModelProviderConnection))
            rows=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(
                Member.role.in_(('owner','admin')),User.active.is_(True))))
            for member in rows:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)}
                listing=await client.get('/v1/model-providers',params={'workspace_id':member.workspace_id},headers=headers)
                assert listing.status_code==200 and listing.headers['cache-control']=='no-store'
                assert len(listing.json())==4 and 'api_key_ciphertext' not in listing.text
                marker='fixture-invalid-input-not-a-real-secret'
                bad=await client.post('/v1/model-providers/openai/connect',headers=headers,json={'unexpected':marker})
                assert bad.status_code==422 and marker not in bad.text and bad.headers['cache-control']=='no-store'
                large=await client.post('/v1/model-providers/openai/connect',headers=headers,json={'unexpected':marker+'x'*9000})
                assert large.status_code==413 and marker not in large.text and large.headers['cache-control']=='no-store'
            assert (await client.get('/v1/model-providers',params={'workspace_id':rows[0].workspace_id})).status_code==401
            assert await db.scalar(select(func.count()).select_from(ModelProviderConnection))==count_before
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0055'
        print(json.dumps({'pass':True,'checkpoint':'S2.2B2b partial model metadata hardening',
            'binding':execution_binding(),'revision':'0055','operations':332,'native_connections_unchanged':True,
            'external_calls':False,'metadata_quota_accepted':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
