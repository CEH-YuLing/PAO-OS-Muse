"""Offline transport source identity tests, no subprocess/provider/DB."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime import source_pin
from pao_cli_runtime.contracts import CliFailure


class SourcePinTests(unittest.TestCase):
    def test_installed_source_has_stable_sha256(self):
        value = source_pin.library_digest()
        self.assertRegex(value, r'^[0-9a-f]{64}$')
        self.assertEqual(value, source_pin.library_digest())

    def test_changes_additions_and_removal_are_not_silent(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / '__init__.py').write_bytes(b'')
            path = folder / 'transport.py'
            path.write_bytes(b'original\r\n')
            with patch.object(source_pin, 'PACKAGE', folder):
                original = source_pin.library_digest()
                path.write_bytes(b'original\n')
                self.assertNotEqual(original, source_pin.library_digest())
                changed = source_pin.library_digest()
                extra = folder / 'extra.py'
                extra.write_bytes(b'new module')
                self.assertNotEqual(changed, source_pin.library_digest())
                extra.unlink()
                self.assertEqual(changed, source_pin.library_digest())

    def test_missing_package_is_denied(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(source_pin, 'PACKAGE', Path(temp)):
            with self.assertRaisesRegex(CliFailure, '^cli_binary_changed$'):
                source_pin.library_digest()


if __name__ == '__main__':
    unittest.main(verbosity=2)
