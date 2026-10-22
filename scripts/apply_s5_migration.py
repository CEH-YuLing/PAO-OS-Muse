"""Release schema0070 only after final S5 gates and an exact restored checkpoint.

Does not enable the feature, alter credentials, restart services or call providers.
"""
import asyncio,json,subprocess,sys
from pathlib import Path
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest,verify
from check_p11_migration import snapshot
from check_m2_restore import inspect


async def main(path):
    url=make_url(settings().database_url);cfg=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert not any(getattr(cfg,key) for key in ('meta_enabled','google_ads_enabled','meta_write_enabled',
        'ads_autopilot_global_enabled','meta_autopilot_enabled','telegram_enabled','telegram_scoped_runtime_enabled',
        'meta_installation_config_enabled','business_planning_enabled'))
    assert digest(ROOT/'.env')=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7'
    backend=json.loads((ROOT/'.runtime/s5-backend.json').read_text(encoding='utf-8'))
    assert backend['pass'] and backend['binding_unchanged'] and backend['binding']==execution_binding()
    assert backend['tests']>=2217 and backend['failures']==backend['errors']==backend['skipped']==0
    browser=json.loads((ROOT/'.runtime/s5-browser.json').read_text(encoding='utf-8'))
    assert all(browser[key] for key in ('pass','real_api_db','tenant_role_isolation','mobile','populated_restore','restored_review_immutable','restored_routing_immutable'))
    assert json.loads((ROOT/'.runtime/s5-migration.json').read_text(encoding='utf-8'))['pass']
    quality=json.loads((ROOT/'.runtime/s5-local-quality.json').read_text(encoding='utf-8'))
    assert quality['pass'] and quality['real_local_inference'] and quality['reported_usage']
    manifest=Path(path).resolve(strict=True);assert manifest.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    saved=json.loads(manifest.read_text(encoding='utf-8'))
    assert saved['binding']==execution_binding() and saved['database']['revision_before']=='0065'
    archive=Path(saved['source']['path']).resolve(strict=True);dump=Path(saved['database']['backup']).resolve(strict=True)
    assert archive.is_relative_to(manifest.parent) and dump.is_relative_to((ROOT/'.runtime').resolve())
    assert digest(archive)==saved['source']['sha256'] and digest(dump)==saved['database']['sha256']
    verify(archive,saved['source']['files'])
    for migration in (ROOT/'apps/api/migrations/versions').glob('00[67]*.py'):
        key=migration.relative_to(ROOT).as_posix()
        assert digest(migration)==saved['source']['files'][key]
    subprocess.run([sys.executable,'scripts/check_acos_idle.py','--safe-repair'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/check_s03_restore.py',str(manifest)],cwd=ROOT,check=True)
    before=await snapshot(url);old=await inspect(url);assert old['revision']=='0065'
    env=digest(ROOT/'.env')
    subprocess.run([sys.executable,'-m','alembic','upgrade','0070'],cwd=ROOT,check=True)
    assert (await snapshot(url,before[0]))[1]==before[1]
    after=await inspect(url)
    assert after['revision']=='0070' and after['artifact_hashes']==old['artifact_hashes']
    assert all(after['counts'][key]==value for key,value in old['counts'].items())
    added=set(after['counts'])-set(old['counts'])
    assert len(added)==13 and all(key.startswith(('business_','monthly_plan')) and after['counts'][key]==0 for key in added)
    assert digest(ROOT/'.env')==env
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,check=True)
    result={'pass':True,'revision':'0070','physical_tables':len(after['counts']),
        'old_columns_exact':True,'new_tables_empty':True,'archives_unchanged':True,
        'env_unchanged':True,'provider_calls':False,'pre_checkpoint':str(manifest),'binding':execution_binding()}
    (ROOT/'.runtime/s5-schema-rollout.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':assert len(sys.argv)==2;asyncio.run(main(sys.argv[1]))
