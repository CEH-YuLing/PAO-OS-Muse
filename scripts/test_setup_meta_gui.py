"""Isolated tests: fake credentials only; never touch the real .env."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from setup_meta_gui import save_configuration, CALLBACK


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / '.env'
        self.key = Fernet.generate_key().decode()
        self.path.write_text('OTHER=keep\nINTEGRATION_ENCRYPTION_KEY=' + self.key + '\n'
                             'export META_WRITE_ENABLED=true\nMETA_APP_SECRET=old-test-value\n')

    def save(self, **overrides):
        values = dict(path=self.path, app_id='123456', version='v26.0',
                      secret='fake-test-value-not-real', callback=CALLBACK, rotated=True)
        values.update(overrides)
        save_configuration(**values)

    def test_preserves_key_and_other_settings_forces_safe_flags(self):
        self.save()
        values = dotenv_values(self.path)
        self.assertEqual(values['INTEGRATION_ENCRYPTION_KEY'], self.key)
        self.assertEqual(values['OTHER'], 'keep')
        self.assertEqual(values['META_ENABLED'], 'true')
        for name in ('META_WRITE_ENABLED', 'META_AUTOPILOT_ENABLED', 'ADS_AUTOPILOT_GLOBAL_ENABLED'):
            self.assertEqual(values[name], 'false')
        self.assertEqual(list(self.path.parent.glob('.meta-config-*')), [])

    def test_invalid_input_and_no_rotation_leave_file_unchanged(self):
        original = self.path.read_bytes()
        for overrides in (dict(rotated=False), dict(secret=''), dict(secret='invalid\nsecret-value'),
                          dict(app_id='bad'), dict(version='26'), dict(callback='https://example.com/callback')):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.save(**overrides)
            self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_existing_key_never_rotated(self):
        self.path.write_text('INTEGRATION_ENCRYPTION_KEY=broken\n')
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.save()
        self.assertEqual(self.path.read_bytes(), original)

    def test_failed_replace_keeps_original_and_cleans_temp(self):
        original = self.path.read_bytes()
        with patch('setup_meta_gui.os.replace', side_effect=OSError('test failure')):
            with self.assertRaises(OSError):
                self.save()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob('.meta-config-*')), [])

    def test_generates_valid_key_only_when_absent(self):
        self.path.write_text('OTHER=keep\n')
        self.save()
        Fernet(dotenv_values(self.path)['INTEGRATION_ENCRYPTION_KEY'].encode())


if __name__ == '__main__':
    unittest.main()
