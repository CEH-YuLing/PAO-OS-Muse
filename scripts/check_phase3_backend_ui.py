"""Read-only installed UI check after backend-only dependency cutover."""
import asyncio,json,os,subprocess
from pathlib import Path
from uuid import uuid4
from importlib.metadata import version
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_phase3_security_installed import principal_fixture

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    assert version('PyJWT')=='2.15.1' and version('cryptography')=='50.0.2'
    before=asyncio.run(snapshot(settings().database_url));env_hash=digest(ROOT/'.env');binding=execution_binding()
    folder=ROOT/'.runtime'/('phase3-backend-ui-'+uuid4().hex);folder.mkdir()
    fixture={**asyncio.run(principal_fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
    with (folder/'browser.log').open('wb') as log:
        subprocess.run(['node','scripts/m6_installed_browser.cjs'],cwd=ROOT,env={**os.environ,'PAO_M6_LIVE':json.dumps(fixture)},stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    result=json.loads((folder/'installed-browser.json').read_text())
    assert result['pass'] and result['read_only'] and result['api_mutations']==0
    assert before==asyncio.run(snapshot(settings().database_url)) and env_hash==digest(ROOT/'.env')
    result.update(binding=binding,python_dependencies={'PyJWT':version('PyJWT'),'cryptography':version('cryptography')},
        primary_unchanged=True,env_unchanged=True,backend_windows_full_rerun=False,production_accepted=False,evidence=str(folder))
    (ROOT/'.runtime/phase3-backend-ui.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
