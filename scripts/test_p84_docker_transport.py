"""Docker transport contract tests using fake daemon/processes, no real Docker/auth."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.contracts import CliFailure, Limits
from pao_cli_runtime.codex_catalog import text_catalog
from pao_cli_runtime.codex_worker import BINARY_SHA256, VERSION
from pao_cli_runtime.docker_transport import DockerTransport, ImagePin


def source():
    return {**{k: str(uuid4()) for k in ('workspace_id','actor_id','connection_id','device_id','profile_id')},
            'binary_sha256': BINARY_SHA256, 'binary_version': VERSION, 'model': 'synthetic-model',
            'runtime_image_id': 'sha256:'+'a'*64}


def output(tool=False):
    events = [{'type':'thread.started','thread_id':str(uuid4())}, {'type':'turn.started'},
              {'type':'item.completed','item':{'id':'item_0','type':'command_execution' if tool else 'agent_message','text':'Xin chào'}},
              {'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':3}}]
    return b''.join(json.dumps(e, ensure_ascii=False).encode() + b'\n' for e in events)


class Reader:
    def __init__(self, data=b'', hang=False):
        self.data, self.hang = data, hang
    async def read(self, count):
        if self.hang:
            await asyncio.Event().wait()
        await asyncio.sleep(0)
        result, self.data = self.data[:count], self.data[count:]
        return result


class Writer:
    def __init__(self):
        self.data = b''
        self.closed = False
    def write(self, data):
        self.data += data
    async def drain(self):
        await asyncio.sleep(0)
    def close(self):
        self.closed = True


class Process:
    def __init__(self, data=None, code=0, hang=False):
        self.returncode = None
        self.code, self.hang = code, hang
        self.stdin = Writer()
        self.stdout = Reader(output() if data is None else data, hang)
        self.stderr = Reader(hang=hang)
    async def wait(self):
        if self.hang and self.returncode is None:
            await asyncio.Event().wait()
        await asyncio.sleep(.01)
        if self.returncode is None:
            self.returncode = self.code
        return self.returncode
    def kill(self):
        self.returncode = -9
        self.stdout.hang = self.stderr.hang = False


class ContractTests(unittest.TestCase):
    def test_pinned_image_and_binary_version(self):
        for image, binary, version in (('tag:latest', BINARY_SHA256, VERSION),
                                       ('sha256:'+'a'*64, '0'*64, VERSION),
                                       ('sha256:'+'a'*64, BINARY_SHA256, 'latest')):
            with self.assertRaises(CliFailure):
                ImagePin(image, binary, version)

    def test_catalog_restricts_tools_without_renaming_model(self):
        model = text_catalog('chosen-model')['models'][0]
        self.assertEqual(model['slug'], 'chosen-model')
        self.assertIsNone(model['apply_patch_tool_type'])
        self.assertEqual(model['experimental_supported_tools'], [])

    def test_catalog_rejects_flags_and_invalid_models(self):
        for model in ('--help', 'x y', 'x\n', '', None):
            with self.assertRaises(CliFailure):
                text_catalog(model)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pin = source()
        self.image = ImagePin('sha256:'+'a'*64, BINARY_SHA256, VERSION)
        self.transport = DockerTransport(self.image, Limits(timeout_seconds=2))
        self.process = Process()
        self.attempt = str(uuid4())
        self.cid = 'b'*64
        self.calls = []
        self.bad_labels = False
        self.cleanup_fails = False
        self.accesses = 0
        self.revoke_after = None
        self.started = asyncio.Event()

    async def authorize(self, pin):
        self.accesses += 1
        return self.revoke_after is None or self.accesses < self.revoke_after

    async def command(self, args, env, timeout=15):
        self.calls.append(args)
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('HTTP_PROXY', env)
        self.assertNotIn('DOCKER_HOST', env)
        if args[:2] == ['volume','inspect']:
            labels = {'pao.cli.'+k: self.pin[k] for k in ('workspace_id','actor_id','connection_id','device_id','profile_id')}
            if self.bad_labels:
                labels['pao.cli.workspace_id'] = str(uuid4())
            return json.dumps([{'Name': args[2], 'Driver':'local', 'Options':{}, 'Labels':labels}]).encode()
        if args[:2] == ['image','inspect']:
            return json.dumps([{'Id':self.image.image_id, 'Config':{'User':'65534:65534', 'Labels':{
                'pao.cli.version':VERSION, 'pao.cli.binary-sha256': BINARY_SHA256}}}]).encode()
        if args[0] == 'create':
            return self.cid.encode()
        if args[0] == 'inspect':
            return json.dumps([{'Id':self.cid, 'Config':{'Labels':{'pao.cli.attempt_id':self.attempt}}}]).encode()
        if args[0] == 'rm':
            if self.cleanup_fails:
                raise CliFailure('cli_docker_failed')
            return self.cid.encode()
        self.fail('Unexpected daemon command')

    async def spawn(self, *args, **kwargs):
        self.started.set()
        self.assertIn(self.cid, args)
        self.assertNotIn('SECRET_PROMPT', args)
        return self.process

    async def invoke(self, prompt='SECRET_PROMPT'):
        with patch.object(self.transport, 'command', self.command), patch('asyncio.create_subprocess_exec', self.spawn):
            return await self.transport.invoke(self.pin, self.attempt, prompt, self.authorize)

    async def test_success_only_after_eof_and_cleanup(self):
        result = await self.invoke()
        self.assertEqual(result.text, 'Xin chào')
        self.assertTrue(self.transport.cleanup_verified)
        self.assertEqual(json.loads(self.process.stdin.data)['prompt'], 'SECRET_PROMPT')
        create = next(c for c in self.calls if c[0] == 'create')
        for flag in ('--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pull=never'):
            self.assertIn(flag, create)
        self.assertTrue(all('type=bind' not in str(c) for c in self.calls))
        self.assertEqual(self.calls[-1], ['rm','--force',self.cid])

    async def test_cross_workspace_profile_denied_before_create(self):
        self.bad_labels = True
        with self.assertRaisesRegex(CliFailure, '^cli_profile_binding_invalid$'):
            await self.invoke()
        self.assertFalse(any(c[0] == 'create' for c in self.calls))

    async def test_access_denied_never_touches_docker(self):
        self.revoke_after = 1
        with self.assertRaisesRegex(CliFailure, '^cli_access_denied$'):
            await self.invoke()
        self.assertEqual(self.calls, [])

    async def test_revocation_after_create_before_prompt(self):
        self.revoke_after = 2
        with self.assertRaisesRegex(CliFailure, '^cli_access_denied$'):
            await self.invoke()
        self.assertEqual(self.process.stdin.data, b'')
        self.assertTrue(self.transport.cleanup_verified)

    async def test_bad_binary_pin(self):
        self.pin['binary_sha256'] = '0'*64
        with self.assertRaisesRegex(CliFailure, '^cli_binary_changed$'):
            await self.invoke()

    async def test_nonzero_exit_is_not_success(self):
        self.process = Process(code=1)
        with self.assertRaisesRegex(CliFailure, '^cli_process_failed$'):
            await self.invoke()
        self.assertTrue(self.transport.cleanup_verified)

    async def test_tool_event_invalidates_result_and_cleans(self):
        self.process = Process(data=output(tool=True))
        with self.assertRaisesRegex(CliFailure, '^cli_tool_event_denied$'):
            await self.invoke()
        self.assertTrue(self.transport.cleanup_verified)

    async def test_incomplete_event_stream(self):
        self.process = Process(data=b'{"type":"turn.started"}\n')
        with self.assertRaises(CliFailure):
            await self.invoke()
        self.assertTrue(self.transport.cleanup_verified)

    async def test_timeout_cleans_container_not_volume(self):
        self.transport.limits = Limits(timeout_seconds=.05)
        self.process = Process(hang=True)
        with self.assertRaisesRegex(CliFailure, '^cli_timeout$'):
            await self.invoke()
        self.assertTrue(self.transport.cleanup_verified)
        self.assertFalse(any('volume' in c and 'rm' in c for c in self.calls))

    async def test_cancel_cleans_container(self):
        self.process = Process(hang=True)
        task = asyncio.create_task(self.invoke())
        await self.started.wait()
        await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(self.transport.cleanup_verified)

    async def test_unverified_cleanup_is_error_not_success(self):
        self.cleanup_fails = True
        with self.assertRaisesRegex(CliFailure, '^cli_cleanup_failed$'):
            await self.invoke()
        self.assertFalse(self.transport.cleanup_verified)

    async def test_input_limit(self):
        self.transport.limits = Limits(max_input_bytes=64)
        with self.assertRaisesRegex(CliFailure, '^cli_input_limit$'):
            await self.invoke('x'*65)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
