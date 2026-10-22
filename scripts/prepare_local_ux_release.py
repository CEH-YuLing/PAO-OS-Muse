"""Prepare exact UI-only release; refuse overlapping user edits or absent browser proof."""
import hashlib,json,sys
from pathlib import Path
from check_local_ux_browser import frontend
from pao.config import ROOT
from pao.skills import execution_binding

def main():
 candidate=Path('F:/Apex/local-ux-candidate');receipt=Path(sys.argv[1]).resolve()
 assert receipt.is_relative_to(ROOT/'.runtime/local-ux-browser-runs')
 proof=json.loads(receipt.read_text());assert proof['pass'] and proof['light_dark_browser'] and proof['binding']==execution_binding()
 assert json.loads((receipt.parent/'cleanup.json').read_text())['pass'] is True
 theme=json.loads((receipt.parent/'theme-browser.json').read_text());assert theme['pass'] and theme['node_tests']==128 and theme['api_mutations']==0
 files=frontend(candidate);assert hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()==proof['frontend_sha256']
 baseline=json.loads((ROOT/'.runtime/checkpoints/p0-20261017T140245-abd8b8e6/manifest.json').read_text())['source']['files']
 current=frontend(ROOT);changes={}
 for name,digest in files.items():
  if current.get(name)==digest:continue
  assert current.get(name)==baseline.get(name),f'Overlapping user edit: {name}'
  changes[name]={'before':current.get(name),'after':digest}
 assert changes and set(current)<=set(files),'No removals allowed'
 assert all(name.startswith('apps/web/') for name in changes)
 result={'pass':True,'browser_receipt':str(receipt),'frontend_sha256':proof['frontend_sha256'],
   'binding':execution_binding(),'changes':changes,'backend_changed':False,'database_changed':False,'env_changed':False}
 output=candidate/'.runtime/local-ux-release.json';output.parent.mkdir(exist_ok=True)
 assert not output.exists();output.write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps({'pass':True,'changed_frontend_files':len(changes),'manifest':str(output)}))
if __name__=='__main__':main()
