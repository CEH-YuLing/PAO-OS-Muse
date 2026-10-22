"""Read-only source/contract/replay/UI verification after local cutover."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_phase3_security_installed import principal_fixture
from prepare_organization_release import files

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    candidate=Path('F:/Apex/enterprise-knowledge-candidate');release=json.loads((candidate/'.runtime/organization-release.json').read_text())
    for name,value in release['changes'].items():assert digest(ROOT/name)==value['after']
    assert files(ROOT)==files(candidate)
    folder=ROOT/'.runtime'/('organization-live-'+uuid4().hex);folder.mkdir()
    before=asyncio.run(snapshot(settings().database_url));env=digest(ROOT/'.env');binding=execution_binding()
    assert binding==release['after_binding']
    (folder/'before.json').write_text(json.dumps(before),encoding='utf-8')
    for title,script in [('live','check_organization_live.py'),('health','check_acos_health.py')]:
        with (folder/(title+'.log')).open('wb') as log:subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    live=json.loads((ROOT/'.runtime/organization-live.json').read_text());assert live['pass'] and live['read_only_replays']==3 and live['operations']==406
    fixture={**asyncio.run(principal_fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
    with (folder/'browser.log').open('wb') as log:subprocess.run(['node',str(ROOT/'scripts/organization_installed_browser.cjs')],cwd=ROOT,env={**os.environ,'PAO_UX_LIVE':json.dumps(fixture)},check=True,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    browser=json.loads((folder/'installed-browser.json').read_text());assert browser['pass'] and browser['api_mutations']==0
    after=asyncio.run(snapshot(settings().database_url));(folder/'after.json').write_text(json.dumps(after),encoding='utf-8')
    changed=[name for name in set(before[1])|set(after[1]) if before[1].get(name)!=after[1].get(name)]
    result={**browser,'pass':not changed and env==digest(ROOT/'.env') and binding==execution_binding(),'primary_unchanged':not changed,'changed_tables':changed,'env_unchanged':env==digest(ROOT/'.env'),
        'binding':binding,'schema':'0071','operations':406,'tables':153,'historical_replays':3,'release':str(candidate/'.runtime/organization-release.json'),'evidence':str(folder),'production_accepted':False,'real_data_accepted':False}
    (folder/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));assert result['pass']
    (ROOT/'.runtime/organization-completion.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
if __name__=='__main__':main()
