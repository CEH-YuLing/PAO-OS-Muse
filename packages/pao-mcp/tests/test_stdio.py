"""Real stdio subprocess, never agy or a model."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]


class StdioTests(unittest.TestCase):
    def start(self, fake=False):
        if fake:
            code = "import sys,asyncio;sys.path.insert(0,sys.argv[1]);from pao_mcp.stdio import serve\nclass Slow:\n async def call(self,*_):\n  await asyncio.sleep(30)\nasyncio.run(serve(Slow()))"
            args = [sys.executable, '-I', '-B', '-c', code, str(ROOT / 'packages/pao-mcp')]
        else:
            args = [sys.executable, '-I', '-B', str(ROOT / 'scripts/pao_mcp.py'), 'serve', '--profile',
                    str(ROOT / '.runtime/pao-mcp/profiles' / (str(uuid4()) + '.dpapi'))]
        self.child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.close)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.addCleanup(lambda: self.executor.shutdown(wait=False, cancel_futures=True))
        self.send({'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'local-test', 'version': '1'}}})
        self.assertEqual(self.receive()['result']['serverInfo']['name'], 'pao-readonly')
        self.send({'method': 'notifications/initialized'})

    def close(self):
        if self.child.poll() is None:
            self.child.stdin.close()
            try: self.child.wait(timeout=4)
            except subprocess.TimeoutExpired: self.child.kill(); self.child.wait(timeout=4)
        for stream in (self.child.stdout, self.child.stderr): stream.close()

    def send(self, value):
        self.child.stdin.write(json.dumps({'jsonrpc': '2.0', **value}).encode() + b'\n')
        self.child.stdin.flush()

    def receive(self):
        line = self.executor.submit(self.child.stdout.readline).result(timeout=5)
        self.assertTrue(line, 'stdio closed unexpectedly')
        return json.loads(line)

    def test_real_catalog_and_missing_profile_denied(self):
        self.start()
        self.send({'id': 2, 'method': 'tools/list'})
        self.assertEqual(len(self.receive()['result']['tools']), 5)
        self.send({'id': 3, 'method': 'tools/call', 'params': {'name': 'pao_scope'}})
        self.assertTrue(self.receive()['result']['isError'])
        self.send({'id': 4, 'method': 'ping'})
        self.assertEqual(self.receive()['result'], {})

    def test_cancel_actual_pending_read(self):
        self.start(True)
        self.send({'id': 8, 'method': 'tools/call', 'params': {'name': 'pao_scope'}})
        self.send({'method': 'notifications/cancelled', 'params': {'requestId': 8}})
        self.assertEqual(self.receive()['error']['code'], -32800)
        self.send({'id': 9, 'method': 'ping'})
        self.assertEqual(self.receive()['result'], {})

    def test_malformed_and_oversized_stdio(self):
        self.start()
        self.child.stdin.write(b'{"jsonrpc":"2.0","id":2,"id":3}\n'); self.child.stdin.flush()
        self.assertEqual(self.receive()['error']['code'], -32700)
        self.child.stdin.write(b'X' * 65537 + b'\n'); self.child.stdin.flush()
        self.assertEqual(self.receive()['error']['code'], -32700)
        self.child.wait(timeout=5)
        self.assertEqual(self.child.returncode, 0)
