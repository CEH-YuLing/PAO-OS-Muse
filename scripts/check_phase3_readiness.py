"""Local evidence assessor; never grants hosted CI, public deploy or production acceptance."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
from zipfile import ZipFile
from pao.config import ROOT
from pao.skills import execution_binding
def assess(ci,private,ci_current,private_current):
 counts=ci.get('backend',{})
 pipeline=ci.get('pass') is True and ci.get('linux_execution') is True and ci.get('node_and_typecheck_and_build') is True and all(ci.get(k) is True for k in ('primary_unchanged','env_unchanged','owned_containers_removed')) and counts.get('tests',0)>=2258 and all(counts.get(k)==0 for k in ('failures','errors','skipped')) and ci_current
 profile=private.get('pass') is True and private_current and all(private.get(k) is True for k in ('tls_private_ca_verified','least_privilege','api_login_two_smes','static_assets','file_secrets_not_docker_env','nonroot_readonly','container_restart','primary_unchanged','env_unchanged','backend_unchanged','owned_resources_removed'))
 return {'local_prepared':bool(pipeline and profile),'production_accepted':False,'s6_accepted':False,'gates':[
  {'id':'clean_linux_pipeline','state':'local_accepted' if pipeline else 'pending'},
  {'id':'private_container_profile','state':'local_accepted' if profile else 'pending'},
  *[{'id':name,'state':'external_pending'} for name in ('hosted_ci_authorized_run','dedicated_host_inventory_and_minimum_db_role',
    'public_https_dns_firewall_and_proxy_trust','private_storage_and_operator_alerts','key_rotation_offsite_and_cold_restore',
    'host_reboot_failover_drill','owner_production_review')]]}
def current_source(folder,kind):
 # Relevant execution inputs only. Docs and independent operator helpers are not
 # represented as having been executed by an earlier backend regression.
 if not (folder/'source.zip').is_file():return False
 with ZipFile(folder/'source.zip') as archive:
  names=archive.namelist()
  selected=[n for n in names if n.startswith(('apps/','packages/')) or n in ('requirements.lock','requirements-dev.lock','package.json','package-lock.json','pyproject.toml','alembic.ini')]
  if kind=='private':selected += [n for n in names if n.startswith('infra/production/')]
  else:selected += [n for n in names if n in ('scripts/ci_entry.py','scripts/s6_linux_entry.py','scripts/run_p0_checks.py','scripts/test_backend.py','.github/workflows/p0-foundation.yml')]
  selected=[n for n in selected if not n.endswith('next-env.d.ts') and not any(p.endswith('.egg-info') for p in Path(n).parts)]
  # Reject newly-added runtime source as well as mutations/removals. Operator
  # receipts/docs and separately-tested Windows helpers are not app source.
  frozen_runtime={n for n in selected if n.startswith(('apps/','packages/'))}
  if frozen_runtime!=runtime_source_names(ROOT):return False
  return bool(selected) and all((ROOT/n).is_file() and hashlib.sha256(archive.read(n)).hexdigest()==hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in selected)

def runtime_source_names(root):
 from pao.modules.operations.checkpoint import entries
 from backup_acos_checkpoint import source_supplements
 names=set(entries(root))|set(source_supplements(root))
 return {n for n in names if is_runtime_source(n)}

def is_runtime_source(name):
 return name.startswith(('apps/','packages/')) and not name.endswith('next-env.d.ts') and not any(p.endswith('.egg-info') for p in Path(name).parts)

def assess_archive(receipt,image):
 reader=receipt.get('archive_reader',{})
 accepted=receipt.get('pass') is True and receipt.get('source_image')==image and all(receipt.get(k) is True for k in ('internal_network','readonly_clone_role','source_archive_hashes_match','primary_unchanged','owned_resources_removed')) and reader.get('pass') is True and reader.get('archives_read')==3 and reader.get('incompatible_execution_denied')==3 and reader.get('tools_reexecuted') is False and len(reader.get('archive_hashes',[]))==3
 return {'archive_read_on_candidate_accepted':accepted,'old_binding_execution_denied':accepted,
         'existing_archive_cold_restore_accepted':False,'full_production_restore_accepted':False}
def main():
 ci_path=Path(sys.argv[1]).resolve();private_path=Path(sys.argv[2]).resolve()
 for path in (ci_path,private_path):assert path.is_relative_to(ROOT/'.runtime') and path.is_file()
 ci=json.loads(ci_path.read_text());private=json.loads(private_path.read_text());result=assess(ci,private,current_source(ci_path.parent,'ci'),current_source(private_path.parent,'private'))
 result.update(ci_evidence=str(ci_path),private_evidence=str(private_path),binding_primary=execution_binding(),hosted_ci_executed=False)
 # A Python patch is part of EXECUTION binding. Historical reading already uses
 # hash/scope/integrity instead; do not infer a read failure from different runtimes.
 rid=private_path.parent.name.removeprefix('phase3-private-');assert re.fullmatch('[0-9a-f]{32}',rid)
 image='pao-release-api:'+rid
 checked=subprocess.run(['docker','image','inspect',image,'--format','{{index .Config.Labels "pao.release.runid"}}'],check=True,capture_output=True,text=True)
 assert checked.stdout.strip()==rid
 checked=subprocess.run(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','python',image,'-c',
  'import json,platform;from pao.skills import execution_binding;print(json.dumps({"python":platform.python_version(),"binding":execution_binding()}))'],check=True,capture_output=True,text=True,timeout=30)
 result['candidate_runtime']=json.loads(checked.stdout)
 result['archive_binding_matches_primary']=result['candidate_runtime']['binding']==result['binding_primary']
 result['existing_archive_cold_restore_accepted']=False
 result['archive_read_on_candidate_accepted']=False
 if len(sys.argv)==4:
  cold_path=Path(sys.argv[3]).resolve();assert cold_path.is_relative_to(ROOT/'.runtime') and cold_path.is_file()
  cold=json.loads(cold_path.read_text());result.update(assess_archive(cold,'pao-s6-linux:'+ci['run_id']))
  result['archive_read_evidence']=str(cold_path)
  if result['archive_read_on_candidate_accepted']:
   assert cold['archive_reader']['candidate_binding']==result['candidate_runtime']['binding']
 (ROOT/'.runtime/phase3-readiness.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(result))
 if not result['local_prepared']:raise SystemExit(1)
if __name__=='__main__':main()
