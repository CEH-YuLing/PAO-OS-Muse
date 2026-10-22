"""Offline codecs/Windows containment; no provider, credentials or database."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock,patch
from pao.modules.cli_connections import muse_execution as m
from pao.modules.cli_connections import muse_resource as r
from pao.modules.cli_connections.muse_process import Child
from pao.modules.engines.contract import EngineFailure


def frame(kind,**payload):return json.dumps({'schema_version':1,'payload_type':kind,'payload':payload}).encode()
def wire(model='muse-spark-1.3',usage=None,**change):
    stdout=b'\n'.join([frame('session.run.linked',run_stream='fixture-run'),
        frame('run.model.configured',model_id=model,provider_id='meta'),
        frame('task.lifecycle.proposed',event={'task_kind':'model.meta.response'}),
        frame('run.terminal.completed',terminal='completed',text='fixture',run_stream='fixture-run')])
    request={'model':model,'instructions':'native fixture','input':[],'reasoning':{'effort':'low'},**change}
    response={'type':'response.completed','response':{'model':model,'usage':usage or {}}}
    return stdout,(json.dumps(request)+'\n'+json.dumps(response)).encode()


class CodecTests(unittest.TestCase):
    def test_usage_is_actual_never_estimated(self):
        text,usage=m.parse(*wire(usage={'input_tokens':13983,'output_tokens':27}), 'muse-spark-1.3','low')
        self.assertEqual((text,usage),('fixture',{'input_tokens':13983,'output_tokens':27}))
        self.assertEqual(m.parse(*wire(),'muse-spark-1.3','low')[1],{})

    def test_wrong_model_effort_tools_and_duplicate_requests_refused(self):
        for change in ({'model':'other'},{'reasoning':{'effort':'high'}},{'tools':[{'name':'shell'}]}):
            with self.subTest(change=change),self.assertRaises(EngineFailure):m.parse(*wire(**change),'muse-spark-1.3','low')
        out,err=wire()
        with self.assertRaises(EngineFailure):m.parse(out,err+b'\n'+err,'muse-spark-1.3','low')

    def test_tool_lifecycle_and_malformed_terminal_refused(self):
        out,err=wire()
        for extra in (frame('task.lifecycle.proposed',event={'task_kind':'tool.shell'}),
                      frame('run.terminal.completed',terminal='completed',text='other',run_stream='fixture-run')):
            with self.assertRaises(EngineFailure):m.parse(out+b'\n'+extra,err,'muse-spark-1.3','low')

    def test_unknown_counts_never_become_zero(self):
        for n in (-1,True,'20',1000001):
            self.assertEqual(m.parse(*wire(usage={'input_tokens':n}),'muse-spark-1.3','low')[1],{})

    def test_source_stamp_cannot_admit_metadata_only_or_changed_binary(self):
        value={'revision':1,'connected':True,'account_state':'accountLogin','binary_sha256':m.client.SHA,
            'schema_fingerprint':m.client.SCHEMA,'profile':'pao_isolated','execution_adapter':r.ADAPTER,'models':[]}
        with patch.object(m.client,'read_state',return_value=value):
            original=r.stamp();value['revision']=2;self.assertNotEqual(original,r.stamp())
            value.pop('execution_adapter')
            with self.assertRaises(EngineFailure):r.stamp()

    def test_containment_child_is_inert_before_resume_and_tree_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'marker'
            script="import pathlib,sys,time,subprocess;pathlib.Path(sys.argv[1]).write_text('owned');subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);time.sleep(30)"
            child=Child([sys.executable,'-c',script,str(marker)],cwd=tmp,env=dict(__import__('os').environ))
            try:
                self.assertFalse(marker.exists());child.resume()
                import time
                deadline=time.monotonic()+5
                while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(marker.exists())
            finally:child.close()
            self.assertTrue(child.cleanup_verified)
            self.assertIsNotNone(child.process.poll())


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_messages_do_not_probe_or_start(self):
        for wire in ([],[{'role':'tool','content':'bad'}],[{'role':'user','content':'x','extra':'bad'}]):
            with patch.object(m.client,'discover',AsyncMock()) as probe,self.assertRaises(EngineFailure):
                await m.execute(wire,'model','low',AsyncMock())
            probe.assert_not_called()

    async def test_revocation_before_resume_closes_suspended_child_without_call(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.profile,'PROFILE',Path(tmp)/'owned'),\
             patch.object(m.client,'discover',AsyncMock(return_value={'account_state':'accountLogin','models':[{'model':'fixture','reasoning_efforts':['low'],'default_effort':'low'}]})),\
             patch.object(m.client,'binary',return_value=Path('never-run')),patch.object(m,'run_environment',return_value={}),\
             patch.object(m,'Child') as cls:
            cls.return_value.close.return_value=None
            authorize=AsyncMock(side_effect=[None,EngineFailure('revoked')])
            with self.assertRaisesRegex(EngineFailure,'revoked'):
                await m.execute([{'role':'user','content':'fixture'}],'fixture','low',authorize)
            cls.return_value.resume.assert_not_called();cls.return_value.close.assert_called_once()
            self.assertEqual(list(Path(tmp).rglob('prompt.txt')),[])

    async def test_gateway_without_ledger_never_runs(self):
        with patch.object(m,'execute',AsyncMock()) as send,self.assertRaises(EngineFailure):
            await m.MuseGateway('fixture',{'model':'fixture'}).invoke([{'role':'user','content':'x'}])
        send.assert_not_called()


if __name__=='__main__':unittest.main()
