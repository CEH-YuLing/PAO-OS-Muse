"""Pure profile admission tests; no Docker/DB, no weakening Windows guard."""
from pathlib import Path
import unittest
from sqlalchemy.engine import make_url
from ci_restore_profile import service_container


class RestoreProfileTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.url = make_url('postgresql+asyncpg://pao:synthetic@127.0.0.1:5432/pao_test')
        self.env = {'PAO_CI_RESTORE': '1', 'GITHUB_ACTIONS': 'true',
            'GITHUB_WORKSPACE': str(self.root), 'PAO_CI_RESTORE_CONTAINER': 'a'*64}

    def check(self, **changes):
        values = dict(root=self.root, url=self.url, env=self.env,
            populated=True, manifest=None, platform='linux')
        values.update(changes)
        return service_container(**values)

    def test_only_owned_linux_service_and_test_database_admitted(self):
        self.assertEqual(self.check(), 'a'*64)

    def test_windows_manifest_and_roundtrip_never_use_ci_override(self):
        for changes in ({'platform': 'win32'}, {'manifest': 'checkpoint.json'}, {'populated': False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(**changes)

    def test_primary_port_host_user_and_driver_cannot_be_relaxed(self):
        for changes in ({'database': 'pao_acos_local'}, {'port': 15432}, {'host': 'remote.example'},
                        {'username': 'postgres'}, {'drivername': 'postgresql'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(url=self.url.set(**changes))

    def test_missing_runner_identity_workspace_or_shell_container_denied(self):
        for field, value in [('PAO_CI_RESTORE', ''), ('GITHUB_ACTIONS', 'false'),
            ('GITHUB_WORKSPACE', ''), ('GITHUB_WORKSPACE', str(self.root/'not-this-repo')),
            ('PAO_CI_RESTORE_CONTAINER', 'pao-acos-local-postgres-1'),
            ('PAO_CI_RESTORE_CONTAINER', 'a'*64+'; echo invalid')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(env={**self.env, field: value})


if __name__ == '__main__':
    unittest.main()
