"""Checkpoint-bound0060->0064 only, after S3 regression. No bot provisioning."""
import asyncio,json,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest,verify
from check_p11_migration import snapshot
from check_m2_restore import inspect
from check_s3_regression import validate as regression


async def main(path):
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    config=settings();assert not config.telegram_enabled and not config.telegram_scoped_runtime_enabled
    manifest=Path(path).resolve(strict=True);assert manifest.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    saved=json.loads(manifest.read_text(encoding='utf-8'))
    assert saved['binding']==execution_binding() and saved['database']['revision_before']=='0060'
    dump=Path(saved['database']['backup']).resolve(strict=True);archive=Path(saved['source']['path']).resolve(strict=True)
    assert dump.is_relative_to((ROOT/'.runtime').resolve()) and archive.is_relative_to(manifest.parent)
    assert digest(dump)==saved['database']['sha256'] and digest(archive)==saved['source']['sha256'];verify(archive,saved['source']['files'])
    for revision in ('0061','0062','0063','0064'):
        paths=list((ROOT/'apps/api/migrations/versions').glob(revision+'_*.py'));assert len(paths)==1
        relative=paths[0].relative_to(ROOT).as_posix();assert digest(paths[0])==saved['source']['files'][relative]
    assert regression()['unique_cases_verified']==2078
    proof=json.loads((ROOT/'.runtime/s3-migration.json').read_text(encoding='utf-8'));assert proof['pass'] and proof['primary_unchanged']
    env_hash=digest(ROOT/'.env');assert env_hash=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    subprocess.run([sys.executable,'scripts/check_acos_idle.py','--safe-repair'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/check_s03_restore.py',str(manifest)],cwd=ROOT,check=True)
    before=await snapshot(url);old=await inspect(url);assert old['revision']=='0060'
    subprocess.run([sys.executable,'-m','alembic','upgrade','0064'],cwd=ROOT,check=True)
    assert (await snapshot(url,before[0]))[1]==before[1]
    after=await inspect(url);assert after['revision']=='0064' and after['artifact_hashes']==old['artifact_hashes']
    assert all(after['counts'][key]==value for key,value in old['counts'].items())
    added=set(after['counts'])-set(old['counts'])
    assert added=={'telegram_runtime_profiles','telegram_runtime_audits','telegram_runtime_receipts','telegram_bot_identities','telegram_pairings'}
    assert all(after['counts'][key]==0 for key in added) and digest(ROOT/'.env')==env_hash
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,check=True)
    result={'pass':True,'revision':'0064','old_columns_exact':True,'new_tables_empty':True,'bot_provisioned':False,
        'external_calls':False,'env_unchanged':True,'pre_checkpoint':str(manifest),'binding':execution_binding()}
    (ROOT/'.runtime/s3-schema-rollout.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':assert len(sys.argv)==2;asyncio.run(main(sys.argv[1]))
