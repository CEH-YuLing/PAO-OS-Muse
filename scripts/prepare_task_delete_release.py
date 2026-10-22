"""Hash-guarded bounded feature release; historical full CI is not reused."""
import hashlib,json,sys
from pathlib import Path
from pao.config import ROOT
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import source_supplements

def files(root):
    return {n:h for n,h in {**entries(root),**source_supplements(root)}.items() if not n.endswith('next-env.d.ts')}

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    candidate=Path('F:/Apex/task-delete-candidate')
    backend_path,browser_path=map(Path,sys.argv[1:])
    assert backend_path.resolve().is_relative_to(candidate/'.runtime')
    assert browser_path.resolve().is_relative_to(ROOT/'.runtime/task-delete-browser-runs')
    backend=json.loads(backend_path.read_text());browser=json.loads(browser_path.read_text())
    assert backend['pass'] and backend['primary_environment_unchanged'] and backend['source_unchanged']
    assert backend['tests']>=200 and all(backend[k]==0 for k in ('failures','errors','skipped'))
    assert all(digest(candidate/n)==h for n,h in backend['tested_source'].items())
    assert browser['pass'] and browser['primary_unchanged'] and browser['environment_unchanged']
    assert json.loads((browser_path.parent/'cleanup.json').read_text())['pass']
    current=files(ROOT);after=files(candidate)
    frontend={n:h for n,h in after.items() if n.startswith('apps/web/')}
    assert hashlib.sha256(json.dumps(frontend,sort_keys=True).encode()).hexdigest()==browser['frontend_sha256']
    baseline=json.loads((candidate/'.runtime/baseline.json').read_text())
    changes={}
    for name,hashed in after.items():
        if current.get(name)==hashed:continue
        assert current.get(name)==baseline.get(name),'Preserve overlapping changes: '+name
        assert name.startswith(('apps/api/','apps/web/','packages/contracts/','scripts/','docs/'))
        assert not name.startswith('apps/api/migrations/') and not name.endswith('models.py')
        changes[name]={'before':current.get(name),'after':hashed}
    assert changes
    result={'pass':True,'changes':changes,'schema':'0071','environment_changed':False,
            'backend_receipt':str(backend_path),'browser_receipt':str(browser_path),
            'full_backend_regression':False,'production_accepted':False}
    out=candidate/'.runtime/task-delete-release.json';assert not out.exists()
    out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(str(out))

if __name__=='__main__':main()
