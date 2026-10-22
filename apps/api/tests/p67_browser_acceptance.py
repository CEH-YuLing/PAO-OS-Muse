import asyncio
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select,func
from pao.config import ROOT
from pao.db import Session
from pao.models import AdAction,AdMetric,OutcomeObservation,now
from test_outcome_observations import fixture
from test_meta import meta
from p6_browser_harness import browser

async def test_outcome_observation_browser(client,identity,meta,monkeypatch):
    ident,cid,stamp=await fixture(identity,monkeypatch)
    async with Session.begin() as db:
        insufficient=AdAction(workspace_id=identity['workspace'],user_id=identity['user_id'],connection_id=cid,connection_version=1,
            account_id='act_1',resource_type='campaign',resource_id='20',action_type='pause',request_key=str(uuid4()),payload_hash='b'*64,
            before_state={'status':'ACTIVE'},proposed_state={'status':'PAUSED'},after_state={'simulated':True},reason='Synthetic insufficient fixture',
            approval_status='approved',execution_status='simulated',dry_run=True,approval_expires_at=now()+timedelta(hours=1),executed_at=stamp)
        db.add(insufficient);await db.flush();other=insufficient.id
    marker=ROOT/'.runtime'/('outcome-marker-'+uuid4().hex)
    async def update():
        for _ in range(300):
            if marker.exists():
                async with Session.begin() as db:(await db.scalar(select(AdMetric))).revenue=999
                return
            await asyncio.sleep(.5)
        raise AssertionError('Outcome browser did not reach source-change handshake')
    task=asyncio.create_task(update())
    try:
        await browser('scripts/verify_outcome_browser.cjs','PAO_OUTCOME_BROWSER_FIXTURE',{'action':ident,'insufficient':other,'marker':str(marker)},'outcome')
        await asyncio.wait_for(task,10)
        async with Session() as db:
            assert await db.scalar(select(func.count(OutcomeObservation.id)))==2
            rows=list(await db.scalars(select(OutcomeObservation)));assert {r.snapshot['outcomes']['7d']['status'] for r in rows}=={'observed','insufficient'}
    finally:task.cancel();await asyncio.gather(task,return_exceptions=True)
