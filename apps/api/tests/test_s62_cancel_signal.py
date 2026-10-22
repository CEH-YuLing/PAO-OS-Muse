"""Verified native abort must wait for signal without waiting indefinitely."""
from types import SimpleNamespace
import pytest
from temporalio.exceptions import ApplicationError
from pao.modules.studio import arq_bridge as bridge


async def test_verified_abort_without_signal_still_has_deadline(monkeypatch):
    clock=SimpleNamespace(now=0)
    async def no_receipt(*args):return None
    async def reserve(*args):pass
    async def recover(*args):return {'status':'cancelled'}
    async def yield_once(*args):pass
    monkeypatch.setattr(bridge,'verified_receipt',no_receipt)
    monkeypatch.setattr(bridge.jobs,'reserve',reserve)
    monkeypatch.setattr(bridge.jobs,'recover',recover)
    monkeypatch.setattr(bridge.activity,'heartbeat',lambda *args:None)
    monkeypatch.setattr(bridge.asyncio,'get_running_loop',lambda:SimpleNamespace(time=lambda:clock.now))
    monkeypatch.setattr(bridge.asyncio,'sleep',yield_once)
    adapter=bridge.DryRunBridge(SimpleNamespace(),require_queue_ack=True)
    calls=[]
    async def drain(args):
        calls.append(args);clock.now=26
        return {'queue_ack_verified':True}
    monkeypatch.setattr(adapter,'drain',drain)
    with pytest.raises(ApplicationError,match='step_bridge_timeout'):
        await adapter.step({'plan_id':'plan','step_id':'step','execution_id':'execution'})
    assert calls==[('plan','step','execution')]
