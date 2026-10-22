"""Bind additive local feature release to frozen CI, native browser and baseline."""
import hashlib,json,sys
from pathlib import Path
from zipfile import ZipFile
from pao.config import ROOT
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import frontend_supplements
from check_phase3_readiness import is_runtime_source

def files(root):
    return {k:v for k,v in {**entries(root),**frontend_supplements(root)}.items() if not k.endswith('next-env.d.ts')}
def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    candidate=Path('F:/Apex/enterprise-knowledge-candidate')
    ci_path,browser_path,focused_path=[Path(p).resolve() for p in sys.argv[1:]]
    for p in (ci_path,browser_path,focused_path):assert p.is_relative_to(ROOT/'.runtime') and p.is_file()
    ci,browser,focused=[json.loads(p.read_text()) for p in (ci_path,browser_path,focused_path)]
    assert ci['pass'] and ci['linux_execution'] and ci['node_and_typecheck_and_build'] and ci['owned_containers_removed'] and ci['primary_unchanged'] and ci['env_unchanged']
    assert ci['backend']['tests']>=2272 and all(ci['backend'][k]==0 for k in ('failures','errors','skipped'))
    assert browser['pass'] and browser['organization_browser'] and browser['production_build'] and browser['primary_unchanged']
    assert json.loads((browser_path.parent/'cleanup.json').read_text())['pass']
    assert json.loads((browser_path.parent/'organization-browser.json').read_text())['pass']
    assert focused['pass'] and focused['tests']==202 and focused['primary_env_backend_unchanged']
    assert focused['binding']==browser['binding']==execution_binding()
    assert focused['candidate_source_unchanged']
    assert all(digest(candidate/n)==h for n,h in focused['tested_files'].items())
    assert all(focused[k]==0 for k in ('failures','errors','skipped'))
    current=files(ROOT);proposed=files(candidate)
    frontend={n:h for n,h in proposed.items() if n.startswith('apps/web/')}
    assert hashlib.sha256(json.dumps(frontend,sort_keys=True).encode()).hexdigest()==browser['frontend_sha256']
    frozen_names=set()
    with ZipFile(ci_path.parent/'source.zip') as frozen:
        for name in frozen.namelist():
            frozen_names.add(name)
            if is_runtime_source(name) or name.startswith(('apps/web/','packages/contracts/','apps/api/tests/')) or name in ('requirements.lock','requirements-dev.lock','package.json','package-lock.json'):
                if name.endswith('next-env.d.ts'):continue
                assert digest(candidate/name)==hashlib.sha256(frozen.read(name)).hexdigest(),'Candidate changed after CI: '+name
    assert all(n in frozen_names for n in proposed if is_runtime_source(n) or n.startswith(('apps/web/','apps/api/tests/','packages/contracts/')))
    baseline=json.loads((ROOT/'.runtime/checkpoints/p0-20261018T032559-1e25c407/manifest.json').read_text())['source']['files']
    assert set(current)<=set(proposed),'No source removal authorized'
    changes={}
    for name,hashed in proposed.items():
        if current.get(name)==hashed:continue
        assert current.get(name)==baseline.get(name),'Preserve overlapping user change: '+name
        assert name.startswith(('apps/','packages/contracts/','scripts/','docs/')) or name=='AGENTS.md'
        changes[name]={'before':current.get(name),'after':hashed}
    assert changes and not any(n.startswith('apps/api/migrations/') or n.endswith('models.py') for n in changes)
    result={'pass':True,'changes':changes,'ci':str(ci_path),'browser':str(browser_path),'focused':str(focused_path),
        'before_binding':execution_binding(),'after_binding':focused['tested_binding'],'schema':'0071','physical_tables':153,'operations':406,'environment_changed':False,'production_accepted':False}
    output=candidate/'.runtime/organization-release.json';output.parent.mkdir(exist_ok=True)
    assert not output.exists();output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'pass':True,'changed_files':list(changes),'manifest':str(output)}))
if __name__=='__main__':main()
