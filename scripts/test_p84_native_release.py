"""Pure offline release-plan guards; no database, Docker, provider or writes."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree
import prepare_p84_native_release as release


class ReleasePlanTests(unittest.TestCase):
    def receipt(self, **changes):
        value = dict(pass_=True, full_backend_regression=True,
                     primary_source_env_schema_unchanged=True, candidate_source_unchanged=True,
                     tests=2343, failures=0, errors=0, skipped=0,
                     candidate_schema='0072', provider_calls=0, primary_migrated=False,
                     candidate_source={'x': 'hash'})
        value['pass'] = value.pop('pass_')
        return {**value, **changes}

    def verify(self, receipt, tests=2343):
        xml = ElementTree.Element('testsuites')
        ElementTree.SubElement(xml, 'testsuite', tests=str(tests), failures='0', errors='0', skipped='0')
        folder = release.ROOT / '.runtime' / ('p84-native-tests-' + 'a' * 32)
        with patch.object(release, 'unlinked', side_effect=lambda p, r: p), \
             patch.object(Path, 'read_text', return_value=json.dumps(receipt)), \
             patch.object(release.ElementTree, 'parse', return_value=ElementTree.ElementTree(xml)):
            return release.verified_full(folder, {'x': 'hash'})

    def test_complete_full_matches_junit(self):
        self.assertEqual(self.verify(self.receipt())['tests'], 2343)

    def test_failure_or_skip_is_not_full_pass(self):
        for change in ({'pass': False}, {'failures': 1}, {'skipped': 1}, {'full_backend_regression': False}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify(self.receipt(**change))

    def test_stale_source_or_primary_mutation_refused(self):
        for change in ({'candidate_source': {'x': 'different'}}, {'primary_migrated': True},
                       {'primary_source_env_schema_unchanged': False}, {'provider_calls': 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify(self.receipt(**change))

    def test_junit_disagreement_refused(self):
        with self.assertRaises(ValueError):
            self.verify(self.receipt(), tests=2342)

    def plan(self, primary, baseline):
        name = 'apps/api/pao/app.py'
        with patch.object(release, 'TARGETS', (name,)), \
             patch.object(release, 'unlinked', side_effect=lambda p, r: p), \
             patch.object(Path, 'is_file', return_value=True), \
             patch.object(release, 'digest', side_effect=lambda p: 'after' if p.is_relative_to(release.CANDIDATE) else primary):
            return release.changes_for(release.ROOT, release.CANDIDATE, {name: baseline}, {name: 'after'})

    def test_source_preimage_preserved(self):
        result = self.plan('before', 'before')
        self.assertEqual(result['apps/api/pao/app.py'], {'before': 'before', 'after': 'after'})

    def test_overlapping_user_change_refused(self):
        with self.assertRaisesRegex(ValueError, 'preserve_overlapping_change'):
            self.plan('user-edit', 'before')

    def test_targets_exclude_environment_frontend_and_stale_docs(self):
        self.assertEqual(len(release.TARGETS), len(set(release.TARGETS)))
        self.assertFalse(any(n.startswith(('.env', '.runtime/', 'docs/', 'apps/web/')) for n in release.TARGETS))
        self.assertEqual([n for n in release.TARGETS if n.startswith('apps/api/migrations/')],
                         ['apps/api/migrations/versions/0072_cli_model_connections.py'])

    def test_unreviewed_addition_or_deletion_not_qualified(self):
        library = {'packages/cli-runtime/pao_cli_runtime/__init__.py': 'library'}
        baseline = {**library, 'apps/api/pao/app.py': 'old'}
        tested = {**baseline, 'apps/api/pao/app.py': 'new'}
        release.validate_scope(baseline, tested, baseline)
        for changed in ({**tested, 'apps/api/pao/unreviewed.py': 'extra'}, library):
            with self.assertRaises(ValueError):
                release.validate_scope(baseline, changed, baseline)

    def test_unrelated_primary_api_or_extra_host_library_blocks_rollout(self):
        baseline = {'apps/api/pao/app.py': 'old', 'packages/cli-runtime/pao_cli_runtime/__init__.py': 'library'}
        tested = {**baseline, 'apps/api/pao/app.py': 'new'}
        for changed in ({**baseline, 'apps/api/pao/user_edit.py': 'preserve'},
                        {**baseline, 'packages/cli-runtime/pao_cli_runtime/extra.py': 'extra'}):
            with self.assertRaises(ValueError):
                release.validate_scope(baseline, tested, changed)

    def test_frontend_contract_requires_matching_tested_inputs(self):
        folder = release.ROOT / '.runtime' / ('p84-frontend-' + 'b' * 32)
        primary = {'apps/web/app/page.tsx': 'web', 'package.json': 'npm', 'package-lock.json': 'lock',
                   'packages/contracts/openapi.json': 'api', 'packages/contracts/schema.d.ts': 'old'}
        built = {**primary, 'packages/contracts/schema.d.ts': 'derived'}
        proof = {'pass': True, 'provider_calls': 0, 'primary_frontend_changed': False,
                 'candidate_source_changed': False, 'stages': ['contracts', 'node', 'typegen', 'typecheck', 'build']}
        with patch.object(release, 'unlinked', side_effect=lambda p, r: p), \
             patch.object(Path, 'read_text', return_value=json.dumps(proof)), \
             patch.object(release, 'entries', return_value=built):
            result = release.frontend_contract(folder, primary, primary, primary)
            self.assertEqual((result['before'], result['after']), ('old', 'derived'))
            for changed in ({**built, 'packages/contracts/openapi.json': 'different'},
                            {**built, 'apps/web/app/page.tsx': 'edited'}):
                with patch.object(release, 'entries', return_value=changed), self.assertRaises(ValueError):
                    release.frontend_contract(folder, primary, primary, primary)

    def test_frontend_partial_pipeline_not_accepted(self):
        folder = release.ROOT / '.runtime' / ('p84-frontend-' + 'b' * 32)
        proof = {'pass': True, 'provider_calls': 0, 'primary_frontend_changed': False,
                 'candidate_source_changed': False, 'stages': ['contracts', 'node']}
        with patch.object(release, 'unlinked', side_effect=lambda p, r: p), \
             patch.object(Path, 'read_text', return_value=json.dumps(proof)), self.assertRaises(ValueError):
            release.frontend_contract(folder, {}, {}, {})


if __name__ == '__main__':
    unittest.main()
