"""Offline setup-readiness checks; no DB, CLI, download or business delivery."""
import asyncio,sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api/tests'))
from temporal_fixture import namespace_ready
from temporalio.service import RPCError,RPCStatusCode

class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    def client(self,call):return SimpleNamespace(namespace='default',workflow_service=SimpleNamespace(describe_namespace=call))

    async def test_registered_is_required_and_probe_does_not_enable_retries(self):
        calls=[]
        async def describe(request,**options):
            calls.append(options);self.assertEqual(request.namespace,'default')
            return SimpleNamespace(namespace_info=SimpleNamespace(state=0 if len(calls)==1 else 1))
        await namespace_ready(self.client(describe),timeout=.5)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(c['retry'] is False for c in calls))

    async def test_unready_cannot_silently_pass_or_wait_forever(self):
        async def describe(*args,**kwargs):
            return SimpleNamespace(namespace_info=SimpleNamespace(state=0))
        with self.assertRaises(asyncio.TimeoutError):await namespace_ready(self.client(describe),timeout=.08)

    async def test_permission_error_is_not_retried_as_startup(self):
        calls=[]
        async def describe(*args,**kwargs):
            calls.append(1);raise RPCError('fixture forbidden',RPCStatusCode.PERMISSION_DENIED,b'')
        with self.assertRaises(RPCError):await namespace_ready(self.client(describe),timeout=.5)
        self.assertEqual(len(calls),1)

    async def test_transient_unavailable_is_prepared_before_test(self):
        calls=[]
        async def describe(*args,**kwargs):
            calls.append(1)
            if len(calls)==1:raise RPCError('fixture starting',RPCStatusCode.UNAVAILABLE,b'')
            return SimpleNamespace(namespace_info=SimpleNamespace(state=1))
        await namespace_ready(self.client(describe),timeout=.5)
        self.assertEqual(len(calls),2)

if __name__=='__main__':unittest.main()
