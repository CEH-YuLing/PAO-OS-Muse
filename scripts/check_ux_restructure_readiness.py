"""Current UI overlay on the unchanged, independently verified backend baseline."""
import hashlib,json
from pathlib import Path
from zipfile import ZipFile

def verify_overlay(completion,release,binding,current_frontend):
 return (completion.get('pass') is True and completion.get('binding')==binding and completion.get('primary_unchanged') is True
  and completion.get('env_unchanged') is True and completion.get('installed_read_only') is True and completion.get('api_mutations')==0
  and release.get('pass') is True and release.get('backend_changed') is False and release.get('database_changed') is False
  and release.get('env_changed') is False and release.get('binding')==binding and release.get('node_tests')==157
  and release.get('frontend_files')==current_frontend)
def main():
 from pao.config import ROOT
 from pao.skills import execution_binding
 from pao.modules.operations.checkpoint import digest
 from check_s6_readiness import read_object,probe
 from check_organization_readiness import assess
 from prepare_ux_restructure_release import frontend
 assert ROOT.resolve()==Path('F:/PAO-ACOS')
 completion=read_object(ROOT/'.runtime/ux-restructure-completion.json')
 install=read_object(ROOT/'.runtime/ux-restructure-installed.json');backup=Path(install['backup']).resolve();assert backup.is_relative_to(ROOT/'.runtime')
 release=read_object(backup/'release.json');binding=execution_binding();assert verify_overlay(completion,release,binding,frontend(ROOT))
 original=read_object(ROOT/'.runtime/organization-installed.json');old_backup=Path(original['backup']).resolve();assert old_backup.is_relative_to(ROOT/'.runtime')
 old=read_object(old_backup/'release.json')
 ci_path=Path(old['ci']).resolve();focused_path=Path(old['focused']).resolve()
 for path in (ci_path,focused_path):assert path.is_relative_to(ROOT/'.runtime')
 ci=read_object(ci_path);focused=read_object(focused_path)
 with ZipFile(ci_path.parent/'source.zip') as frozen:
  for name in frozen.namelist():
   if name.startswith(('apps/api/','packages/')):assert digest(ROOT/name)==hashlib.sha256(frozen.read(name)).hexdigest()
 assert all(digest(ROOT/n)==h for n,h in focused['tested_files'].items())
 for name,proof in release['changes'].items():assert digest(ROOT/name)==proof['after']
 assert json.loads(Path(release['browser_receipt']).read_text())['connections_browser'] is True
 live=probe(ROOT,'check_organization_live.py');health=probe(ROOT,'check_acos_health.py')
 result=assess(live,health,completion,release,ci,focused,binding,True)
 result.update(version='s6-local-ux-restructure-v1',frontend_overlay=True,node_tests=157,backend_regression_reused=2272,production_accepted=False)
 (ROOT/'.runtime/s6-readiness.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result));return 0 if result['local_checks_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
