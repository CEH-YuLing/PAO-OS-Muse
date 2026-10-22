"""Release 0071 only with current full regression/browser/restore/checkpoint evidence."""
import asyncio,json,subprocess,sys
from pathlib import Path
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.skills import execution_binding,_execution_digest
from pao.modules.operations.checkpoint import digest,verify
from check_p11_migration import snapshot
from check_m2_restore import inspect

NEW={'workspace_invitations','login_sessions','lifecycle_audits','data_lifecycle_requests'}


def evidence(path):
    path=Path(path).resolve(strict=True)
    assert path.is_relative_to((ROOT/'.runtime').resolve()) and path.stat().st_size<2*1024*1024
    value=json.loads(path.read_text(encoding='utf-8'))
    assert type(value) is dict and value.get('pass') is True
    return value


async def main(manifest_path,browser_path,migration_path):
    config=settings();url=make_url(config.database_url);binding=execution_binding()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.host=='127.0.0.1' and url.port==15432 and url.database=='pao_acos_local' and url.username=='pao'
    assert not any(getattr(config,key) for key in ('meta_enabled','google_ads_enabled','meta_write_enabled',
        'ads_autopilot_global_enabled','meta_autopilot_enabled','telegram_enabled','telegram_scoped_runtime_enabled',
        'meta_installation_config_enabled','channel_retention_enabled'))
    backend=evidence(ROOT/'.runtime/s62-backend.json')
    assert backend['binding']==binding and backend['binding_unchanged'] is True and backend['tests']>=2251
    assert all(type(backend[key]) is int and backend[key]==0 for key in ('failures','errors','skipped'))
    browser=evidence(browser_path)
    cleanup=evidence(Path(browser_path).parent/'cleanup.json')
    assert cleanup.get('database_absent') is True and cleanup.get('test_ports_free') is True
    assert all(browser.get(key) is True for key in ('real_api_db','invitation_created','invitation_accepted_in_browser',
        'two_sme_ui_isolation','export_real_download','deletion_request_confirmed_without_purge','mobile_390','member_removed','server_logout_all'))
    assert browser.get('provider_calls') is False
    assert browser.get('binding')==binding and browser.get('backend_binding_unchanged') is True
    from pao.modules.operations.checkpoint import entries
    from backup_acos_checkpoint import frontend_supplements
    import hashlib
    frontend={k:v for k,v in {**entries(ROOT),**frontend_supplements(ROOT)}.items()
              if k.startswith('apps/web/') and not k.endswith('next-env.d.ts')}
    assert browser.get('frontend_sha256')==hashlib.sha256(json.dumps(frontend,sort_keys=True).encode()).hexdigest()
    migration=evidence(migration_path)
    assert all(migration.get(key) is True for key in ('old_columns_exact','populated_restore_exact','audit_immutable_after_restore','populated_downgrade_refused','primary_unchanged','env_unchanged'))
    manifest=Path(manifest_path).resolve(strict=True)
    assert manifest.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    saved=json.loads(manifest.read_text(encoding='utf-8'))
    assert saved['binding']==binding and saved['database']['revision_before']=='0070'
    archive=Path(saved['source']['path']).resolve(strict=True);dump=Path(saved['database']['backup']).resolve(strict=True)
    assert archive.is_relative_to(manifest.parent) and dump.is_relative_to((ROOT/'.runtime').resolve())
    assert digest(archive)==saved['source']['sha256'] and digest(dump)==saved['database']['sha256']
    verify(archive,saved['source']['files'])
    path=ROOT/'apps/api/migrations/versions/0071_account_data_lifecycle.py'
    assert digest(path)==saved['source']['files'][path.relative_to(ROOT).as_posix()]
    subprocess.run([sys.executable,'scripts/check_acos_idle.py'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'scripts/check_s03_restore.py',str(manifest)],cwd=ROOT,check=True)
    before=await snapshot(url);old=await inspect(url);assert old['revision']=='0070'
    env_hash=digest(ROOT/'.env')
    subprocess.run([sys.executable,'-m','alembic','upgrade','0071'],cwd=ROOT,check=True)
    after=await inspect(url)
    assert after['revision']=='0071' and set(after['counts'])-set(old['counts'])==NEW
    assert all(after['counts'][table]==0 for table in NEW)
    assert (await snapshot(url,before[0]))[1]==before[1]
    assert after['artifact_hashes']==old['artifact_hashes']
    assert digest(ROOT/'.env')==env_hash and _execution_digest()==binding['sha256']
    subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,check=True)
    result={'pass':True,'revision':'0071','physical_tables':len(after['counts']),
        'old_columns_exact':True,'new_tables_empty':True,'archives_unchanged':True,
        'env_unchanged':True,'binding':binding,'checkpoint':str(manifest),
        'browser':str(Path(browser_path)),'migration':str(Path(migration_path)),
        'provider_calls':False,'production_accepted':False}
    (ROOT/'.runtime/s62-schema-rollout.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    assert len(sys.argv)==4
    asyncio.run(main(*sys.argv[1:]))
