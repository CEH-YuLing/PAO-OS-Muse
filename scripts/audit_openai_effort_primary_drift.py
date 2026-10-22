"""Read-only primary comparison against a restored checkpoint, not a restore.

This cannot reconstruct the exact missing test-start snapshot from the earlier
failed helper. It records checkpoint-relative drift and a fresh bounded window.
"""
import asyncio,json,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from pao.config import settings
from sqlalchemy.engine import make_url
from check_installation_ai_migration import signatures
from check_m2_restore import CONTAINER,inspect
from pao.modules.operations.checkpoint import digest


def docker(*args,**kwargs):
    return subprocess.run(['docker','exec',*args],check=True,timeout=90,**kwargs)


async def main():
    url=make_url(settings().database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    checkpoint=ROOT/'.runtime/checkpoints/p0-20261020T142659-cc78274d/manifest.json'
    manifest=json.loads(checkpoint.read_text());backup=Path(manifest['database']['backup'])
    assert backup.parent==ROOT/'.runtime' and digest(backup)==manifest['database']['sha256']
    folder=ROOT/'.runtime'/('openai-effort-drift-'+uuid4().hex);folder.mkdir()
    clone='pao_effort_drift_'+uuid4().hex;created=False
    before=await signatures(url)
    state={'primary_restore':False,'provider_calls':0,'checkpoint':str(checkpoint),'primary_rows_before':before,
        'exact_test_start_snapshot_available':False,'owned_clone_removed':False}
    try:
        docker(CONTAINER,'createdb','-U','pao',clone,capture_output=True);created=True
        with backup.open('rb') as source,(folder/'restore.log').open('wb') as log:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',clone,'--no-owner','--exit-on-error',stdin=source,stdout=log,stderr=subprocess.STDOUT)
        previous=await signatures(url.set(database=clone))
        state['checkpoint_rows']=previous
        state['changed_since_checkpoint']=[k for k in sorted(set(before)|set(previous)) if before.get(k)!=previous.get(k)]
        old_archives=(await inspect(url.set(database=clone)))['artifact_hashes']
        state['archives_unchanged']=(await inspect(url))['artifact_hashes']==old_archives
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',clone,capture_output=True);state['owned_clone_removed']=True
        after=await signatures(url);state['primary_rows_after']=after;state['fresh_window_unchanged']=before==after
        state['primary_data_restored_or_overwritten']=False
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**{k:v for k,v in state.items() if not k.endswith('_rows') and k not in ('primary_rows_before','primary_rows_after')}}))


if __name__=='__main__':asyncio.run(main())
