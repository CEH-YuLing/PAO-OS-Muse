"""Offline startup guard tests. No database, Docker, provider or primary mutation."""
import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch

from check_acos_startup_schema import check, local_url, validate_revision


class StartupSchemaTests(unittest.TestCase):
    def test_reviewed_schema_is_read_only_and_no_migration(self):
        value = validate_revision(['0077'], '0077')
        self.assertTrue(value['pass'])
        self.assertTrue(value['read_only'])
        self.assertFalse(value['migration_executed'])

    def test_mismatched_empty_and_multiple_heads_are_denied(self):
        for rows in ([], ['0074'], ['0075'], ['0076'], ['0075', '0077'], ['0077', '0077']):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'acos_schema_release_required'):
                validate_revision(rows, '0077')

    def test_no_symbolic_head_or_shell_argument(self):
        for pin in ('head', 'heads', 'base', '75', '', '0075;echo', None, 75):
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, 'explicit_reviewed_revision_required'):
                validate_revision([pin], pin)

    def test_only_exact_local_primary_allowed(self):
        good = 'postgresql+asyncpg://pao:synthetic@127.0.0.1:15432/pao_acos_local'
        self.assertEqual(local_url(good).database, 'pao_acos_local')
        for raw in (good.replace('15432', '5432'), good.replace('127.0.0.1', 'remote.example'),
                    good.replace('pao_acos_local', 'pao_test'), good.replace('pao:synthetic', 'admin:synthetic')):
            with self.assertRaisesRegex(ValueError, 'scope_denied'):
                local_url(raw)

    def test_invalid_pin_never_opens_a_database(self):
        with patch('sqlalchemy.ext.asyncio.create_async_engine') as make:
            with self.assertRaises(ValueError):
                asyncio.run(check('invalid', 'head'))
            make.assert_not_called()

    def test_both_launchers_have_no_alembic_upgrade(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('start_acos_local.ps1', 'start_local.ps1', 'restart_acos_backend.ps1'):
            source = (root/'scripts'/name).read_text(encoding='utf-8')
            self.assertNotIn('-m alembic upgrade', source)
            self.assertIn('check_acos_startup_schema.py --expected 0077', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
