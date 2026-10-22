"""UI-only release proof; never reuse a backend baseline for changed API source."""
import hashlib,json,sys
from pathlib import Path
from pao.config import ROOT
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import frontend_supplements

def files(root):return {n:h for n,h in {**entries(root),**frontend_supplements(root)}.items() if not n.endswith('next-env.d.ts')}
def frontend(root):return {n:h for n,h in files(root).items() if n.startswith('apps/web/')}
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def main():
 assert ROOT.resolve()==Path('F:/PAO-ACOS')
 candidate=Path('F:/Apex/connections-ui-candidate');path=Path(sys.argv[1]).resolve();assert path.is_relative_to(ROOT/'.runtime/connections-ui-browser-runs')
 browser=json.loads(path.read_text());assert all(browser.get(k) is True for k in ('pass','connections_browser','production_build','primary_unchanged','environment_unchanged','m6_journey'))
 assert browser['node_tests']==148 and browser['binding']==execution_binding()
 assert json.loads((path.parent/'cleanup.json').read_text())['pass'] is True
 assert json.loads((path.parent/'connections-browser.json').read_text())['connection_mutations']==0
 before=files(ROOT);after=files(candidate);baseline=json.loads((candidate/'.runtime/baseline.json').read_text())
 # A diagnostic-only follow-up may supersede an already installed UI release.
 # Rebase only paths proven installed by that immutable receipt; preserve all
 # other original baseline guards and require identical frontend evidence.
 if len(sys.argv)>2:
  prior_path=Path(sys.argv[2]).resolve();installed=json.loads((ROOT/'.runtime/connections-ui-installed.json').read_text(encoding='utf-8-sig'))
  assert prior_path==Path(installed['backup']).resolve()/'release.json'
  assert prior_path.is_relative_to(ROOT/'.runtime') and installed['pass'] is True
  prior=json.loads(prior_path.read_text(encoding='utf-8-sig'))
  assert prior['pass'] is True and prior['binding']==execution_binding() and prior['frontend_files']==frontend(ROOT)==frontend(candidate)
  assert all(before.get(n)==v['after'] for n,v in prior['changes'].items())
  baseline.update({n:v['after'] for n,v in prior['changes'].items()})
 assert set(before)<=set(after)
 changes={}
 for name,hashed in after.items():
  if before.get(name)==hashed:continue
  assert name.startswith(('apps/web/','scripts/','docs/')),'UI-only source scope: '+name
  assert before.get(name)==baseline.get(name),'Preserve overlapping changes: '+name
  changes[name]={'before':before.get(name),'after':hashed}
 assert fingerprint(frontend(candidate))==browser['frontend_sha256']
 assert all(before.get(n)==h for n,h in after.items() if n.startswith(('apps/api/','packages/')) or n in ('requirements.lock','requirements-dev.lock','package.json','package-lock.json'))
 result={'pass':True,'changes':changes,'browser_receipt':str(path),'frontend_sha256':fingerprint(frontend(candidate)),
  'frontend_files':frontend(candidate),'before_frontend_files':frontend(ROOT),'binding':execution_binding(),'before_binding':execution_binding(),'after_binding':execution_binding(),
  'backend_changed':False,'database_changed':False,'env_changed':False,'node_tests':148,'production_accepted':False,
  'supersedes':str(prior_path) if len(sys.argv)>2 else None}
 output=candidate/'.runtime/connections-ui-release.json';assert not output.exists();output.write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps({'pass':True,'manifest':str(output),'changed_files':list(changes)}))
if __name__=='__main__':main()
