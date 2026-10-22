"""Offline human-setup tests: fake API/process/Docker/temp, no credentials."""
from contextlib import ExitStack
import json
from types import SimpleNamespace
import subprocess
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import setup_p84_codex_profile as setup
from pao_cli_runtime.codex_worker import BINARY_SHA256, VERSION
from pao_cli_runtime.profile_transport import ProfileAdmin
from pao_cli_runtime.docker_transport import ImagePin
from pao_cli_runtime.contracts import CliFailure


def immediate(coroutine):
    """All awaited I/O is AsyncMock: no real Windows event-loop/socket setup."""
    try:
        coroutine.send(None)
    except StopIteration as done:
        return done.value
    finally:
        coroutine.close()
    raise AssertionError('Offline test unexpectedly suspended on real I/O')


class ProfileSetupTests(unittest.TestCase):
    def setUp(self):
        self.wid, self.uid, self.cid, self.profile, self.device = [str(uuid4()) for _ in range(5)]
        self.config = {'image_id': 'sha256:' + 'a' * 64, 'binary_sha256': BINARY_SHA256,
                       'binary_version': VERSION, 'device_id': self.device}
        self.row = {'id': self.cid, 'profile_id': self.profile, 'workspace_id': self.wid,
                    'owner_id': self.uid, 'device_id': self.device, 'provider': 'codex_cli',
                    'model': 'synthetic-model', 'version': 2, 'scope': 'local_personal_self_only',
                    'credentials_stored_in_PAO': False, 'tools_enabled': False, 'activation_required': True}
        self.pin = {k: self.row[v] for k, v in (
            ('workspace_id', 'workspace_id'), ('actor_id', 'owner_id'), ('connection_id', 'id'),
            ('device_id', 'device_id'), ('profile_id', 'profile_id'))}
        self.admin = ProfileAdmin(ImagePin(self.config['image_id'], BINARY_SHA256, VERSION))

    def test_actual_authenticated_owner_required(self):
        api = MagicMock()
        api.call.side_effect = [{'id': self.uid}, {'id': self.wid, 'role': 'owner', 'name': 'Synthetic SME'}]
        selected = {'workspace_id': self.wid, 'current_owner_user_id': self.uid}
        self.assertEqual(setup.identity(api, selected), (self.wid, self.uid, 'Synthetic SME'))

    def test_selected_receipt_is_not_authority(self):
        api = MagicMock()
        api.call.return_value = {'id': str(uuid4())}
        with self.assertRaises(setup.SetupFailure):
            setup.identity(api, {'workspace_id': self.wid, 'current_owner_user_id': self.uid})
        self.assertEqual(api.call.call_count, 1)

    def test_removed_owner_refused(self):
        api = MagicMock()
        api.call.side_effect = [{'id': self.uid}, {'id': self.wid, 'role': 'viewer', 'name': 'Synthetic SME'}]
        with self.assertRaises(setup.SetupFailure):
            setup.identity(api, {'workspace_id': self.wid, 'current_owner_user_id': self.uid})

    def test_profile_scope_and_no_tool_authority(self):
        self.assertEqual(setup.checked_row(self.row, self.wid, self.uid, 'synthetic-model', self.config), self.row)
        for changed in ({'owner_id': str(uuid4())}, {'workspace_id': str(uuid4())}, {'device_id': str(uuid4())},
                        {'tools_enabled': True}, {'credentials_stored_in_PAO': True}, {'version': True}):
            with self.subTest(changed=changed), self.assertRaises(setup.SetupFailure):
                setup.checked_row({**self.row, **changed}, self.wid, self.uid, 'synthetic-model', self.config)

    def test_api_rejects_redirect_without_following(self):
        with self.assertRaises(setup.SetupFailure):
            setup.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid')

    def test_api_rejects_non_fixed_paths(self):
        api = setup.LocalAPI()
        api.opener = MagicMock()
        for path in ('https://other.invalid', '//other.invalid', '/v1/../secret', '/v1/x?token=bad', '/v1/x\n'):
            with self.subTest(path=path), self.assertRaises(setup.SetupFailure):
                api.call('GET', path)
        api.opener.open.assert_not_called()

    def test_untrusted_login_command_never_runs(self):
        with patch.object(setup.subprocess, 'run') as execute:
            with self.assertRaises(setup.SetupFailure):
                setup.official_login(self.row, self.config, ['powershell', 'untrusted'])
            execute.assert_not_called()

    def human_login(self, error=None):
        command = self.admin.login_command(self.pin)
        with ExitStack() as stack:
            temporary = stack.enter_context(patch.object(setup.tempfile, 'TemporaryDirectory'))
            temporary.return_value.__enter__.return_value = 'synthetic-temporary-not-created'
            profile = stack.enter_context(patch('pao_cli_runtime.docker_transport.DockerTransport.check_profile', new_callable=AsyncMock))
            cleanup = stack.enter_context(patch.object(setup, 'cleanup_login', new_callable=AsyncMock))
            stack.enter_context(patch.object(setup.asyncio, 'run', side_effect=immediate))
            execute = stack.enter_context(patch.object(setup.subprocess, 'run'))
            execute.return_value.returncode = 0
            execute.side_effect = error
            stack.enter_context(patch.dict(setup.os.environ, {'OPENAI_API_KEY': 'synthetic-do-not-inherit'}))
            if error:
                with self.assertRaises(type(error)):
                    setup.official_login(self.row, self.config, command)
            else:
                setup.official_login(self.row, self.config, command)
            profile.assert_awaited_once()
            cleanup.assert_awaited_once()
            return execute.call_args, profile.await_args.args[0]

    def test_login_uses_console_and_filtered_environment(self):
        args, _ = self.human_login()
        self.assertIs(args.kwargs['shell'], False)
        self.assertNotIn('stdout', args.kwargs)
        self.assertNotIn('capture_output', args.kwargs)
        self.assertNotIn('OPENAI_API_KEY', args.kwargs['env'])
        self.assertIn('--name', args.args[0])
        self.assertEqual(args.args[0][-2:], ['login', '--device-auth'])

    def test_login_passes_complete_runtime_pin_to_profile_guard(self):
        _, pin = self.human_login()
        self.assertEqual(pin.get('binary_sha256'), self.config['binary_sha256'])
        self.assertEqual(pin.get('binary_version'), self.config['binary_version'])
        self.assertEqual(pin.get('runtime_image_id'), self.config['image_id'])

    def test_actual_profile_guard_accepts_complete_pin_and_refuses_missing_fields(self):
        _, pin = self.human_login()
        volume = 'pao-cli-profile-' + self.profile.replace('-', '')
        labels = {'pao.cli.' + key: pin[key] for key in
                  ('workspace_id', 'actor_id', 'connection_id', 'device_id', 'profile_id')}
        volume_info = [{'Name': volume, 'Driver': 'local', 'Options': None, 'Labels': labels}]
        image_info = [{'Id': self.config['image_id'], 'Config': {'User': '65534:65534', 'Labels': {
            'pao.cli.version': VERSION, 'pao.cli.binary-sha256': BINARY_SHA256}}}]
        self.admin.transport.command = AsyncMock(side_effect=[json.dumps(volume_info).encode(),
                                                               json.dumps(image_info).encode()])
        self.assertEqual(immediate(self.admin.transport.check_profile(pin, {})), volume)
        self.assertEqual(self.admin.transport.command.await_count, 2)
        for name in ('binary_sha256', 'binary_version', 'runtime_image_id'):
            partial = {k: v for k, v in pin.items() if k != name}
            self.admin.transport.command = AsyncMock()
            with self.subTest(missing=name), self.assertRaises(CliFailure):
                immediate(self.admin.transport.check_profile(partial, {}))
            self.admin.transport.command.assert_not_awaited()

    def test_timeout_still_attempts_owned_cleanup(self):
        self.human_login(subprocess.TimeoutExpired('synthetic', 900))

    def test_cleanup_missing_owned_container_is_safe(self):
        self.admin.transport.command = AsyncMock(return_value=b'')
        immediate(setup.cleanup_login(self.admin, 'generated-name', 'operation', {}))
        self.assertEqual(self.admin.transport.command.await_count, 1)

    def test_cleanup_only_exact_id_label_and_image(self):
        cid = 'b' * 64
        info = {'Id': cid, 'Name': '/generated-name', 'Image': self.config['image_id'],
                'Config': {'Labels': {'pao.cli.login_operation_id': 'operation'}}}
        self.admin.transport.command = AsyncMock(side_effect=[cid.encode(), json.dumps([info]).encode(), b'', b''])
        immediate(setup.cleanup_login(self.admin, 'generated-name', 'operation', {}))
        self.assertEqual(self.admin.transport.command.await_args_list[2].args[0], ['rm', '--force', cid])

    def test_cleanup_wrong_owner_never_removes(self):
        cid = 'b' * 64
        info = {'Id': cid, 'Name': '/generated-name', 'Image': self.config['image_id'],
                'Config': {'Labels': {'pao.cli.login_operation_id': 'someone-else'}}}
        self.admin.transport.command = AsyncMock(side_effect=[cid.encode(), json.dumps([info]).encode()])
        with self.assertRaises(setup.SetupFailure):
            immediate(setup.cleanup_login(self.admin, 'generated-name', 'operation', {}))
        self.assertEqual(self.admin.transport.command.await_count, 2)


if __name__ == '__main__':
    unittest.main()
