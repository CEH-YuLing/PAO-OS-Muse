from check_phase3_readiness import assess
def evidence():
 return ({'pass':True,'linux_execution':True,'node_and_typecheck_and_build':True,'primary_unchanged':True,'env_unchanged':True,'owned_containers_removed':True,'backend':{'tests':2258,'failures':0,'errors':0,'skipped':0}},
 {'pass':True,**{k:True for k in ('tls_private_ca_verified','least_privilege','api_login_two_smes','static_assets','file_secrets_not_docker_env','nonroot_readonly','container_restart','primary_unchanged','env_unchanged','backend_unchanged','owned_resources_removed')}})
def test_local_success_never_means_hosted_or_production():
 ci,private=evidence();result=assess(ci,private,True,True)
 assert result['local_prepared'] and not result['production_accepted'] and not result['s6_accepted']
 assert sum(g['state']=='external_pending' for g in result['gates'])==7
def test_skip_partial_or_stale_pipeline_rejected():
 for field,value in [('tests',2257),('failures',1),('errors',1),('skipped',1)]:
  ci,private=evidence();ci['backend'][field]=value;assert not assess(ci,private,True,True)['local_prepared']
 ci,private=evidence();assert not assess(ci,private,False,True)['local_prepared']
 assert not assess(ci,private,True,False)['local_prepared']
def test_configured_or_tls_alone_does_not_pass_private_gate():
 ci,private=evidence();private['least_privilege']=False;assert not assess(ci,private,True,True)['local_prepared']

def test_ci_drift_or_missing_cleanup_is_rejected_even_with_green_tests():
 for field in ('primary_unchanged','env_unchanged','owned_containers_removed'):
  for value in (False,None):
   ci,private=evidence();ci[field]=value
   assert not assess(ci,private,True,True)['local_prepared']
