from copy import deepcopy
from check_phase3_readiness import assess_archive

def good():
 return {'pass':True,'source_image':'reviewed-image',**{k:True for k in ('internal_network','readonly_clone_role','source_archive_hashes_match','primary_unchanged','owned_resources_removed')},
   'archive_reader':{'pass':True,'archives_read':3,'incompatible_execution_denied':3,'tools_reexecuted':False,'archive_hashes':['a','b','c']}}

def test_read_compatibility_never_grants_execution_or_full_production_restore():
 result=assess_archive(good(),'reviewed-image')
 assert result['archive_read_on_candidate_accepted'] and result['old_binding_execution_denied']
 assert not result['existing_archive_cold_restore_accepted'] and not result['full_production_restore_accepted']

def test_missing_stale_or_writable_clone_is_rejected():
 assert not assess_archive({},'reviewed-image')['archive_read_on_candidate_accepted']
 assert not assess_archive(good(),'other-image')['archive_read_on_candidate_accepted']
 for key in ('internal_network','readonly_clone_role','source_archive_hashes_match','primary_unchanged','owned_resources_removed'):
  value=good();value[key]=False;assert not assess_archive(value,'reviewed-image')['archive_read_on_candidate_accepted']

def test_reading_cannot_hide_execution_or_missing_archives():
 for key,value in [('tools_reexecuted',True),('incompatible_execution_denied',2),('archives_read',2),('archive_hashes',[])]:
  receipt=good();receipt['archive_reader'][key]=value
  assert not assess_archive(receipt,'reviewed-image')['archive_read_on_candidate_accepted']
