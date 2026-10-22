"""Checkpoint-bound0058->0059; no credentials, mapping or namespace backfill."""
import asyncio,json,subprocess,sys
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest,verify
from check_p11_migration import snapshot
from check_m2_restore import inspect

async def main(path):
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    manifest=Path(path).resolve(strict=True);assert manifest.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    saved=json.loads(manifest.read_text(encoding='utf-8'))
    assert saved['binding']==execution_binding() and saved['database']['revision_before']=='0058'
    dump=Path(saved['database']['backup']).resolve(strict=True);archive=Path(saved['source']['path']).resolve(strict=True)
    assert dump.is_relative_to((ROOT/'.runtime').resolve()) and archive.is_relative_to(manifest.parent)
    assert digest(dump)==saved['database']['sha256'] and digest(archive)==saved['source']['sha256'];verify(archive,saved['source']['files'])
    migration='apps/api/migrations/versions/0059_telegram_connection_namespaces.py'
    assert digest(ROOT/migration)==saved['source']['files'][migration], 'Migration changed after checkpoint'
    env_hash=digest(ROOT/'.env')
    assert env_hash=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    subprocess.run([sys.executable,'scripts/check_acos_idle.py','--safe-repair'],cwd=ROOT,check=True)
    # A valid older dump is not proof the primary still matches it. Refuse if
    # local users added even completed data since the verified checkpoint.
    subprocess.run([sys.executable,'scripts/check_s03_restore.py',str(manifest)],cwd=ROOT,check=True)
    before=await snapshot(url);old=await inspect(url);assert old['revision']=='0058'
    subprocess.run([sys.executable,'-m','alembic','upgrade','0059'],cwd=ROOT,check=True)
    assert (await snapshot(url,before[0]))[1]==before[1]
    after=await inspect(url);assert after['revision']=='0059' and after['artifact_hashes']==old['artifact_hashes']
    assert all(after['counts'][key]==value for key,value in old['counts'].items())
    local=create_async_engine(url)
    try:
        async with local.connect() as db:
            assert await db.scalar(text('SELECT count(*) FROM telegram_connections'))==0
            for table in ('telegram_peers','telegram_updates','telegram_deliveries','channel_bindings','channel_inbounds','channel_outbox','channel_audits'):
                assert await db.scalar(text(f'SELECT count(*) FROM {table} WHERE connection_id IS NOT NULL'))==0
    finally:await local.dispose()
    assert digest(ROOT/'.env')==env_hash
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,check=True)
    print(json.dumps({'pass':True,'revision':'0059','old_column_hashes_exact':True,'automatic_mapping':False,
        'credential_copy':False,'external_calls':False,'env_unchanged':True,'pre_checkpoint':str(manifest)}))

if __name__=='__main__':assert len(sys.argv)==2;asyncio.run(main(sys.argv[1]))
