"""Current local S6 diagnostic, tied to the additive feature's exact source proof.

Historical receipts are retained; no hosted/production acceptance is inferred.
"""
import hashlib,json,subprocess,sys
from pathlib import Path
from zipfile import ZipFile

def assess(live,health,completion,release,ci,focused,binding,source_verified):
    counts=ci.get('backend',{})
    tests=(ci.get('pass') is True and ci.get('linux_execution') is True and ci.get('primary_unchanged') is True
        and ci.get('env_unchanged') is True and ci.get('owned_containers_removed') is True
        and type(counts.get('tests')) is int and counts['tests']>=2272
        and all(type(counts.get(k)) is int and counts[k]==0 for k in ('failures','errors','skipped'))
        and focused.get('pass') is True and focused.get('candidate_source_unchanged') is True
        and focused.get('tests')==202 and focused.get('tested_binding')==binding)
    installed=(source_verified is True and completion.get('pass') is True and completion.get('binding')==binding
        and release.get('pass') is True and release.get('after_binding')==binding
        and completion.get('primary_unchanged') is True and completion.get('env_unchanged') is True
        and completion.get('installed_read_only') is True and completion.get('api_mutations')==0)
    baseline=(live.get('pass') is True and live.get('binding')==binding and live.get('revision')=='0071'
        and live.get('operations')==406 and live.get('physical_tables')==153 and live.get('read_only_replays')==3
        and live.get('provider_calls') is False and live.get('business_hashes_unchanged') is True)
    runtime=(all(health.get('endpoints',{}).get(k)==200 for k in ('api_health','api_ready','web'))
        and health.get('operations',{}).get('worker',{}).get('healthy') is True)
    return {'version':'s6-local-organization-v1','local_checks_passed':bool(tests and installed and baseline and runtime),
        'binding':binding,'s6_accepted':False,'production_accepted':False,'provider_calls':False,'business_writes':False,
        'gates':[{'id':'installed_contract_replays','state':'pass' if baseline and installed else 'fail'},
            {'id':'current_source_regression','state':'pass' if tests else 'fail'},
            {'id':'windows_runtime','state':'pass' if runtime else 'fail'},
            {'id':'s6_1_real_business','state':'external_pending'},
            {'id':'s6_1_real_action','state':'external_pending'},
            {'id':'s6_2_hosted_ci_current_source','state':'external_pending'},
            {'id':'s6_2_production','state':'deferred_by_user'},
            {'id':'s6_3_owner_pilot','state':'external_pending'}]}

def main():
    from pao.config import ROOT
    from pao.skills import execution_binding
    from pao.modules.operations.checkpoint import digest
    from check_s6_readiness import read_object,probe
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    completion=read_object(ROOT/'.runtime/organization-completion.json')
    release_path=Path(completion['release']).resolve()
    # Installed copy of the exact release; do not depend on candidate remaining.
    installed=read_object(ROOT/'.runtime/organization-installed.json')
    backup=Path(installed['backup']).resolve();assert backup.is_relative_to(ROOT/'.runtime')
    release=read_object(backup/'release.json')
    def receipt(name):
        path=Path(release[name]).resolve();assert path.is_relative_to(ROOT/'.runtime');return path,read_object(path)
    ci_path,ci=receipt('ci');_,focused=receipt('focused')
    with ZipFile(ci_path.parent/'source.zip') as frozen:
        for name in frozen.namelist():
            if name.startswith(('apps/','packages/')) and not name.endswith('next-env.d.ts'):
                assert digest(ROOT/name)==hashlib.sha256(frozen.read(name)).hexdigest(),'Installed source differs from frozen CI'
    assert all(digest(ROOT/n)==h['after'] for n,h in release['changes'].items())
    assert all(digest(ROOT/n)==h for n,h in focused['tested_files'].items())
    binding=execution_binding();live=probe(ROOT,'check_organization_live.py');health=probe(ROOT,'check_acos_health.py')
    result=assess(live,health,completion,release,ci,focused,binding,True)
    result.update(local_release=str(backup/'release.json'),ci=str(ci_path),candidate_path_not_required=str(release_path))
    (ROOT/'.runtime/s6-readiness.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    return 0 if result['local_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
