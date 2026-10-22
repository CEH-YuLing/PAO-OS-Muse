"""Offline current-release/failed-snapshot guards; no real DB or providers."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from check_s6_readiness import assess_current, failed_snapshot

BINDING = {'policy':'exact-backend-source-v1', 'sha256':'a'*64}
def evidence():
    return [
        {'pass':True,'binding':BINDING,'revision':'0071','operations':407,'physical_tables':153,
         'read_only_replays':3,'business_hashes_unchanged':True,'provider_calls':False},
        {'endpoints':dict(api_health=200,api_ready=200,web=200),'operations':{'worker':{'healthy':True}}},
        {'binding':BINDING,'primary_incident_review':'resolved_with_evidence'},
        {'pass':True,'binding':BINDING,'primary_unchanged':True,'environment_unchanged':True,'api_mutations':0},
        {'pass':True,'linux_execution':True,'node_and_typecheck_and_build':True,'primary_unchanged':True,
         'env_unchanged':True,'owned_containers_removed':True,
         'backend':dict(tests=2293,failures=0,errors=0,skipped=0)}, BINDING, True, True]

class CurrentReadiness(unittest.TestCase):
    def test_fresh_current_local_proof_never_closes_external_gates(self):
        result = assess_current(*evidence())
        self.assertTrue(result['local_checks_passed'])
        self.assertFalse(result['s6_accepted']); self.assertFalse(result['production_accepted'])
        self.assertEqual(sum(g['state']=='external_pending' for g in result['gates']),4)

    def test_clean_rerun_does_not_resolve_old_incident(self):
        for value in (None, 'unresolved', True):
            e=deepcopy(evidence()); e[2]['primary_incident_review']=value
            self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_stale_binding_or_source_never_passes(self):
        for index in (0,2,3):
            e=deepcopy(evidence()); e[index]['binding']={}
            self.assertFalse(assess_current(*e)['local_checks_passed'])
        e=evidence(); e[-2]=False
        self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_edited_resolution_label_is_not_verified_incident_review(self):
        e=evidence();e[-1]=False
        self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_functional_ci_pass_does_not_override_primary_guard(self):
        for key in ('pass','linux_execution','node_and_typecheck_and_build','primary_unchanged','env_unchanged','owned_containers_removed'):
            for value in (False, 'true', None):
                e=deepcopy(evidence()); e[4][key]=value
                self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_full_counts_are_strict(self):
        for key,value in [('tests',2292),('tests',True),('errors',1),('failures',1),('skipped',1),('skipped',False)]:
            e=deepcopy(evidence());e[4]['backend'][key]=value
            self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_partial_install_or_truthy_flags_refused(self):
        for key,value in [('pass','true'),('api_mutations',1),('api_mutations',False),('primary_unchanged',False),('environment_unchanged',False)]:
            e=deepcopy(evidence());e[3][key]=value
            self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_contract_worker_and_archive_guards(self):
        for key,value in [('revision','0070'),('operations',406),('physical_tables',152),('read_only_replays',2),('provider_calls',True)]:
            e=deepcopy(evidence());e[0][key]=value
            self.assertFalse(assess_current(*e)['local_checks_passed'])
        e=evidence();e[1]['operations']['worker']['healthy']='true'
        self.assertFalse(assess_current(*e)['local_checks_passed'])

    def test_failure_replaces_old_green_with_fresh_false_not_historical_receipt(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'.runtime';runtime.mkdir()
            (runtime/'s6-readiness.json').write_text('{"local_checks_passed":true}')
            history=runtime/'ux-restructure-completion.json';history.write_text('{"pass":true}')
            failed_snapshot(root, 'latest_release_binding_stale')
            result=json.loads((runtime/'s6-readiness.json').read_text())
            self.assertFalse(result['local_checks_passed']);self.assertIn('checked_at',result)
            self.assertEqual(json.loads(history.read_text()),{'pass':True})
            self.assertEqual(list(runtime.glob('*.tmp')),[])

if __name__=='__main__': unittest.main()
