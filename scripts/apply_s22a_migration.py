"""Checkpoint-bound local rollout only; never mutate tenant history to downgrade."""
import asyncio,json,subprocess,sys
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import make_url
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
    assert saved['binding']==execution_binding() and saved['database']['revision_before']=='0052'
    dump=Path(saved['database']['backup']).resolve(strict=True);archive=Path(saved['source']['path']).resolve(strict=True)
    assert dump.is_relative_to((ROOT/'.runtime').resolve()) and archive.is_relative_to(manifest.parent)
    assert digest(dump)==saved['database']['sha256'] and digest(archive)==saved['source']['sha256'];verify(archive,saved['source']['files'])
    subprocess.run([sys.executable,'scripts/check_acos_idle.py'],cwd=ROOT,check=True)
    before=await snapshot(url);old=await inspect(url);assert old['revision']=='0052'
    subprocess.run([sys.executable,'-m','alembic','upgrade','0053'],cwd=ROOT,check=True)
    assert (await snapshot(url,before[0]))[1]==before[1]
    after=await inspect(url);assert after['revision']=='0053' and after['artifact_hashes']==old['artifact_hashes'] and after['counts']==old['counts']
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT count(*) FROM tenant_connection_references WHERE generation<>1 OR supersedes_id IS NOT NULL'))==0
    finally:await engine.dispose()
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,check=True)
    print(json.dumps({'pass':True,'revision':'0053','legacy_column_hashes_exact':True,'auto_generations':False,
                     'external_calls':False,'pre_checkpoint':str(manifest)}))


if __name__=='__main__':assert len(sys.argv)==2;asyncio.run(main(sys.argv[1]))
