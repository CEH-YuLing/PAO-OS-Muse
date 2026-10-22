"""Pure offline tests: no database, provider, secret, or primary mutation."""
from copy import deepcopy
import unittest
from check_s6_readiness import assess

BINDING = {'policy': 'exact-backend-source-v1', 'sha256': 'a'*64}


def evidence():
    return ({'pass': True, 'revision': '0070', 'operations': 382, 'physical_tables': 149,
        'read_only_replays': 3, 'binding': BINDING, 'business_hashes_unchanged': True,
        'provider_calls': False},
        {'pass': True, 'binding': BINDING, 'binding_unchanged': True,
         'tests': 2224, 'failures': 0, 'errors': 0, 'skipped': 0},
        {'endpoints': {'api_health': 200, 'api_ready': 200, 'web': 200},
         'operations': {'worker': {'healthy': True}}})


class ReadinessTests(unittest.TestCase):
    def test_local_green_never_accepts_real_business_or_production(self):
        result = assess(*evidence(), BINDING)
        self.assertTrue(result['local_checks_passed'])
        self.assertFalse(result['s6_accepted'])
        self.assertFalse(result['production_accepted'])
        self.assertEqual(sum(g['state']=='external_pending' for g in result['gates']), 5)

    def test_empty_evidence_fails_closed(self):
        self.assertFalse(assess({}, {}, {}, BINDING)['local_checks_passed'])

    def test_stale_binding_or_old_contract_or_changed_rows_is_not_accepted(self):
        for field, value in [('binding', {}), ('revision', '0065'), ('operations', 353),
                             ('physical_tables', 136), ('read_only_replays', 2),
                             ('business_hashes_unchanged', False), ('pass', 'true'),
                             ('provider_calls', True)]:
            with self.subTest(field=field):
                live, regression, health = deepcopy(evidence()); live[field] = value
                self.assertFalse(assess(live, regression, health, BINDING)['local_checks_passed'])

    def test_regression_missing_failures_skips_or_fake_boolean_denied(self):
        for field, value in [('binding', {}), ('binding_unchanged', False), ('tests', True),
                             ('tests', 2223), ('failures', 1), ('errors', 1), ('skipped', 1),
                             ('skipped', False), ('pass', 'true')]:
            with self.subTest(field=field, value=value):
                live, regression, health = deepcopy(evidence()); regression[field] = value
                self.assertFalse(assess(live, regression, health, BINDING)['local_checks_passed'])

    def test_dead_worker_or_incomplete_endpoint_is_not_provider_health(self):
        for health in ({}, {'endpoints': {'api_health': 200}},
                       {'endpoints': {'api_health': 200, 'api_ready': 200, 'web': 200},
                        'operations': {'worker': {'healthy': 'true'}}}):
            live, regression, _ = evidence()
            self.assertFalse(assess(live, regression, health, BINDING)['local_checks_passed'])

    def test_injected_acceptance_claims_do_not_close_external_gates(self):
        live, regression, health = evidence()
        live.update(production_accepted=True, s6_accepted=True, linux_ci=True)
        result = assess(live, regression, health, BINDING)
        self.assertFalse(result['s6_accepted'])
        pending = {g['id']: g['state'] for g in result['gates'][3:]}
        self.assertEqual(sum(v == 'external_pending' for v in pending.values()), 5)
        self.assertEqual(pending['s6_2_identity_lifecycle'], 'implementation_pending')
        self.assertEqual(pending['s6_2_data_lifecycle'], 'implementation_pending')


if __name__ == '__main__':
    unittest.main()
