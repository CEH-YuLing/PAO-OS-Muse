"""Installed metadata quota/status only; never remote discovery or inference."""
import asyncio,json
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy import select,text,func
from sqlalchemy.engine import make_url
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import Member,User,ModelProviderConnection,ConnectorConnection,TenantMetadataLease,TenantMetadataPolicy
from pao.skills import execution_binding
from pao.modules.connections.metadata_resources import DEFAULTS
from pao.modules.connections import metadata_resources
from pao.modules.operations.checkpoint import digest
from check_m2_restore import inspect
from check_p11_migration import snapshot


async def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    assert digest(ROOT/'.env')=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=25) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0058'
            # A user's open Web may legitimately admit a catalogue request.
            # Preserve that immutable history; prove this checker has no writes,
            # not that the entire installation has never been used.
            columns={model.__tablename__:[column.name for column in model.__table__.columns]
                for model in (TenantMetadataLease,TenantMetadataPolicy)}
            metadata_before=await snapshot(make_url(settings().database_url),columns)
            assert metadata_before[1]['tenant_metadata_policies']['count']==0
            sources=[await db.scalar(select(func.count()).select_from(model)) for model in (ModelProviderConnection,ConnectorConnection)]
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            operations=sum(method in ('get','post','put','patch','delete','head','options') for paths in saved['paths'].values() for method in paths)
            assert operations==334
            rows=list(await db.scalars(select(Member).join(User,User.id==Member.user_id).where(Member.role.in_(('owner','admin')),User.active.is_(True))))
            assert rows
            for member in rows:
                headers={'Authorization':'Bearer '+issue_token(member.user_id)}
                path=f'/v1/workspaces/{member.workspace_id}/resources/metadata'
                result=await client.get(path,headers=headers);assert result.status_code==200 and result.headers['cache-control']=='no-store'
                data=result.json();assert data['workspace_id']==member.workspace_id and data['metadata_policy']=={'version':0,**DEFAULTS}
                assert data['usage']==await metadata_resources.usage(db,member.workspace_id)
                assert data['grants_authorized'] is False
                assert {'local_model_catalogue','local_model_selection'}<=set(data['coverage'])
                model_status=await client.get(f'/v1/workspaces/{member.workspace_id}/resources/models',headers=headers)
                assert model_status.status_code==200 and model_status.headers['cache-control']=='no-store'
                model_data=model_status.json()
                assert 'unaccounted_legacy_denied' in model_data['coverage']
                assert 'memory_embeddings' in model_data['coverage']
                assert 'knowledge_embeddings' in model_data['coverage']
                assert model_data['pending_coverage']==[]
                assert (await client.get(path)).status_code==401
                assert (await client.get(f'/v1/workspaces/{uuid4()}/resources/metadata',headers=headers)).status_code==404
                marker='fixture-validation-not-a-key'
                bad=await client.put(path,headers=headers,json={'secret':marker})
                assert bad.status_code==422 and marker not in bad.text and bad.headers['cache-control']=='no-store'
                listing=await client.get('/v1/model-providers',headers=headers,params={'workspace_id':member.workspace_id})
                assert listing.status_code==200 and listing.headers['cache-control']=='no-store' and 'ciphertext' not in listing.text
                invalid=await client.post('/v1/model-providers/openai/connect',headers={**headers,'Idempotency-Key':marker},json={'workspace_id':member.workspace_id,'api_key':marker})
                assert invalid.status_code==422 and marker not in invalid.text and invalid.headers['cache-control']=='no-store'
                local_invalid=await client.get('/v1/engines',headers={**headers,'Idempotency-Key':marker},params={'workspace_id':member.workspace_id})
                assert local_invalid.status_code==422 and marker not in local_invalid.text and local_invalid.headers['cache-control']=='no-store'
                foreign=await client.get('/v1/engines',headers=headers,params={'workspace_id':str(uuid4())})
                assert foreign.status_code==404 and foreign.headers['cache-control']=='no-store'
                skills=await client.get('/v1/skills',headers=headers,params={'workspace_id':member.workspace_id})
                assert skills.status_code==200 and all(item['execution_binding']==execution_binding() for item in skills.json())
            assert sources==[await db.scalar(select(func.count()).select_from(model)) for model in (ModelProviderConnection,ConnectorConnection)]
            assert await snapshot(make_url(settings().database_url),columns)==metadata_before
            for path in ('/health','/ready'):assert (await client.get(path)).status_code==200
        async with httpx.AsyncClient(timeout=30) as web:assert (await web.get('http://127.0.0.1:3200/settings')).status_code==200
        archives=await inspect(make_url(settings().database_url));assert len(archives['artifact_hashes'])==3
        print(json.dumps({'pass':True,'revision':'0058','operations':334,'binding':execution_binding(),
            'm2_replay':'3/3','metadata_history_rows':{table:value['count'] for table,value in metadata_before[1].items()},
            'checker_metadata_hashes_unchanged':True,'native_connection_counts_unchanged':True,
            'external_calls':False,'local_discovery_calls':False,'metadata_quota_backend_accepted':True,
            'full_B2b_accepted':True,'acceptance_scope':'local_native_coverage',
            'full_S2_accepted':False,'production_accepted':False,'global_host_fairness_accepted':False}))
    finally:await engine.dispose()


if __name__=='__main__':asyncio.run(main())
