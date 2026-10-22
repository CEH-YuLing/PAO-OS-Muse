"""Offline foundation tests. No PAO settings, DB, provider binary or credentials."""
import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime import CliFailure, CliProvider, CliRequest, CliScope, Limits, FixtureTransport
from pao_cli_runtime.contracts import PROVIDERS, external_dispatch


def scope():
    return CliScope(*(str(uuid4()) for _ in range(5)))


def request(**overrides):
    return CliRequest(**{'provider': CliProvider.CODEX, 'scope': scope(), 'attempt_id': str(uuid4()),
                         'prompt': 'Xin chào PAO', **overrides})


async def allow(_scope):
    return True


def alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        # A zombie has terminated and cannot execute, but still has a PID.
        status = Path(f'/proc/{pid}/stat')
        return not status.exists() or status.read_text().split(') ', 1)[1][0] != 'Z'
    except ProcessLookupError:
        return False


class ContractTests(unittest.TestCase):
    def test_all_three_providers_are_prepared_not_live(self):
        self.assertEqual(len(PROVIDERS), 3)
        self.assertTrue(all(value['live_enabled'] is False for value in PROVIDERS.values()))
        for provider in CliProvider:
            with self.subTest(provider=provider), self.assertRaisesRegex(CliFailure, '^cli_external_disabled$'):
                external_dispatch(provider, enabled=True, command=['agy'], token='SECRET_SENTINEL')

    def test_invalid_ids_and_model(self):
        for invalid in ('', 'owner', str(uuid4()).upper(), None):
            with self.subTest(invalid=invalid), self.assertRaises(CliFailure):
                replace(scope(), actor_id=invalid)
        for model in ('', 'bad model', 'x\n', 'x\x00', 'x' * 121):
            with self.subTest(model=model), self.assertRaises(CliFailure):
                request(model=model)

    def test_request_and_limits_strict(self):
        for value in (float('nan'), float('inf'), True, 0, 121):
            with self.subTest(value=value), self.assertRaises(CliFailure):
                Limits(timeout_seconds=value)
        for value in (True, 63, 1048577, 128.0):
            with self.subTest(value=value), self.assertRaises(CliFailure):
                Limits(max_output_bytes=value)
        with self.assertRaises(CliFailure):
            Limits(max_output_bytes=128, max_line_bytes=256)
        with self.assertRaises(CliFailure):
            request(provider='codex_cli')
        with self.assertRaises(CliFailure):
            request(prompt='\ud800')

    def test_errors_and_repr_do_not_reflect_secrets(self):
        self.assertNotIn('SECRET_SENTINEL', repr(request(prompt='SECRET_SENTINEL')))
        self.assertEqual(str(CliFailure('SECRET_SENTINEL')), 'cli_internal_error')


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix='pao-p84-unit-')
        self.addCleanup(self.directory.cleanup)
        self.transport = FixtureTransport(self.directory.name)

    async def test_unicode_echo_for_all_three_descriptors(self):
        for provider in CliProvider:
            with self.subTest(provider=provider):
                value = await self.transport.run(request(provider=provider, prompt='Tiếng Việt: nhãn hàng 🐾\nDòng 2'), authorize=allow)
                self.assertEqual(value.text, 'Tiếng Việt: nhãn hàng 🐾\nDòng 2')
                self.assertIsNone(value.input_tokens)
                self.assertIsNone(value.output_tokens)
                self.assertFalse(value.provider_inference_verified)
                self.assertEqual(value.mode, 'offline_fixture')
                self.assertNotIn('Tiếng Việt', repr(value))

    async def test_reported_usage_is_not_subscription_cost(self):
        value = await self.transport.run(request(), authorize=allow, fixture='usage')
        self.assertEqual((value.input_tokens, value.output_tokens), (12, 4))
        self.assertFalse(value.provider_inference_verified)

    async def test_invalid_protocol_and_failure_matrix(self):
        cases = {'malformed': 'cli_protocol_invalid', 'stderr': 'cli_process_failed',
                 'incomplete': 'cli_incomplete', 'trailing': 'cli_protocol_invalid',
                 'false_success': 'cli_process_failed', 'bad_usage': 'cli_protocol_invalid',
                 'duplicate': 'cli_protocol_invalid', 'duplicate_keys': 'cli_protocol_invalid', 'flood': 'cli_output_limit',
                 'stderr_flood': 'cli_output_limit'}
        for mode, expected in cases.items():
            with self.subTest(mode=mode), self.assertRaises(CliFailure) as caught:
                await self.transport.run(request(), authorize=allow, fixture=mode)
            self.assertEqual(caught.exception.code, expected)
            self.assertNotIn('SECRET_SENTINEL', str(caught.exception))

    async def test_input_bounded_in_bytes_and_json_overhead(self):
        for prompt in ('á' * 40, '"' * 48):
            with self.subTest(prompt=prompt), self.assertRaisesRegex(CliFailure, 'cli_input_limit'):
                await self.transport.run(request(prompt=prompt, limits=Limits(max_input_bytes=64)), authorize=allow)

    async def test_access_denied_and_scope_not_implicitly_shared(self):
        selected = scope()

        async def only_selected(value):
            return value == selected

        await self.transport.run(request(scope=selected), authorize=only_selected)
        for changed in ('workspace_id', 'actor_id', 'connection_id', 'brand_id', 'device_id', 'profile_id'):
            with self.subTest(changed=changed), self.assertRaisesRegex(CliFailure, 'cli_access_denied'):
                await self.transport.run(request(scope=replace(selected, **{changed: str(uuid4())})), authorize=only_selected)

    async def test_access_checked_before_dispatch_and_each_delivery(self):
        calls = []
        delivered = []

        async def check(value):
            calls.append(value)
            return not delivered

        async def sink(text):
            delivered.append(text)

        with self.assertRaisesRegex(CliFailure, 'cli_access_denied'):
            await self.transport.run(request(), authorize=check, fixture='delay', on_delta=sink)
        self.assertEqual(delivered, ['first'])
        self.assertGreaterEqual(len(calls), 4)

    async def test_final_delivery_rechecks_access(self):
        checks = 0

        async def check(_):
            nonlocal checks
            checks += 1
            return checks < 4

        with self.assertRaisesRegex(CliFailure, 'cli_access_denied'):
            await self.transport.run(request(), authorize=check)

    async def test_authority_exception_is_sanitized(self):
        async def broken(_):
            raise ValueError('SECRET_SENTINEL')

        with self.assertRaisesRegex(CliFailure, '^cli_access_denied$'):
            await self.transport.run(request(), authorize=broken)

    async def test_initial_authority_timeout_is_bounded(self):
        async def blocked(_):
            await asyncio.sleep(60)

        with self.assertRaisesRegex(CliFailure, '^cli_timeout$'):
            await self.transport.run(request(limits=Limits(timeout_seconds=.1)), authorize=blocked)

    async def test_timeout_releases_profile_but_does_not_retry_attempt(self):
        value = request(limits=Limits(timeout_seconds=.15))
        with self.assertRaisesRegex(CliFailure, 'cli_timeout'):
            await self.transport.run(value, authorize=allow, fixture='sleep')
        with self.assertRaisesRegex(CliFailure, 'cli_attempt_already_dispatched'):
            await self.transport.run(value, authorize=allow)
        await self.transport.run(replace(value, attempt_id=str(uuid4()), limits=Limits()), authorize=allow)

    async def test_cancellation_releases_profile_and_cleans_folder(self):
        value = request()
        task = asyncio.create_task(self.transport.run(value, authorize=allow, fixture='sleep'))
        await asyncio.sleep(.15)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])
        await self.transport.run(replace(value, attempt_id=str(uuid4())), authorize=allow)

    async def test_same_profile_busy_even_in_another_workspace(self):
        value = request()
        task = asyncio.create_task(self.transport.run(value, authorize=allow, fixture='sleep'))
        try:
            await asyncio.sleep(.1)
            second = request(scope=replace(value.scope, workspace_id=str(uuid4()), connection_id=str(uuid4())))
            with self.assertRaisesRegex(CliFailure, 'cli_profile_busy'):
                await self.transport.run(second, authorize=allow)
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

    async def test_duplicate_submission_fenced_after_async_authorization(self):
        value = request()
        ready = asyncio.Event()
        reached = 0

        async def delayed(_):
            nonlocal reached
            reached += 1
            if reached == 2:
                ready.set()
            await ready.wait()
            return True

        results = await asyncio.gather(*(self.transport.run(value, authorize=delayed) for _ in range(2)), return_exceptions=True)
        self.assertEqual(sum(isinstance(result, CliFailure) and result.code == 'cli_attempt_already_dispatched' for result in results), 1)
        self.assertEqual(sum(not isinstance(result, BaseException) for result in results), 1)

    async def test_parent_environment_not_inherited_or_mutated(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'SECRET_SENTINEL', 'DATABASE_URL': 'SECRET_SENTINEL',
                                     'HTTP_PROXY': 'SECRET_SENTINEL', 'PYTHONPATH': 'SECRET_SENTINEL'}):
            before = dict(os.environ)
            value = await self.transport.run(request(), authorize=allow, fixture='env')
            keys = set(json.loads(value.text))
            self.assertFalse(keys & {'ANTHROPIC_API_KEY', 'DATABASE_URL', 'HTTP_PROXY', 'PYTHONPATH', 'PATH'})
            self.assertEqual(dict(os.environ), before)

    async def test_parent_exit_cleans_orphan_descendant_and_reports_incomplete(self):
        pids = []

        async def child(text):
            pids.append(int(text))

        with self.assertRaisesRegex(CliFailure, 'cli_incomplete'):
            await self.transport.run(request(limits=Limits(timeout_seconds=4)), authorize=allow, fixture='tree', on_delta=child)
        self.assertEqual(len(pids), 1)
        for _ in range(40):
            if not alive(pids[0]):
                break
            await asyncio.sleep(.025)
        self.assertFalse(alive(pids[0]))

    async def test_invalid_fixture_cannot_supply_command(self):
        with self.assertRaisesRegex(CliFailure, 'cli_fixture_invalid'):
            await self.transport.run(request(), authorize=allow, fixture='agy --dangerously-skip-permissions')

    async def test_attempt_capacity_fails_closed(self):
        transport = FixtureTransport(self.directory.name, max_attempts=1)
        await transport.run(request(), authorize=allow)
        with self.assertRaisesRegex(CliFailure, 'cli_capacity'):
            await transport.run(request(), authorize=allow)

    async def test_active_process_capacity_across_profiles(self):
        transport = FixtureTransport(self.directory.name, max_active=1)
        task = asyncio.create_task(transport.run(request(), authorize=allow, fixture='sleep'))
        try:
            await asyncio.sleep(.1)
            with self.assertRaisesRegex(CliFailure, 'cli_capacity'):
                await transport.run(request(), authorize=allow)
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

    async def test_prompt_is_data_not_shell_or_argv(self):
        prompt = '$(Get-Content .env); & whoami | echo "not a command"\n--dangerously-skip-permissions'
        result = await self.transport.run(request(prompt=prompt), authorize=allow)
        self.assertEqual(result.text, prompt)

    async def test_cancel_during_spawn_reaps_the_created_process(self):
        real_spawn = asyncio.create_subprocess_exec
        created = asyncio.Event()
        release = asyncio.Event()
        pids = []

        async def slow_spawn(*args, **kwargs):
            process = await real_spawn(*args, **kwargs)
            pids.append(process.pid)
            created.set()
            await release.wait()
            return process

        with patch('pao_cli_runtime.transport.asyncio.create_subprocess_exec', side_effect=slow_spawn):
            task = asyncio.create_task(self.transport.run(request(), authorize=allow))
            await asyncio.wait_for(created.wait(), 3)
            task.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(len(pids), 1)
        self.assertFalse(alive(pids[0]))

    def test_reparse_runtime_path_rejected_before_resolve(self):
        import types
        original = Path.lstat
        root = Path(self.directory.name)

        def reparse(path, *args, **kwargs):
            if path == root:
                return types.SimpleNamespace(st_mode=0o040700, st_file_attributes=0x400)
            return original(path, *args, **kwargs)

        with patch.object(Path, 'lstat', reparse), self.assertRaisesRegex(CliFailure, 'cli_runtime_path_invalid'):
            FixtureTransport(root)

    def test_missing_or_relative_runtime_directory_is_rejected(self):
        for path in ('relative', str(Path(self.directory.name) / 'missing')):
            with self.subTest(path=path), self.assertRaisesRegex(CliFailure, 'cli_runtime_path_invalid'):
                FixtureTransport(path)


if __name__ == '__main__':
    # Windows asyncio uses a localhost socketpair. Allow that internal pipe,
    # but make a mistaken provider/network call fail even outside the sandbox.
    import ipaddress

    def offline_network(event, args):
        if event in ('socket.connect', 'socket.bind'):
            address = args[1]
            if isinstance(address, tuple):
                try:
                    if not ipaddress.ip_address(address[0]).is_loopback:
                        raise ValueError()
                except ValueError:
                    raise RuntimeError('p84_external_network_denied') from None
        if event == 'socket.getaddrinfo' and args[0] not in ('localhost', '127.0.0.1', '::1'):
            raise RuntimeError('p84_external_network_denied')

    sys.addaudithook(offline_network)
    unittest.main(verbosity=2)
