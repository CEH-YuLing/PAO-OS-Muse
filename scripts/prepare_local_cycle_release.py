"""Bind a UI-only release to native business/browser and focused backend proof."""
import hashlib,json,sys
from pathlib import Path
from check_local_cycle_browser import frontend
from pao.config import ROOT
from pao.skills import execution_binding
def main():
 candidate=Path('F:/Apex/local-cycle-candidate');receipt=Path(sys.argv[1]).resolve();focused=Path(sys.argv[2]).resolve()
 assert receipt.is_relative_to(ROOT/'.runtime/local-cycle-browser-runs') and focused.parent.parent==ROOT/'.runtime' and focused.parent.name.startswith('local-cycle-focused-')
 proof=json.loads(receipt.read_text());tests=json.loads(focused.read_text())
 assert proof['pass'] and proof['cycle_browser'] and proof['node_tests']==132 and proof['binding']==execution_binding()
 assert tests['pass'] and tests['primary_env_backend_unchanged'] and tests['binding']==execution_binding() and tests['tests']==125 and not any(tests[k] for k in ('failures','errors','skipped'))
 assert json.loads((receipt.parent/'cleanup.json').read_text())['pass']
 assert json.loads((receipt.parent/'cycle-browser.json').read_text())['pass']
 files=frontend(candidate);assert hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()==proof['frontend_sha256']
 baseline=json.loads((ROOT/'.runtime/checkpoints/p0-20261018T024335-ec6839c1/manifest.json').read_text())['source']['files']
 current=frontend(ROOT);changes={}
 for name,hashed in files.items():
  if current.get(name)==hashed:continue
  assert current.get(name)==baseline.get(name),'Overlapping source change: '+name
  changes[name]={'before':current.get(name),'after':hashed}
 assert changes and set(current)<=set(files) and all(n.startswith('apps/web/') for n in changes)
 result={'pass':True,'browser_receipt':str(receipt),'focused_backend':str(focused),'frontend_sha256':proof['frontend_sha256'],'binding':execution_binding(),'changes':changes,'backend_changed':False,'database_changed':False,'env_changed':False}
 output=candidate/'.runtime/local-cycle-release.json';output.parent.mkdir(exist_ok=True);assert not output.exists();output.write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps({'pass':True,'changed_frontend_files':len(changes),'manifest':str(output)}))
if __name__=='__main__':main()
