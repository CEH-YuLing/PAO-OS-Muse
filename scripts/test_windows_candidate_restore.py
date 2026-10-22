"""Pure scope/command guards with a fake Docker process; never touch a DB."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from windows_candidate_restore import EXPECTED, PgTools


class CandidateRestoreTests(unittest.TestCase):
    def setUp(self):
        self.url = make_url('postgresql+asyncpg://pao:synthetic@127.0.0.1:15432/pao_test')
        self.env = {'PAO_WINDOWS_CANDIDATE_RESTORE': '1', 'PAO_ROOT': str(EXPECTED),
                    'PAO_WINDOWS_CANDIDATE_PG_CONTAINER': 'a' * 64}

    def profile(self, **changes):
        values = dict(root=EXPECTED, url=self.url, env=self.env, populated=True, manifest=None, platform='win32')
        values.update(changes)
        return PgTools(**values)

    def test_exact_candidate_only(self):
        self.assertEqual(self.profile().container, 'a' * 64)
        for root in ('F:/PAO-ACOS', 'F:/PAO-BOS Backup 001', str(EXPECTED) + '/other'):
            with self.subTest(root=root), self.assertRaises(ValueError):
                self.profile(root=root)

    def test_primary_remote_port_user_and_driver_denied(self):
        for change in ({'database': 'pao_acos_local'}, {'host': 'remote.example'}, {'port': 5432},
                       {'username': 'postgres'}, {'drivername': 'postgresql'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.profile(url=self.url.set(**change))

    def test_no_rollout_or_other_platform(self):
        for change in ({'platform': 'linux'}, {'manifest': 'checkpoint.json'}, {'populated': False}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.profile(**change)

    def test_explicit_environment_and_container_required(self):
        for field, value in (('PAO_ROOT', 'F:/PAO-ACOS'), ('PAO_WINDOWS_CANDIDATE_RESTORE', ''),
            ('PAO_WINDOWS_CANDIDATE_PG_CONTAINER', 'named-container'), ('PAO_CI_RESTORE', '1'),
            ('PAO_LINUX_LOCAL_RESTORE', '1')):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.profile(env={**self.env, field: value})

    def test_primary_dump_and_unowned_drop_are_not_commands(self):
        tools = self.profile()
        for command in (('pg_dump', '-U', 'pao', '-d', 'pao_acos_local', '-Fc'),
                        ('dropdb', '-U', 'pao', 'pao_p7_restore_' + 'b' * 32),
                        ('dropdb', '-U', 'pao', '--force'), ('psql', '-c', 'DROP DATABASE anything')):
            with self.subTest(command=command), self.assertRaises(ValueError):
                tools('ignored', *command)

    def test_only_created_clone_can_restore_and_drop(self):
        tools = self.profile()
        name = 'pao_p7_restore_' + 'b' * 32
        with patch('windows_candidate_restore.subprocess.run') as run, patch('windows_candidate_restore.tempfile.TemporaryDirectory') as temp:
            temp.return_value.__enter__.return_value = 'synthetic-unit-config-no-files'
            tools('ignored', 'createdb', '-U', 'pao', name)
            tools('-i', 'ignored', 'pg_restore', '-U', 'pao', '-d', name, '--no-owner', '--exit-on-error')
            tools('ignored', 'dropdb', '-U', 'pao', name)
            self.assertEqual(tools.created, set())
            self.assertTrue(all('a' * 64 in call.args[0] for call in run.call_args_list))
            self.assertNotIn('OPENAI_API_KEY', run.call_args.kwargs['env'])
        with self.assertRaises(ValueError):
            tools('ignored', 'dropdb', '-U', 'pao', name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
