"""Offline safety checks; temporary files only, never primary/Redis/provider calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from gd00_baseline import (checkpoint, extract_source, owned_path, read_private,
                           scan_bytes, TOKEN_PATTERNS, write_new)
from gd00_clone_reader import clone_url, network_guard


class GD00SafetyTests(unittest.TestCase):
    def test_existing_contract_metadata_preflight_without_running_tests(self):
        import run_p0_checks
        with patch.object(run_p0_checks,'call') as execute:
            run_p0_checks.main(preflight_only=True)
            execute.assert_not_called()

    def test_path_escape_and_dotdot_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)/'owned'; base.mkdir()
            for path in (base.parent/'outside', base/'..'/'outside'):
                with self.assertRaisesRegex(ValueError, 'outside_scope'): owned_path(path, base)

    def test_child_network_rejects_provider_and_primary_api(self):
        for address in (('api.openai.com',443),('127.0.0.1',8100),('127.0.0.1',3200),('localhost',15432)):
            with self.assertRaisesRegex(RuntimeError,'external_network_denied'):
                network_guard('socket.connect',(None,address))
        for address in (('127.0.0.1',15432),('127.0.0.1',16379)):
            network_guard('socket.connect',(None,address))

    def test_child_may_not_launch_workers_or_cli(self):
        for event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):
            with self.assertRaisesRegex(RuntimeError,'child_process_denied'): network_guard(event,())

    def test_reader_refuses_primary_test_other_host_or_name(self):
        base = 'postgresql+asyncpg://pao:synthetic@127.0.0.1:15432/'
        clone_url(base+'pao_s03_restore_'+'a'*32)
        for name in ('pao_acos_local','pao_test','pao_s03_restore_existing','pao_s03_restore_'+'a'*31):
            with self.assertRaisesRegex(ValueError,'owned_clone_required'): clone_url(base+name)
        with self.assertRaises(ValueError): clone_url((base+'pao_s03_restore_'+'a'*32).replace('127.0.0.1','remote'))

    def make_checkpoint(self, base):
        folder=base/'.runtime/checkpoints/synthetic'; folder.mkdir(parents=True)
        archive=folder/'source.zip'; dump=base/'.runtime/synthetic.dump'
        with ZipFile(archive,'w') as zipfile: zipfile.writestr('apps/synthetic.py','safe')
        dump.write_bytes(b'synthetic-dump')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        manifest={'source':{'path':str(archive),'sha256':sha(archive),
            'files':{'apps/synthetic.py':hashlib.sha256(b'safe').hexdigest()}},
            'database':{'backup':str(dump),'sha256':sha(dump)}}
        path=folder/'manifest.json'; write_new(path,manifest)
        return path, archive, dump, manifest

    def test_checkpoint_and_extracted_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,archive,_,manifest=self.make_checkpoint(root)
            self.assertEqual(checkpoint(path,root)[0],manifest)
            target=root/'restored'; extract_source(archive,manifest['source']['files'],target)
            self.assertEqual((target/'apps/synthetic.py').read_bytes(),b'safe')
            self.assertFalse((target/'.env').exists())
            with self.assertRaisesRegex(ValueError,'target_exists'): extract_source(archive,manifest['source']['files'],target)

    def test_dump_tampering_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,_,dump,_=self.make_checkpoint(root)
            dump.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash_mismatch'):checkpoint(path,root)

    def test_source_archive_tampering_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,archive,_,_=self.make_checkpoint(root)
            archive.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash_mismatch'):checkpoint(path,root)

    def test_unsafe_zip_member_denied_without_extracting(self):
        for name in ('../outside.py','/absolute.py','C:/absolute.py','apps\\unsafe.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base=Path(directory); archive=base/'bad.zip'
                with ZipFile(archive,'w') as saved:saved.writestr(name,b'safe')
                with self.assertRaises(ValueError):
                    extract_source(archive,{name:hashlib.sha256(b'safe').hexdigest()},base/'target')

    def test_scanner_records_fingerprint_not_secret_value(self):
        value=b'synthetic-gd00-sensitive-value-only'
        result=scan_bytes(value, 'synthetic', {'SYNTHETIC_SECRET':value})
        self.assertEqual(result,[{'location':'synthetic','rule':'configured_value','field':'SYNTHETIC_SECRET'}])
        self.assertNotIn(value.decode(),json.dumps(result))
        marker=b'-----BEGIN '+b'RSA PRIVATE KEY-----'
        found=scan_bytes(marker,'synthetic',{})
        self.assertEqual(found[0]['match_sha256'],hashlib.sha256(marker).hexdigest())
        self.assertNotIn(marker.decode(),json.dumps(found))

    def test_private_missing_env_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);write_new(base/'manifest.json',{'format':'windows-dpapi-current-user-v1','files':[]})
            with self.assertRaisesRegex(ValueError,'env_missing'):read_private(base)

    def test_private_hash_mismatch_precedes_decryption(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);(base/'0.dpapi').write_bytes(b'tampered')
            write_new(base/'manifest.json',{'format':'windows-dpapi-current-user-v1','files':[
                {'source':'.env','sealed':'0.dpapi','sha256':'0'*64,'original_sha256':'0'*64}]})
            with patch('pao_mcp.profile.crypt') as crypt:
                with self.assertRaisesRegex(ValueError,'hash_mismatch'):read_private(base)
                crypt.assert_not_called()

    def test_private_arbitrary_original_path_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);write_new(base/'manifest.json',{'format':'windows-dpapi-current-user-v1',
                'files':[{'source':'../../outside','sealed':'0.dpapi'}]})
            with self.assertRaisesRegex(ValueError,'source_denied'):read_private(base)

    def test_evidence_never_overwrites_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'receipt.json';write_new(path,{'original':True})
            with self.assertRaises(FileExistsError):write_new(path,{'changed':True})
            self.assertEqual(json.loads(path.read_text()),{'original':True})


if __name__=='__main__':unittest.main(verbosity=2)
