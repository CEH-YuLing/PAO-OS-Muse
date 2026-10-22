"""Offline Temporal cache selection tests; no CLI download or server startup."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/api/tests'))
from temporal_fixture import cached_binary


class TemporalFixtureTests(unittest.TestCase):
    def make(self, root, suffix, magic):
        directory = Path(root) / '.runtime/p62-temporal-fixture'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ('temporal-sdk-python-1.33.0' + suffix)
        path.write_bytes(magic)
        return path

    def test_missing_does_not_download(self):
        with TemporaryDirectory() as root, self.assertRaisesRegex(ValueError, 'cache_missing'):
            cached_binary(root, 'linux')

    def test_windows_uses_pe_not_elf(self):
        with TemporaryDirectory() as root:
            path = self.make(root, '.exe', b'MZtest')
            self.make(root, '', b'\x7fELFtest')
            self.assertEqual(cached_binary(root, 'win32'), str(path))
            path.write_bytes(b'\x7fELFtest')
            with self.assertRaisesRegex(ValueError, 'wrong_platform'):
                cached_binary(root, 'win32')

    def test_linux_requires_executable_elf(self):
        with TemporaryDirectory() as root:
            path = self.make(root, '', b'\x7fELFtest')
            self.make(root, '.exe', b'MZtest')
            with patch('temporal_fixture.os.access', return_value=True):
                self.assertEqual(cached_binary(root, 'linux'), str(path))
            with patch('temporal_fixture.os.access', return_value=False):
                with self.assertRaisesRegex(ValueError, 'not_executable'):
                    cached_binary(root, 'linux')
            path.write_bytes(b'MZtest')
            with self.assertRaisesRegex(ValueError, 'wrong_platform'):
                cached_binary(root, 'linux')

    def test_other_platform_is_not_silently_supported(self):
        with TemporaryDirectory() as root, self.assertRaisesRegex(ValueError, 'unsupported'):
            cached_binary(root, 'darwin')


if __name__ == '__main__':
    unittest.main()
