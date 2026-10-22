"""Native PG transport command guards; no actual DB or subprocess in unit tests."""
import unittest
from unittest.mock import patch
from sqlalchemy.engine import make_url
from linux_local_restore import PgTools


class TransportTests(unittest.TestCase):
    def setup_transport(self, **changes):
        args=dict(root='/workspace',url=make_url('postgresql+asyncpg://pao:synthetic@127.0.0.1:5432/pao_test'),
            env={'PAO_LINUX_LOCAL_RESTORE':'1','PAO_S6_LINUX_RUN':'a'*32},populated=True,manifest=None,platform='linux')
        args.update(changes);return PgTools(**args)

    def test_primary_or_manifest_or_wrong_platform_denied(self):
        for changes in ({'platform':'win32'},{'manifest':'saved'},{'populated':False},{'root':'/app'},
            {'url':make_url('postgresql+asyncpg://pao:x@127.0.0.1:5432/pao_acos_local')},
            {'env':{'PAO_LINUX_LOCAL_RESTORE':'1','PAO_S6_LINUX_RUN':'invalid'}}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.setup_transport(**changes)

    def test_only_created_clone_can_be_restored_or_dropped(self):
        transport=self.setup_transport();name='pao_p7_restore_'+'b'*32
        with self.assertRaises(ValueError):transport('ignored','dropdb','-U','pao',name)
        with patch('linux_local_restore.subprocess.run') as run:
            transport('ignored','createdb','-U','pao',name)
            transport('-i','ignored','pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error')
            transport('ignored','dropdb','-U','pao',name)
            self.assertEqual(run.call_count,3)
            self.assertEqual(run.call_args.args[0],['dropdb','-U','pao',name])
        self.assertEqual(transport.created,set())

    def test_no_shell_or_primary_dump(self):
        transport=self.setup_transport()
        for command in (('ignored','sh','-c','anything'),('ignored','dropdb','-U','pao','pao_test'),
            ('ignored','pg_dump','-U','pao','-d','pao_acos_local','-Fc')):
            with self.subTest(command=command),self.assertRaises(ValueError):transport(*command)

    def test_failed_createdb_never_becomes_owned(self):
        import subprocess
        transport=self.setup_transport();name='pao_p7_restore_'+'c'*32
        with patch('linux_local_restore.subprocess.run',side_effect=subprocess.CalledProcessError(1,['createdb'])):
            with self.assertRaises(subprocess.CalledProcessError):transport('ignored','createdb','-U','pao',name)
        self.assertEqual(transport.created,set())


if __name__=='__main__':unittest.main()
