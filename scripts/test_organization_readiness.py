"""Offline current-receipt gates, independent of local DB or credentials."""
from copy import deepcopy
import unittest
from check_organization_readiness import assess
B={'policy':'exact-backend-source-v1','sha256':'a'*64}
def evidence():return [
 {'pass':True,'binding':B,'revision':'0071','operations':406,'physical_tables':153,'read_only_replays':3,'provider_calls':False,'business_hashes_unchanged':True},
 {'endpoints':dict(api_health=200,api_ready=200,web=200),'operations':{'worker':{'healthy':True}}},
 {'pass':True,'binding':B,'primary_unchanged':True,'env_unchanged':True,'installed_read_only':True,'api_mutations':0},
 {'pass':True,'after_binding':B},
 {'pass':True,'linux_execution':True,'primary_unchanged':True,'env_unchanged':True,'owned_containers_removed':True,'backend':dict(tests=2272,failures=0,errors=0,skipped=0)},
 {'pass':True,'candidate_source_unchanged':True,'tests':202,'tested_binding':B},B,True]
class Gates(unittest.TestCase):
 def test_green_remains_local(self):
  r=assess(*evidence());self.assertTrue(r['local_checks_passed']);self.assertFalse(r['production_accepted']);self.assertFalse(r['s6_accepted'])
 def test_source_required(self):
  e=evidence();e[-1]=False;self.assertFalse(assess(*e)['local_checks_passed'])
 def test_binding_stale(self):
  for index,key in [(0,'binding'),(2,'binding'),(3,'after_binding'),(5,'tested_binding')]:
   e=deepcopy(evidence());e[index][key]={};self.assertFalse(assess(*e)['local_checks_passed'])
 def test_failed_skipped_or_short_full_run(self):
  for key,value in [('failures',1),('errors',1),('skipped',1),('tests',2271),('tests',True)]:
   e=deepcopy(evidence());e[4]['backend'][key]=value;self.assertFalse(assess(*e)['local_checks_passed'])
 def test_truthy_pass_not_proof(self):
  for index in [0,2,3,4,5]:
   e=deepcopy(evidence());e[index]['pass']='true';self.assertFalse(assess(*e)['local_checks_passed'])
 def test_contract_or_replay_drift(self):
  for key,value in [('operations',399),('physical_tables',152),('read_only_replays',2),('provider_calls',True)]:
   e=deepcopy(evidence());e[0][key]=value;self.assertFalse(assess(*e)['local_checks_passed'])
 def test_worker_dead(self):
  e=deepcopy(evidence());e[1]['operations']['worker']['healthy']=False;self.assertFalse(assess(*e)['local_checks_passed'])
if __name__=='__main__':unittest.main()
