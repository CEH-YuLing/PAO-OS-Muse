"""Collect exact bounded proofs. Never marks the unfinished CLI phase complete."""
import json
from pathlib import Path
from uuid import uuid4
from gd00_baseline import ROOT,digest,write_new


def proof(relative):
    path=ROOT/'.runtime'/relative/'receipt.json'
    value=json.loads(path.read_text(encoding='utf-8'))
    assert value['pass'] is True,relative
    return path,value


def main():
    from check_p84_foundation import binding
    regression,tests=proof('gd01-tests-0686ee062d5842c7aed09abe9157a04a')
    live,actual=proof('gd01-tests-6e6e3cc32ebf4800bd8de89f61b116a4')
    frontend,web=proof('model-provider-tabs-frontend-73ea6be92d53470eb6c870662155a3e8')
    installed,current=proof('gd01-installed-a8e21b340a654b43801d0cfd16c02d50')
    assert tests['counts']=={'tests':469,'failures':0,'errors':0,'skipped':0}
    assert actual['provider_calls']==2 and actual['live_summary']['native_chat_and_studio']
    assert current['schema']['revision']=='0075' and current['schema']['physical_tables']==161
    assert current['replays']==3 and current['primary_rows_unchanged'] and current['source_env_pins_unchanged']
    assert current['binding']==binding()
    for report in (regression,live):
        staged=report.parent/'source'
        for path in (ROOT/'apps/api/pao').rglob('*.py'):
            assert digest(path)==digest(staged/path.relative_to(ROOT)),'Tested backend source changed'
    assert web['frontend_unchanged_during_build']
    from pao.modules.operations.checkpoint import entries
    from backup_acos_checkpoint import frontend_supplements
    staged=Path(web['source'])
    original={k:v for k,v in {**entries(staged),**frontend_supplements(staged)}.items() if k.startswith('apps/web/')}
    current_files={k:v for k,v in {**entries(ROOT),**frontend_supplements(ROOT)}.items() if k.startswith('apps/web/')}
    assert set(original)==set(current_files),'Frontend source file set changed'
    for name,sha in original.items():
        if current_files[name]==sha:continue
        assert name=='apps/web/next-env.d.ts','Tested frontend source changed: '+name
        # Next typegen writes one environment-specific generated reference.
        # Verify the entire remainder; never normalize application code/caches.
        raw=(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
        candidate=(staged/name).read_bytes().replace(b'\r\n',b'\n')
        assert raw.count(b'./.pao-next/types/routes.d.ts')==1
        assert candidate.count(b'./.pao-build-check/types/routes.d.ts')==1
        assert raw.replace(b'./.pao-next/types/routes.d.ts',b'./.pao-build-check/types/routes.d.ts')==candidate
    value={'phase':'GD01','date':'2026-10-21','status':'in_progress','whole_phase_complete':False,
        'core_api_local_accepted':True,'production_accepted':False,'schema':'0075','physical_tables':161,'operations':429,
        'binding':current['binding'],'backend_regression':str(regression),'backend_tests':tests['counts'],
        'frontend_generated_type_reference_normalization':'verified_next_dev_vs_build_routes_only',
        'frontend':str(frontend),'node_tests':243,'installed':str(installed),'live_openai':str(live),
        'provider_quota_remaining':None,'billing_amount':None,'env_or_credentials_changed':False,
        'primary_schema_migrated':False,'native_cli_runtime_swapped':False,'candidate_0076_installed':False,
        'backup_before':'F:\\PAO-BOS Backup 001\\PAO-ACOS-Backups\\20261021T073403Z-ed028f5689ac4379af57d68d41eaf574',
        'cli_versions':{'codex':'0.157.1','claude_code':'2.1.220','antigravity':'1.4.3'},
        'remaining_implementation':['official_codex_plan_usage_and_shared_admission',
            'codex_candidate_profile_promotion_release_rollback','complete_model_modality_capability_catalog',
            'legacy_authority_migration_preview_and_deprecation'],
        'provider_gates':{'claude_live':'deferred_by_user_no_subscription',
            'anthropic_api_live':'key_not_configured','gemini_api_live':'key_not_configured',
            'antigravity_inference':'unsupported_consumer_wrapper_and_isolation_not_accepted'},
        'historical_failures_preserved':['gd01-tests-bfd63b52d9924becae23a9aa36ab2540',
            'gd01-tests-b4396d6faeb047ec8bf92d1481b382bc','gd01-installed-4005de5c30b14bce82d7fb4792efcdc9'],
        'next_phase_gd02_started':False}
    completion=ROOT/'.runtime'/('gd01-completion-'+uuid4().hex+'.json')
    write_new(completion,value)
    # The pointer is a current aggregate, never a rewritten historical receipt.
    pointer=ROOT/'.runtime/gd01-current-status.json'
    assert not pointer.exists(),'Existing current status needs explicit review'
    write_new(pointer,{**value,'completion':str(completion)})
    print(json.dumps({'status':str(pointer),'completion':str(completion),'core_api_local_accepted':True,'whole_phase_complete':False}))


if __name__=='__main__':main()
