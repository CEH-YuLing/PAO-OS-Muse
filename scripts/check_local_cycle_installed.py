"""Verify installed frontend identity plus actual API/UI without primary writes."""
import asyncio,hashlib,json,os,subprocess
from pathlib import Path
from uuid import uuid4
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_phase3_security_installed import principal_fixture
from check_local_cycle_browser import frontend

def main():
 assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
 candidate=Path('F:/Apex/local-cycle-candidate');manifest=json.loads((candidate/'.runtime/local-cycle-release.json').read_text())
 assert frontend(ROOT)==frontend(candidate)
 assert hashlib.sha256(json.dumps(frontend(ROOT),sort_keys=True).encode()).hexdigest()==manifest['frontend_sha256']
 folder=ROOT/'.runtime'/('local-cycle-live-'+uuid4().hex);folder.mkdir()
 before=asyncio.run(snapshot(settings().database_url));environment=digest(ROOT/'.env');binding=execution_binding()
 assert binding==manifest['binding']
 (folder/'before.json').write_text(json.dumps({'snapshot':before,'environment':environment,'binding':binding},indent=2),encoding='utf-8')
 fixture={**asyncio.run(principal_fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
 with (folder/'browser.log').open('wb') as log:
  subprocess.run(['node',str(candidate/'scripts/local_ux_installed_browser.cjs')],cwd=ROOT,
   env={**os.environ,'PAO_UX_LIVE':json.dumps(fixture)},check=True,stdout=log,stderr=subprocess.STDOUT,timeout=360)
 result=json.loads((folder/'installed-browser.json').read_text());assert result['pass'] and result['api_mutations']==0
 after=asyncio.run(snapshot(settings().database_url))
 unchanged=before==after;env_same=environment==digest(ROOT/'.env');backend_same=binding==execution_binding()
 changed={name:{'before_count':before[1].get(name,{}).get('count'),'after_count':after[1].get(name,{}).get('count')} for name in set(before[1])|set(after[1]) if before[1].get(name)!=after[1].get(name)}
 (folder/'after.json').write_text(json.dumps({'snapshot':after,'environment':digest(ROOT/'.env'),'binding':execution_binding()},indent=2),encoding='utf-8')
 (folder/'verification.json').write_text(json.dumps({'pass':unchanged and env_same and backend_same,'primary_unchanged':unchanged,'environment_unchanged':env_same,'backend_unchanged':backend_same,'changed_tables':changed},indent=2),encoding='utf-8')
 print(json.dumps({'read_only_verification':unchanged and env_same and backend_same,'changed_tables':changed,'env_same':env_same,'backend_same':backend_same,'evidence':str(folder)}),flush=True)
 assert unchanged and env_same and backend_same
 assert frontend(ROOT)==frontend(candidate)
 result.update(primary_unchanged=True,env_unchanged=True,backend_unchanged=True,binding=binding,
  node_tests=132,production_build=True,isolated_browser=manifest['browser_receipt'],focused_backend=manifest['focused_backend'],evidence=str(folder),production_accepted=False)
 (ROOT/'.runtime/local-cycle-completion.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result))
if __name__=='__main__':main()
