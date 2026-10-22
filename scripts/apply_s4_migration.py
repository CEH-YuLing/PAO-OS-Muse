"""Apply0065 only after full regression and an exact-restored checkpoint."""
import asyncio,json,subprocess,sys
from pathlib import Path
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest,verify
from check_p11_migration import snapshot
from check_m2_restore import inspect
from check_s4_regression import validate as regression


async def main(path):
    url=make_url(settings().database_url);config=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert not any((config.meta_enabled,config.google_ads_enabled,config.meta_write_enabled,config.ads_autopilot_global_enabled,config.telegram_enabled,config.telegram_scoped_runtime_enabled))
    assert digest(ROOT/'.env')=='5672f74189bcef6c110d4c434e956d4f324598ee3901b88bbd56902c945fbea7','Local configuration changed since S4 baseline'
    gate=regression()
    assert gate['pass'] and gate['backend_unchanged'] and gate['binding']==execution_binding() and gate['unique_cases_verified']==2099
    assert config.meta_installation_config_enabled is False
    assert json.loads((ROOT/'.runtime/s4-migration.json').read_text(encoding='utf-8'))['pass']
    browser=json.loads((ROOT/'.runtime/s4-browser.json').read_text(encoding='utf-8'))
    assert all(browser[key] for key in ('pass','real_api_db','synthetic_oauth','google_oauth','google_platform_gate','managed_byo','rotation','unknown_ack','secret_wipe','tenant_role_isolation','mobile'))
    locks=json.loads((ROOT/'.runtime/s4-locks.json').read_text(encoding='utf-8'))
    assert locks['pass'] and locks['binding']==execution_binding() and locks['fresh_process']['pass'] and locks['primary_unchanged']
    manifest=Path(path).resolve(strict=True);assert manifest.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    saved=json.loads(manifest.read_text(encoding='utf-8'));assert saved['binding']==execution_binding() and saved['database']['revision_before']=='0064'
    archive=Path(saved['source']['path']).resolve(strict=True);dump=Path(saved['database']['backup']).resolve(strict=True)
    assert archive.is_relative_to(manifest.parent) and dump.is_relative_to((ROOT/'.runtime').resolve())
    assert digest(archive)==saved['source']['sha256'] and digest(dump)==saved['database']['sha256'];verify(archive,saved['source']['files'])
    migration='apps/api/migrations/versions/0065_ads_tenant_apps.py';assert digest(ROOT/migration)==saved['source']['files'][migration]
    subprocess.run([sys.executable,'scripts/check_acos_idle.py','--safe-repair'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/check_s03_restore.py',str(manifest)],cwd=ROOT,check=True)
    before=await snapshot(url);old=await inspect(url);assert old['revision']=='0064'
    env=digest(ROOT/'.env')
    subprocess.run([sys.executable,'-m','alembic','upgrade','0065'],cwd=ROOT,check=True)
    assert (await snapshot(url,before[0]))[1]==before[1]
    after=await inspect(url);assert after['revision']=='0065' and after['artifact_hashes']==old['artifact_hashes']
    assert all(after['counts'][key]==value for key,value in old['counts'].items())
    added=set(after['counts'])-set(old['counts']);assert added=={'ads_app_configs','ads_app_audits'} and all(after['counts'][key]==0 for key in added)
    assert digest(ROOT/'.env')==env
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,check=True)
    result={'pass':True,'revision':'0065','physical_tables':136,'old_columns_exact':True,'new_tables_empty':True,
        'archives_unchanged':True,'env_unchanged':True,'provider_calls':False,'pre_checkpoint':str(manifest),'binding':execution_binding()}
    (ROOT/'.runtime/s4-schema-rollout.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':assert len(sys.argv)==2;asyncio.run(main(sys.argv[1]))
