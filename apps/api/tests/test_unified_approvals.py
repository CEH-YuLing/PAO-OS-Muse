import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock
import jwt
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Member, Task, ToolCall, AdAction, BusinessEvent, BusinessReceipt, now
from pao.modules.events.approvals import ticket
from pao.auth import Principal
from test_tools import tools_on, submit
from test_memory import run_chat
from test_ads_actions import write_setup, proposal, run_action
from test_meta import meta
from test_ads_autopilot import autopilot_data, put_policy, policy, analyst_proposal


@pytest.fixture
def approvals_on(monkeypatch):
    monkeypatch.setattr(settings(), 'unified_approvals_enabled', True)


async def make_task(client, identity):
    response = await client.post('/v1/tasks', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'title': 'Synthetic approval', 'status': 'waiting_approval',
        'success_criteria': ['Synthetic criteria'], 'evidence': [{'reference': 'Synthetic evidence'}]})
    assert response.status_code == 201
    return response.json()


async def get_inbox(client, identity, headers=None):
    return await client.get('/v1/business-events/approvals', params={'workspace_id': identity['workspace']},
                            headers=headers or identity['owner'])


async def test_default_off_and_auth(client, identity):
    assert (await client.get('/v1/business-events/status')).status_code == 401
    assert (await get_inbox(client, identity)).status_code == 409
    status = await client.get('/v1/business-events/status', headers=identity['owner'])
    assert status.status_code == 200 and not status.json()['enabled']


async def test_task_signed_scoped_snapshot(client, identity, approvals_on):
    row = await make_task(client, identity)
    response = await get_inbox(client, identity); assert response.status_code == 200
    [item] = response.json()
    assert item['id'] == row['id'] and item['can_decide'] and item['kind'] == 'task'
    claims = ticket(item['ticket'], Principal(identity['user_id'], 0))
    assert claims['workspace_id'] == identity['workspace'] and claims['input_hash'] == item['input_hash']
    assert 'Synthetic evidence' not in item['ticket']
    assert (await get_inbox(client, identity, identity['outsider'])).status_code == 404


async def test_viewer_read_only_and_hash_changes(client, identity, approvals_on):
    row = await make_task(client, identity)
    [before] = (await get_inbox(client, identity)).json()
    response = await client.patch('/v1/tasks/' + row['id'], headers=identity['owner'],
                                 json={'version': row['version'], 'description': 'New input'})
    assert response.status_code == 200
    [after] = (await get_inbox(client, identity)).json(); assert after['input_hash'] != before['input_hash']
    async with Session.begin() as db:
        (await db.get(Member, (identity['workspace'], identity['user_id']))).role = 'viewer'
    [viewer] = (await get_inbox(client, identity)).json(); assert not viewer['can_decide']


async def decision(client, identity, item, kind='approve', headers=None):
    return await client.post('/v1/business-events/approvals/decision', headers=headers or identity['owner'],
                             json={'ticket': item['ticket'], 'decision': kind})


async def propose(client,identity):
    return await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])


async def test_concurrent_approve_reject_one_wins_and_replay_stale(client, identity, approvals_on, monkeypatch):
    monkeypatch.setattr(settings(),'business_events_enabled',True)
    row = await make_task(client,identity)
    [item] = (await get_inbox(client,identity)).json()
    results = await asyncio.gather(decision(client,identity,item),decision(client,identity,item,'reject'))
    assert sorted(result.status_code for result in results)==[200,409]
    assert (await decision(client,identity,item)).status_code==409
    async with Session() as db:
        task = await db.get(Task,row['id']); assert task.status in ('completed','failed')
        events = list(await db.scalars(select(BusinessEvent)))
        assert sum(event.event_type=='approval.requested' for event in events)==1
        assert sum(event.event_type=='task.completed' for event in events)==(1 if task.status=='completed' else 0)


@pytest.mark.parametrize('change',['input','viewer','removed','expired','actor','forged'])
async def test_stale_or_invalid_ticket_denied(client,identity,approvals_on,change):
    row = await make_task(client,identity); [item] = (await get_inbox(client,identity)).json()
    if change in ('input','viewer','removed'):
        async with Session.begin() as db:
            if change=='input': (await db.get(Task,row['id'])).evidence=[{'reference':'changed-without-version'}]
            elif change=='viewer': (await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
            else: await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
    elif change=='expired':
        claims=jwt.decode(item['ticket'],settings().jwt_secret,algorithms=['HS256'],audience='pao-approval-decision')
        claims['exp']=int((now()-timedelta(seconds=1)).timestamp());item['ticket']=jwt.encode(claims,settings().jwt_secret,algorithm='HS256')
    elif change=='forged': item['ticket']=item['ticket'][:-8]+'aaaaaaaa'
    response=await decision(client,identity,item,headers=identity['other'] if change=='actor' else None)
    assert response.status_code in (403,404,409)
    async with Session() as db: assert (await db.get(Task,row['id'])).status=='waiting_approval'


async def test_tool_scope_freeze_and_revocation(client,identity,approvals_on,tools_on,monkeypatch):
    monkeypatch.setattr(settings(),'business_events_enabled',True)
    _,rid=await run_chat(client,identity,'Synthetic mock email')
    call=(await submit(client,identity,rid)).json()
    [item]=(await get_inbox(client,identity)).json(); assert item['kind']=='tool' and item['can_decide']
    assert (await get_inbox(client,identity,identity['other'])).json()==[]
    approved=await decision(client,identity,item); assert approved.status_code==200,approved.text
    provider=AsyncMock(return_value={'simulated':True})
    revoke=await client.post(f"/v1/business-events/approvals/tool/{call['id']}/revoke",headers=identity['owner'],json={'version':approved.json()['version']})
    assert revoke.status_code==200
    from pao.tool_gateway import execute_tool
    await execute_tool({'tool_invoke':provider},call['id']);provider.assert_not_awaited()
    assert (await decision(client,identity,item)).status_code==409
    async with Session() as db:
        event=await db.scalar(select(BusinessEvent));assert event.event_type=='approval.requested' and event.tool_call_id==call['id']


async def test_tool_input_changed_after_approval_never_invokes(client,identity,approvals_on,tools_on):
    _,rid=await run_chat(client,identity,'Synthetic mock email');call=(await submit(client,identity,rid)).json()
    [item]=(await get_inbox(client,identity)).json();assert (await decision(client,identity,item)).status_code==200
    async with Session.begin() as db:
        row=await db.get(ToolCall,call['id']);row.arguments={**row.arguments,'subject':'tampered'}
    from pao.tool_gateway import execute_tool
    provider=AsyncMock();await execute_tool({'tool_invoke':provider},call['id']);provider.assert_not_awaited()
    async with Session() as db:assert (await db.get(ToolCall,call['id'])).status=='cancelled'


async def test_ads_unified_rbac_snapshot_and_dry_run(client,identity,approvals_on,write_setup,monkeypatch):
    monkeypatch.setattr(settings(),'business_events_enabled',True)
    made=await propose(client,identity);assert made.status_code==201
    row=made.json()['action'];[item]=(await get_inbox(client,identity)).json()
    assert item['kind']=='ads' and item['dry_run']
    [other]=(await get_inbox(client,identity,identity['other'])).json();assert not other['can_decide']
    assert (await decision(client,identity,other,headers=identity['other'])).status_code==404
    assert (await decision(client,identity,item)).status_code==200
    await run_action(row['id']);assert write_setup[0].writes==[]
    async with Session() as db:
        action=await db.get(AdAction,row['id']);assert action.execution_status=='simulated'
        event=await db.scalar(select(BusinessEvent));assert event.ad_action_id==row['id']


async def test_ads_input_changed_after_approval_blocks_provider(client,identity,approvals_on,write_setup):
    made=await propose(client,identity);row=made.json()['action'];[item]=(await get_inbox(client,identity)).json()
    assert (await decision(client,identity,item)).status_code==200
    async with Session.begin() as db: (await db.get(AdAction,row['id'])).proposed_state={'status':'ACTIVE'}
    await run_action(row['id']);assert write_setup[0].writes==[]
    async with Session() as db:
        action=await db.get(AdAction,row['id']);assert action.execution_status=='cancelled' and action.error_code=='approval_input_changed'


async def test_ads_analysis_event_producer_and_delivery(client,identity,meta,monkeypatch):
    from datetime import date
    from test_intelligence import seed,target,analysis
    from pao.modules.events.delivery import claim,consume
    monkeypatch.setattr(settings(),'business_events_enabled',True)
    monkeypatch.setattr(settings(),'business_event_delivery_enabled',True)
    day=date(2026,2,3);await seed(identity,[(day,'30','0','0')])
    assert (await client.put('/v1/ads/targets',json=target(identity),headers=identity['owner'])).status_code==200
    body=analysis(identity,day)
    result=await client.post('/v1/ads/intelligence/analyze',json=body,headers=identity['owner']);assert result.status_code==201,result.text
    assert (await client.post('/v1/ads/intelligence/analyze',json=body,headers=identity['owner'])).status_code==201
    async with Session() as db:
        events=list(await db.scalars(select(BusinessEvent)));assert len(events)==1
        assert events[0].event_type=='ads.analysis.completed' and events[0].analysis_id
    assert await consume(*(await claim())[0])
    async with Session() as db:assert len(list(await db.scalars(select(BusinessReceipt))))==1


async def test_deferred_autopilot_policy_snapshot_and_stale_policy(client,identity,approvals_on,autopilot_data,monkeypatch):
    from pao.models import AdsAutopilotPolicy
    monkeypatch.setattr(settings(),'business_events_enabled',True)
    fake,_,rid=autopilot_data
    assert (await put_policy(client,identity)).status_code==200
    result=await client.post('/v1/ads/actions',json=analyst_proposal(identity,rid),headers=identity['owner'])
    assert result.status_code==201;row=result.json()['action'];assert row['approval_status']=='approved'
    async with Session.begin() as db:
        stored=await db.get(AdsAutopilotPolicy,row['policy_id']);stored.halted=True;stored.version+=1
    await run_action(row['id'])
    [item]=(await get_inbox(client,identity)).json();assert item['kind']=='ads'
    async with Session.begin() as db:
        stored=await db.get(AdsAutopilotPolicy,row['policy_id']);stored.version+=1
    response=await decision(client,identity,item)
    assert response.status_code==409 and response.json()['detail']=='approval_input_changed'
    assert fake.writes==[]
    async with Session() as db:
        event=await db.scalar(select(BusinessEvent));assert event.event_type=='approval.requested'
