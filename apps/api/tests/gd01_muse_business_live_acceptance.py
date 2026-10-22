"""Explicit two-call real Muse subscription business cycle, synthetic pao_test only."""
from test_muse_business import business_cycle


async def test_real_muse_business_cycle(client,identity,monkeypatch,tmp_path):
    state=await business_cycle(client,identity,monkeypatch,tmp_path,live=True)
    assert state['pass'] and state['live_subscription'] is True
