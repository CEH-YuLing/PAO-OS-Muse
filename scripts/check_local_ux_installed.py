"""Verify installed frontend identity plus actual API/UI without primary writes."""
import asyncio,hashlib,json,os,subprocess
from pathlib import Path
from uuid import uuid4
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_phase3_security_installed import principal_fixture
from check_local_ux_browser import frontend

def main():
 assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
 candidate=Path('F:/Apex/local-ux-candidate');manifest=json.loads((candidate/'.runtime/local-ux-release.json').read_text())
 assert frontend(ROOT)==frontend(candidate)
 assert hashlib.sha256(json.dumps(frontend(ROOT),sort_keys=True).encode()).hexdigest()==manifest['frontend_sha256']
 before=asyncio.run(snapshot(settings().database_url));environment=digest(ROOT/'.env');binding=execution_binding()
 assert binding==manifest['binding']
 folder=ROOT/'.runtime'/('local-ux-live-'+uuid4().hex);folder.mkdir()
 fixture={**asyncio.run(principal_fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
 with (folder/'browser.log').open('wb') as log:
  subprocess.run(['node',str(candidate/'scripts/local_ux_installed_browser.cjs')],cwd=ROOT,
   env={**os.environ,'PAO_UX_LIVE':json.dumps(fixture)},check=True,stdout=log,stderr=subprocess.STDOUT,timeout=360)
 result=json.loads((folder/'installed-browser.json').read_text());assert result['pass'] and result['api_mutations']==0
 assert before==asyncio.run(snapshot(settings().database_url)) and environment==digest(ROOT/'.env') and binding==execution_binding()
 assert frontend(ROOT)==frontend(candidate)
 result.update(primary_unchanged=True,env_unchanged=True,backend_unchanged=True,binding=binding,
  node_tests=128,production_build=True,isolated_browser=manifest['browser_receipt'],evidence=str(folder),production_accepted=False)
 (ROOT/'.runtime/local-ux-completion.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result))
if __name__=='__main__':main()
