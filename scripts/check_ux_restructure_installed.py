"""Verify installed UI source identity, backend preservation and read-only browser."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_phase3_security_installed import principal_fixture
from prepare_ux_restructure_release import frontend,files

def main():
 assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
 candidate=Path('F:/Apex/ux-restructure-candidate');proof=json.loads((candidate/'.runtime/ux-restructure-release.json').read_text())
 assert frontend(ROOT)==frontend(candidate)==proof['frontend_files']
 assert all(digest(ROOT/n)==v['after'] for n,v in proof['changes'].items())
 folder=ROOT/'.runtime'/('ux-restructure-live-'+uuid4().hex);folder.mkdir()
 before=asyncio.run(snapshot(settings().database_url));env=digest(ROOT/'.env');binding=execution_binding();assert binding==proof['binding']
 (folder/'before.json').write_text(json.dumps(before),encoding='utf-8')
 for title,script in [('live','check_organization_live.py'),('health','check_acos_health.py')]:
  with (folder/(title+'.log')).open('wb') as log:subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
 fixture={**asyncio.run(principal_fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
 with (folder/'browser.log').open('wb') as log:subprocess.run(['node',str(ROOT/'scripts/ux_restructure_installed_browser.cjs')],cwd=ROOT,env={**os.environ,'PAO_UX_LIVE':json.dumps(fixture)},check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 result=json.loads((folder/'installed-browser.json').read_text());after=asyncio.run(snapshot(settings().database_url))
 (folder/'after.json').write_text(json.dumps(after),encoding='utf-8')
 changed=[n for n in set(before[1])|set(after[1]) if before[1].get(n)!=after[1].get(n)]
 result.update(pass_=not changed and env==digest(ROOT/'.env') and binding==execution_binding(),primary_unchanged=not changed,changed_tables=changed,env_unchanged=env==digest(ROOT/'.env'),binding=binding,evidence=str(folder),node_tests=157,backend_baseline_reused=2272,production_accepted=False)
 result['pass']=result.pop('pass_') and result['pass'];(folder/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));assert result['pass']
 assert frontend(ROOT)==proof['frontend_files']
 (ROOT/'.runtime/ux-restructure-completion.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
