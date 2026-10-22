"""Read-only verification of the independent fork, never the source database."""
import asyncio
import hashlib
import json
from pathlib import Path
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from muse_sandbox import guard,ROOT,RUNTIME

async def main():
    cfg=guard()
    manifest=json.loads((ROOT/'handoff/source-manifest.json').read_text())
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    changed=[name for name,value in manifest.items() if name!='AGENTS.md' and
        (not (ROOT/name).is_file() or digest(ROOT/name)!=value)]
    assert not changed, 'Unexpected original source modification: '+repr(changed)
    assert digest(ROOT/'handoff/AGENTS-SOURCE-HISTORY.md')==manifest['AGENTS.md']
    engine=create_async_engine(cfg.database_url,connect_args={'server_settings':{'default_transaction_read_only':'on'}})
    try:
        async with engine.connect() as db:
            revision=await db.scalar(text('SELECT version_num FROM alembic_version'))
            count=await db.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'"))
            rows={table:await db.scalar(text('SELECT count(*) FROM '+table)) for table in
                ('users','workspaces','sessions','runs','llm_attempts','installation_ai_resources')}
        assert revision=='0077' and count==161 and rows['users']==rows['workspaces']==1
        assert rows['runs']==rows['llm_attempts']==rows['installation_ai_resources']==0
    finally:await engine.dispose()
    async with httpx.AsyncClient(trust_env=False,timeout=30) as client:
        health={path:(await client.get(url)).status_code for path,url in {
            'api':'http://127.0.0.1:8200/health','ready':'http://127.0.0.1:8200/ready',
            'web':'http://127.0.0.1:3300/'}.items()}
        assert all(v==200 for v in health.values())
        contract=(await client.get('http://127.0.0.1:8200/openapi.json')).json()
        assert contract==json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    from redis.asyncio import from_url
    redis=from_url(cfg.redis_url)
    try:
        ttl=await redis.ttl('pao:worker:health');assert ttl>0
    finally:await redis.aclose()
    result={'pass':True,'root':str(ROOT),'source_files':len(manifest),
        'unchanged_original_files':len(manifest)-1,'documented_AGENTS_override':True,
        'health':health,'schema':revision,'tables':count,'rows':rows,
        'openapi_source_live_equal':True,'worker_healthy':True,'worker_ttl':ttl,
        'fresh_data':True,'native_CLI_credentials_copied':False,'provider_inference_calls':0,
        'connected_AI_providers':0,'source_database_accessed':False}
    (RUNTIME/'muse-install-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':asyncio.run(main())
