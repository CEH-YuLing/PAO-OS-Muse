import asyncio
from copy import deepcopy
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pao_mcp.bridge import BASE, Bridge, Denied, profile, strict_json
from pao_mcp.stdio import Protocol
from pao_mcp import profile as store

W, A, P, B, S, T, X = [str(uuid4()) for _ in range(7)]


def config():
    return {'version': 1, 'actor_id': A, 'workspace_id': W, 'projects': [P], 'brains': {B: None},
            'token': 'synthetic-test-token-not-real', 'consent': True, 'enabled': True}


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    def make(self, transform=None):
        self.cfg = config(); self.calls = []
        def handle(request):
            self.calls.append(request)
            assert request.method == 'GET'
            assert str(request.url).startswith(BASE + '/')
            assert request.headers['authorization'] == 'Bearer ' + self.cfg['token']
            path = request.url.path
            if path == '/v1/me': body = {'id': A}
            elif path.endswith('/context'): body = {'id': W, 'role': 'owner'}
            elif path == '/v1/brains': body = [{'id': B, 'workspace_id': W, 'brand_id': None, 'archived_at': None}]
            elif path == '/v1/tasks': body = [{'id': T, 'workspace_id': W, 'project_id': P, 'title': 'Việc thử', 'secret_field': 'NEVER-EXPORT'}]
            elif path == '/v1/tasks/' + T: body = {'id': T, 'workspace_id': W, 'project_id': P, 'description': 'Bản thử', 'input_references': ['NEVER-EXPORT']}
            elif path.endswith('/sources'): body = [{'id': S, 'brain_id': B, 'title': 'Nguồn', 'archived_at': None}]
            elif path.endswith('/preview'): body = {'source_id': S, 'version': 1, 'format': 'plain_text', 'content': 'Tài liệu tiếng Việt'}
            else: raise AssertionError(path)
            return transform(request, body) if transform else httpx.Response(200, json=body)
        return Bridge(lambda: deepcopy(self.cfg), httpx.MockTransport(handle))

    async def test_scope_minimal_no_token(self):
        value = await self.make().call('pao_scope', {})
        self.assertEqual(value['workspace_id'], W)
        self.assertNotIn('synthetic', json.dumps(value))
        self.assertEqual(len(self.calls), 4)

    async def test_tasks_projection_and_query(self):
        value = await self.make().call('pao_list_tasks', {'project_id': P, 'limit': 2})
        self.assertEqual(value['items'][0]['title'], 'Việc thử')
        self.assertNotIn('NEVER-EXPORT', json.dumps(value))
        request = next(r for r in self.calls if r.url.path == '/v1/tasks')
        self.assertEqual(request.url.params['workspace_id'], W)
        self.assertEqual(request.url.params['project_id'], P)
        self.assertEqual(request.url.params['limit'], '2')

    async def test_task_detail(self):
        value = await self.make().call('pao_get_task', {'project_id': P, 'task_id': T})
        self.assertEqual(value['items'][0]['description'], 'Bản thử')
        self.assertNotIn('NEVER-EXPORT', json.dumps(value))

    async def test_no_guessed_unselected_task_fetch(self):
        bridge = self.make()
        with self.assertRaises(Denied): await bridge.call('pao_get_task', {'project_id': P, 'task_id': X})
        self.assertFalse(any(r.url.path == '/v1/tasks/' + X for r in self.calls))

    async def test_sources_and_preview(self):
        bridge = self.make()
        self.assertEqual((await bridge.call('pao_list_sources', {'brain_id': B}))['items'][0]['id'], S)
        self.assertEqual((await bridge.call('pao_preview_source', {'brain_id': B, 'source_id': S, 'version': 1}))['content'], 'Tài liệu tiếng Việt')

    async def test_unknown_inputs_pre_http(self):
        for name, args in [('execute', {}), ('pao_scope', {'url': 'https://evil.test'}),
                           ('pao_list_tasks', {'project_id': '../etc'}), ('pao_list_tasks', {'project_id': {'a': 1}}),
                           ('pao_list_tasks', {'project_id': P, 'limit': True}),
                           ('pao_list_tasks', {'project_id': P, 'limit': 500}),
                           ('pao_preview_source', {'brain_id': B, 'source_id': S, 'version': 0}),
                           ('pao_scope', []), ('pao_get_task', {'task_id': T})]:
            bridge = self.make()
            with self.subTest(name=name, args=args), self.assertRaises(Denied): await bridge.call(name, args)
            self.assertEqual(self.calls, [])

    async def test_unselected_projects_and_brains(self):
        for name, args in [('pao_list_tasks', {'project_id': X}), ('pao_get_task', {'project_id': X, 'task_id': T}), ('pao_list_sources', {'brain_id': X})]:
            bridge = self.make()
            with self.assertRaises(Denied): await bridge.call(name, args)
            self.assertFalse(any(r.url.path in ('/v1/tasks', '/v1/brains') for r in self.calls))

    async def test_unauthorized_and_redirect_not_followed(self):
        for code in (401, 403, 404, 409, 503, 302):
            bridge = self.make(lambda r, b: httpx.Response(code, headers={'location': 'https://evil.test'}, text='secret upstream detail'))
            with self.subTest(code=code), self.assertRaises(Denied) as caught: await bridge.call('pao_scope', {})
            self.assertNotIn('secret', str(caught.exception))
            self.assertEqual(len(self.calls), 1)

    async def test_cross_actor_workspace_and_role(self):
        for mutation in ('actor', 'workspace', 'role'):
            def change(request, body):
                if mutation == 'actor' and request.url.path == '/v1/me': body['id'] = X
                if request.url.path.endswith('/context'):
                    if mutation == 'workspace': body['id'] = X
                    if mutation == 'role': body['role'] = 'viewer'
                return httpx.Response(200, json=body)
            with self.subTest(mutation=mutation), self.assertRaises(Denied): await self.make(change).call('pao_scope', {})

    async def test_post_read_session_revocation(self):
        count = 0
        def change(request, body):
            nonlocal count
            if request.url.path == '/v1/me': count += 1
            return httpx.Response(401) if count == 2 else httpx.Response(200, json=body)
        with self.assertRaises(Denied): await self.make(change).call('pao_list_tasks', {'project_id': P})

    async def test_local_disconnect_mid_read(self):
        def change(request, body):
            if request.url.path == '/v1/tasks': self.cfg['enabled'] = False
            return httpx.Response(200, json=body)
        with self.assertRaises(Denied): await self.make(change).call('pao_list_tasks', {'project_id': P})

    async def test_task_moved_no_release(self):
        def change(request, body):
            if request.url.path == '/v1/tasks/' + T: body['project_id'] = X
            return httpx.Response(200, json=body)
        with self.assertRaises(Denied): await self.make(change).call('pao_get_task', {'project_id': P, 'task_id': T})

    async def test_cross_workspace_task_no_release(self):
        def change(request, body):
            if request.url.path == '/v1/tasks': body[0]['workspace_id'] = X
            return httpx.Response(200, json=body)
        with self.assertRaises(Denied): await self.make(change).call('pao_list_tasks', {'project_id': P})

    async def test_brain_brand_change_and_revoke_after_read(self):
        for mode in ('brand', 'revoke', 'archive', 'workspace'):
            count = 0
            def change(request, body):
                nonlocal count
                if request.url.path == '/v1/brains':
                    count += 1
                    if count == 2:
                        if mode == 'revoke': body = []
                        elif mode == 'brand': body[0]['brand_id'] = X
                        elif mode == 'workspace': body[0]['workspace_id'] = X
                        else: body[0]['archived_at'] = '2026-10-20'
                return httpx.Response(200, json=body)
            with self.subTest(mode=mode), self.assertRaises(Denied): await self.make(change).call('pao_list_sources', {'brain_id': B})

    async def test_wrong_source_result(self):
        def change(request, body):
            if request.url.path.endswith('/preview'): body['source_id'] = X
            return httpx.Response(200, json=body)
        with self.assertRaises(Denied): await self.make(change).call('pao_preview_source', {'brain_id': B, 'source_id': S, 'version': 1})

    async def test_http_bounds_content_type_and_json(self):
        for response in (httpx.Response(200, text='not json'),
                         httpx.Response(200, content=b'{"id":1,"id":2}', headers={'content-type': 'application/json'}),
                         httpx.Response(200, json={'id': 'x' * 1_048_576})):
            with self.assertRaises(Denied): await self.make(lambda r, b: response).call('pao_scope', {})

    async def test_oversize_result(self):
        def change(request, body):
            if request.url.path == '/v1/tasks': body[0]['title'] = 'x' * 61_000
            return httpx.Response(200, json=body)
        with self.assertRaises(Denied): await self.make(change).call('pao_list_tasks', {'project_id': P})

    async def test_network_error_sanitized(self):
        def change(request, body): raise httpx.ConnectError('private-token', request=request)
        with self.assertRaises(Denied) as caught: await self.make(change).call('pao_scope', {})
        self.assertNotIn('private-token', str(caught.exception))


class ProfileTests(unittest.TestCase):
    def test_profile_variants(self):
        for key, value in [('enabled', False), ('consent', False), ('version', True), ('actor_id', '../'), ('token', 'bad\nsecret'), ('projects', [P, P])]:
            cfg = config(); cfg[key] = value
            with self.subTest(key=key), self.assertRaises(Denied): profile(cfg)

    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'"\xff"', b'"\\ud800"'):
            with self.subTest(raw=raw), self.assertRaises(Denied): strict_json(raw)

    def test_real_windows_dpapi_roundtrip_and_tamper(self):
        encrypted = store.crypt(b'synthetic-not-a-provider-token')
        self.assertNotIn(b'synthetic', encrypted)
        self.assertEqual(store.crypt(encrypted, True), b'synthetic-not-a-provider-token')
        with self.assertRaises(Denied): store.crypt(encrypted[:-8], True)

    def test_local_profile_disconnect(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.dpapi'
            store.create(path, config())
            self.assertEqual(store.read(path), config())
            with self.assertRaises(FileExistsError): store.create(path, config())
            store.disable(path)
            with self.assertRaises(Denied): store.read(path)


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_catalog_and_error(self):
        p = Protocol(Bridge(lambda: profile({'enabled': False})))
        self.assertIn('error', await p.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}))
        reply = await p.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}})
        self.assertEqual(reply['result']['protocolVersion'], '2024-11-05')
        self.assertEqual(reply['result']['capabilities'], {'tools': {'listChanged': False}})
        await p.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        tools = await p.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'})
        self.assertEqual(len(tools['result']['tools']), 5)
        self.assertTrue(all(t['annotations']['readOnlyHint'] for t in tools['result']['tools']))
        result = await p.handle({'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'pao_scope'}})
        self.assertTrue(result['result']['isError'])
        self.assertNotIn('token', json.dumps(result))

    async def test_invalid_envelopes_and_methods(self):
        p = Protocol(None)
        for value in ([], {}, {'jsonrpc': '2.0', 'id': True, 'method': 'ping'}, {'jsonrpc': '2.0', 'id': 1, 'method': 'ping', 'params': []}):
            with self.subTest(value=value): self.assertIn('error', await p.handle(value))
        await p.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': 'future'}})
        await p.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        for method in ('initialize', 'resources/read', 'sampling/createMessage', 'pao_delete_task'):
            self.assertIn('error', await p.handle({'jsonrpc': '2.0', 'id': 2, 'method': method}))

    async def test_unexpected_exception_not_exposed(self):
        class Fake:
            async def call(self, *_): raise RuntimeError('SECRET-MARKER')
        p = Protocol(Fake()); p.ready = True
        result = await p.handle({'jsonrpc': '2.0', 'id': 'a', 'method': 'tools/call', 'params': {'name': 'pao_scope'}})
        self.assertTrue(result['result']['isError'])
        self.assertNotIn('SECRET-MARKER', json.dumps(result))
