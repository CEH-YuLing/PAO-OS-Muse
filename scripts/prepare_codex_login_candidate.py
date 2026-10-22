"""Private source+DB checkpoint and separate Codex UI-login candidate. No rollout."""
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from backup_acos_checkpoint import source_archive
from check_p84_foundation import binding, primary_schema, health
from pao.modules.operations.checkpoint import digest

def main():
    assert ROOT==Path('F:/PAO-ACOS')
    candidate=ROOT/'.runtime/codex-login-candidate-20261019'
    assert not candidate.exists(),'Preserve existing candidate'
    folder=ROOT/'.runtime'/('codex-login-checkpoint-'+uuid4().hex)
    folder.mkdir()
    state={'binding':binding(),'schema':asyncio.run(primary_schema()),'health':health(),
           'env_sha256':digest(ROOT/'.env'),'candidate':str(candidate),'primary_migrated':False}
    assert state['schema']['revision']=='0072' and all(x==200 for x in state['health'].values())
    state['source_manifest']=source_archive(ROOT,folder/'source.zip')
    with (folder/'primary.dump').open('xb') as output:
        result=subprocess.run(['docker','exec','pao-acos-local-postgres-1','pg_dump','-U','pao','-d','pao_acos_local','-Fc'],stdout=output,stderr=subprocess.PIPE,timeout=90)
    assert result.returncode==0 and (folder/'primary.dump').stat().st_size>1024
    state['database_sha256']=digest(folder/'primary.dump')
    candidate.mkdir()
    with ZipFile(folder/'source.zip') as archive:
        for name in state['source_manifest']:
            target=candidate/name
            assert target.resolve().is_relative_to(candidate) and not target.exists()
            target.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(name) as incoming,target.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
    assert binding()==state['binding'] and digest(ROOT/'.env')==state['env_sha256']
    (folder/'checkpoint.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
    print(json.dumps({'checkpoint':str(folder),'candidate':str(candidate),'schema':'0072','primary_modified':False}))

if __name__=='__main__':main()
