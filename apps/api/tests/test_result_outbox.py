"""Real DB outbox/restart, permission loss and Goal terminal evidence."""
import asyncio,json,os,subprocess,sys
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import ResultDelivery,ResultInboxReceipt,GoalResultReceipt,GoalResultDelivery,Member,User,GoalExecution
from pao.modules.results import outbox
from test_result_inbox import terminal
from test_durable_admission import gates
from test_goal_admission import goal_gates
from test_goal_iterations import iteration_gates
from test_goal_runner import runner_gates,stack,admission,approve,approve_steps,wait
from test_goal_temporal_kernel import temporal

async def pending(client,identity,monkeypatch):
    await terminal(client,identity,monkeypatch)
    items=(await client.get('/v1/results',params={'workspace_id':identity['workspace']},headers=identity['owner'])).json()
    item=items[0];url='/v1/results/'+item['id']+'/deliveries'
    body={'source_hash':item['source_hash'],'recipient_id':identity['user_id']}
    original=outbox.dispatch_one;monkeypatch.setattr(outbox,'dispatch_one',AsyncMock())
    result=await client.post(url,headers=identity['owner'],json=body)
    assert result.status_code==200 and result.json()['status']=='pending',result.text
    monkeypatch.setattr(outbox,'dispatch_one',original)
    return url,body,result.json()

async def test_pending_survives_fresh_interpreter_and_dedup(client,identity,gates,monkeypatch):
    url,body,row=await pending(client,identity,monkeypatch)
    code='import asyncio,json; from pao.modules.results.outbox import dispatch_results; from pao.db import engine; '+"\nasync def main():\n print(json.dumps(await dispatch_results()));await engine.dispose()\nasyncio.run(main())"
    p=await asyncio.create_subprocess_exec(sys.executable,'-c',code,env={**os.environ,'RESULT_INBOX_ENABLED':'true'},stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:stdout,_=await asyncio.wait_for(p.communicate(),25)
    except asyncio.TimeoutError:p.kill();await p.communicate();raise
    assert p.returncode==0 and json.loads(stdout)['processed']==1
    results=await asyncio.gather(*(client.post(url,headers=identity['owner'],json=body) for _ in range(3)))
    assert all(r.status_code==200 and r.json()['status']=='delivered' and r.json()['attempts']==1 for r in results)
    async with Session() as db:
        assert await db.scalar(select(func.count(ResultDelivery.id)))==1
        assert await db.scalar(select(func.count(ResultInboxReceipt.id)))==0

@pytest.mark.parametrize('loss',['sender','recipient','inactive','source'])
async def test_pending_permission_or_source_loss_is_failed_not_delivered(client,identity,gates,monkeypatch,loss):
    url,body,row=await pending(client,identity,monkeypatch)
    async with Session.begin() as db:
        if loss=='sender':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif loss=='recipient':await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
        elif loss=='inactive':(await db.get(User,identity['user_id'])).active=False
        else:
            from pao.models import StudioExecution
            saved=await db.get(StudioExecution,(await db.get(ResultDelivery,row['id'])).source_id);saved.state={**saved.state,'reason':'tampered'}
    await outbox.dispatch_results();await outbox.dispatch_results()
    async with Session() as db:
        saved=await db.get(ResultDelivery,row['id']);assert saved.status=='failed' and saved.attempts==1 and saved.delivered_at is None
        assert saved.error_code in ('sender_permission_lost','recipient_permission_lost','source_invalid')

async def test_explicit_retry_after_authority_restored_bounded_and_read_scoped(client,identity,gates,monkeypatch):
    url,body,row=await pending(client,identity,monkeypatch)
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    await outbox.dispatch_results()
    assert (await client.post(url,headers=identity['owner'],json=body)).status_code==403
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='owner'
    r=await client.post(url,headers=identity['owner'],json=body);assert r.json()['status']=='delivered' and r.json()['attempts']==2
    assert len((await client.get(url,headers=identity['owner'])).json())==1
    assert (await client.get(url,headers=identity['other'])).json()==[]
    assert (await client.get(url,headers=identity['outsider'])).status_code==404
    async with Session.begin() as db:
        saved=await db.get(ResultDelivery,row['id']);saved.status='failed';saved.attempts=5;saved.error_code='delivery_attempts_exhausted'
    r=await client.post(url,headers=identity['owner'],json=body);assert r.json()['status']=='failed' and r.json()['attempts']==5

async def test_gate_rollback_leaves_pending_until_reenabled(client,identity,gates,monkeypatch):
    _,_,row=await pending(client,identity,monkeypatch)
    settings().result_inbox_enabled=False;assert (await outbox.dispatch_results())['processed']==0
    async with Session() as db:assert (await db.get(ResultDelivery,row['id'])).status=='pending'
    settings().result_inbox_enabled=True
    await asyncio.gather(*(outbox.dispatch_results() for _ in range(3)))
    async with Session() as db:assert (await db.get(ResultDelivery,row['id'])).attempts==1

async def test_actual_goal_receipt_delivery_and_projection_tamper(client,identity,runner_gates,temporal,monkeypatch):
    monkeypatch.setattr(settings(),'result_inbox_enabled',True)
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,plan,row,_=await admission(client,identity,target='Fixture planning')
            await approve(client,identity,row);await approve_steps(client,identity,plan['plan_id'])
            await wait(client,identity,row,'completed')
    items=(await client.get('/v1/results',params={'workspace_id':identity['workspace']},headers=identity['owner'])).json()
    goal=next(i for i in items if i['source']=='goal_dry_run');assert goal['id']==row['execution_id'] and not goal['business_success_proven']
    url='/v1/results/'+goal['id'];body={'source_hash':goal['source_hash'],'action':'ack'}
    results=await asyncio.gather(*(client.post(url+'/receipt',headers=identity['owner'],json=body) for _ in range(2)))
    assert all(r.status_code==200 and r.json()['acknowledged'] for r in results)
    r=await client.post(url+'/deliveries',headers=identity['owner'],json={'source_hash':goal['source_hash'],'recipient_id':identity['user_id']})
    assert r.status_code==200 and r.json()['status']=='delivered',r.text
    async with Session.begin() as db:
        assert await db.scalar(select(func.count(GoalResultReceipt.id)))==1
        assert await db.scalar(select(func.count(GoalResultDelivery.id)))==1
        saved=await db.get(GoalExecution,goal['id']);saved.state={**saved.state,'reason':'tampered'}
    assert (await client.post(url+'/receipt',headers=identity['owner'],json=body)).status_code==409
