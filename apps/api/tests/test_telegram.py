import asyncio
from datetime import timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select, func
import pao.ads_actions as action_service
from pao.config import settings
from pao.db import Session
from pao.models import (TelegramPeer, TelegramUpdate, TelegramDelivery, Run, ChatSession,
    Member, ToolCall, AdAction, AdActionAudit, Goal, Task, Workspace, now)
from pao.telegram import ingest, collect, deliver
from pao.runtime import execute_run
from pao.main import app
from pao.tool_gateway import propose
from test_meta import connected, meta


@pytest.fixture
async def peer(identity,monkeypatch):
    monkeypatch.setattr(settings(),'telegram_enabled',True)
    monkeypatch.setattr(settings(),'telegram_bot_token','synthetic-token-no-network')
    monkeypatch.setattr(settings(),'telegram_mode','webhook')
    monkeypatch.setattr(settings(),'telegram_webhook_secret','x'*40)
    async with Session.begin() as db:
        row=TelegramPeer(telegram_user_id='12345',chat_id='12345',user_id=identity['user_id'],workspace_id=identity['workspace'])
        db.add(row)
    return row


def update(index=1,text='Summarize supplied test facts',sender=12345,chat=12345,kind='private'):
    return {'update_id':index,'message':{'message_id':index,'from':{'id':sender,'is_bot':False},'chat':{'id':chat,'type':kind},'text':text}}


@pytest.fixture
async def ads_approval(identity,meta):
    connection_id=await connected(identity)
    async with Session.begin() as db:
        action=AdAction(connection_id=connection_id,connection_version=1,workspace_id=identity['workspace'],
            user_id=identity['user_id'],platform='meta',account_id='act_1',resource_type='campaign',resource_id='10',
            action_type='pause',request_key=str(uuid4()),payload_hash='a'*64,
            before_state={'id':'10','account_id':'1','status':'ACTIVE'},proposed_state={'status':'PAUSED'},
            after_state={},compensating_action={'status':'ACTIVE'},reason='Telegram approval integration test',
            confidence='0.9',source_agent='user',approval_status='pending',execution_status='pending',dry_run=True,
            version=1,approval_expires_at=now()+timedelta(hours=24),result_24h={},result_72h={},result_7d={})
        db.add(action);await db.flush();return action.id


async def test_whitelist_and_replay_are_atomic(client,peer):
    redis=app.state.redis
    for payload in (update(sender=999),update(chat=999),update(kind='group')):
        await ingest(payload,redis)
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run))==0
    await asyncio.gather(ingest(update(),redis),ingest(update(),redis))
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run))==1
        assert await db.scalar(select(func.count()).select_from(TelegramUpdate))==1
        session=await db.scalar(select(ChatSession))
        assert session.user_id==peer.user_id and session.workspace_id==peer.workspace_id and not session.memory_enabled


async def test_busy_cancel_new_and_status(client,peer):
    redis=app.state.redis
    await ingest(update(),redis)
    await ingest(update(2,'Another task'),redis)
    await ingest(update(3,'/cancel'),redis)
    async with Session() as db:
        runs=list(await db.scalars(select(Run)))
        assert len(runs)==1 and runs[0].cancel_requested
    await ingest(update(4,'/new'),redis)
    await ingest(update(5,'New conversation task'),redis)
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(ChatSession))==2


async def test_read_only_goal_and_task_commands(client,peer):
    async with Session.begin() as db:
        goal=Goal(workspace_id=peer.workspace_id,title='Tăng chất lượng báo cáo',description='',
                  success_criteria=['Có evidence'],status='active',owner_id=peer.user_id,
                  created_by=peer.user_id)
        task=Task(workspace_id=peer.workspace_id,title='Đối chiếu nguồn',description='',status='ready',
                  kind='human',priority='medium',assignee_type='unassigned',progress=0,source='user',
                  success_criteria=['Có kết quả'],created_by=peer.user_id)
        db.add_all([goal,task])
    await ingest(update(1,'/goals'),app.state.redis)
    await ingest(update(2,'/tasks'),app.state.redis)
    async with Session() as db:
        deliveries=list(await db.scalars(select(TelegramDelivery).order_by(TelegramDelivery.created_at)))
        text='\n'.join(row.payload['text'] for row in deliveries)
        assert 'Tăng chất lượng báo cáo · active' in text
        assert 'Đối chiếu nguồn · ready' in text


async def test_revoked_peer_cannot_receive_or_submit(client,peer):
    redis=app.state.redis; await ingest(update(),redis)
    async with Session.begin() as db:
        member=await db.get(Member,(peer.workspace_id,peer.user_id));member.role='viewer'
    await ingest(update(2),redis)
    send=AsyncMock();await deliver(send)
    send.assert_not_awaited()
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run))==1
        assert (await db.scalar(select(TelegramDelivery))).status=='cancelled'


async def test_webhook_secret_size_and_disabled(client,peer,monkeypatch):
    assert (await client.post('/v1/telegram/webhook',json=update())).status_code==403
    headers={'X-Telegram-Bot-Api-Secret-Token':'x'*40}
    assert (await client.post('/v1/telegram/webhook',json=update(),headers=headers)).status_code==200
    assert (await client.post('/v1/telegram/webhook',content='x'*65537,headers=headers)).status_code==413
    assert (await client.post('/v1/telegram/webhook',json={'update_id':'oops'},headers=headers)).status_code==422
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    assert (await client.post('/v1/telegram/webhook',json=update(),headers=headers)).status_code==503


async def test_task_runs_through_existing_runtime_and_delivery_deduplicates(client,peer):
    from pao.gateway import Chunk
    class Gateway:
        provider_name='ollama'
        model_name=settings().ollama_model
        async def stream(self,messages,max_tokens=None):
            yield Chunk(text='Telegram synthetic answer')
    await ingest(update(),app.state.redis)
    async with Session() as db:
        run=await db.scalar(select(Run))
        assert run.engine_snapshot and run.engine_snapshot['chat_policy']['version']=='p3-policy-v1'
    await execute_run({'gateway':Gateway()},run.id)
    await collect();await collect()
    send=AsyncMock(return_value={'message_id':99})
    for _ in range(4):await deliver(send)
    assert send.await_count==2
    assert 'Telegram synthetic answer' in str(send.call_args_list)
    async with Session() as db:
        assert (await db.get(Run,run.id)).status=='completed'


@pytest.mark.parametrize('foreign',['sme','member'])
async def test_legacy_telegram_admission_rejects_foreign_session_atomic(client,identity,peer,foreign):
    from fastapi import HTTPException
    wid=identity['workspace'];headers=identity['other']
    if foreign=='sme':
        async with Session.begin() as db:
            second=Workspace(name='Same owner other SME');db.add(second);await db.flush()
            db.add(Member(workspace_id=second.id,user_id=identity['user_id'],role='owner'));wid=second.id
        headers=identity['owner']
    result=await client.post('/v1/sessions',headers=headers,json={'workspace_id':wid})
    assert result.status_code==201
    async with Session.begin() as db:(await db.get(TelegramPeer,peer.id)).session_id=result.json()['id']
    with pytest.raises(HTTPException) as denied:await ingest(update(),app.state.redis)
    assert denied.value.status_code==403 and denied.value.detail=='telegram_session_scope_mismatch'
    async with Session() as db:
        for model in (Run,TelegramUpdate,TelegramDelivery):
            assert await db.scalar(select(func.count()).select_from(model))==0


async def test_approval_buttons_bound_to_delivered_message_and_identity(client,peer,monkeypatch):
    monkeypatch.setattr(settings(),'tools_enabled',True)
    redis=app.state.redis;await ingest(update(),redis)
    async with Session() as db:run=await db.scalar(select(Run))
    call=await propose(run.id,peer.user_id,'telegram-tool-test',{'name':'email.mock_send','agent':'chief_of_staff','arguments':{'to':'qa@example.test','subject':'Review','body':'Synthetic email'}})
    await collect()
    send=AsyncMock(return_value={'message_id':99})
    await deliver(send);await deliver(send)
    payload={'update_id':2,'callback_query':{'id':'query','from':{'id':12345},'message':{'message_id':98,'chat':{'id':12345,'type':'private'}},'data':f'pao:a:{call.id}:1'}}
    await ingest(payload,redis)
    async with Session() as db:assert (await db.get(ToolCall,call.id)).status=='pending'
    payload['update_id']=3;payload['callback_query']['message']['message_id']=99
    await ingest(payload,redis);await ingest(payload,redis)
    async with Session() as db:assert (await db.get(ToolCall,call.id)).status=='queued'


async def test_uncertain_delivery_not_retried_and_stale_claim_recovered(client,peer):
    await ingest(update(),app.state.redis)
    send=AsyncMock(side_effect=RuntimeError('TOKEN MUST NOT LEAK'))
    await deliver(send);await deliver(send)
    send.assert_awaited_once()
    async with Session.begin() as db:
        row=await db.scalar(select(TelegramDelivery));assert row.status=='unknown' and row.error_code=='delivery_uncertain'
        row.status='sending';row.updated_at=now()-timedelta(minutes=2)
    await deliver(send)
    async with Session() as db:
        row=await db.scalar(select(TelegramDelivery));assert row.status=='unknown' and row.error_code=='delivery_interrupted'


async def test_status_is_scoped_and_no_token(client,peer,identity):
    own=await client.get('/v1/telegram/status',headers=identity['owner'])
    other=await client.get('/v1/telegram/status',headers=identity['other'])
    assert own.json()['allowed_peers']==1 and other.json()['allowed_peers']==0
    assert 'synthetic-token' not in own.text


async def test_old_completed_task_is_delivered_and_unicode_is_split_safely(client,peer):
    from pao.telegram import queue
    await ingest(update(),app.state.redis)
    async with Session.begin() as db:
        run=await db.scalar(select(Run));run.status='completed';run.response='Old task result';run.created_at=now()-timedelta(days=30)
        await queue(db,peer,'unicode-check','😀'*4000)
    await collect()
    async with Session() as db:
        rows=list(await db.scalars(select(TelegramDelivery)))
        assert any('Old task result' in row.payload['text'] for row in rows)
        chunks=[row for row in rows if row.dedup_key.startswith('unicode-check:')]
        assert len(chunks)==3 and all(len(row.payload['text'].encode('utf-16-le'))//2<=3500 for row in chunks)


@pytest.mark.parametrize('action,expected',[('a','queued'),('r','rejected')])
async def test_multipart_approval_uses_actual_button_message(client,peer,monkeypatch,action,expected):
    from pao.models import ToolAudit
    monkeypatch.setattr(settings(),'tools_enabled',True)
    redis=app.state.redis
    await ingest(update(),redis)
    async with Session() as db:
        run=await db.scalar(select(Run))
    call=await propose(run.id,peer.user_id,'multipart-approval',{'name':'email.mock_send','agent':'chief_of_staff',
        'arguments':{'to':'qa@example.test','subject':'Review','body':'😀'*2000}})
    await collect()
    next_message=100
    async def send(method,payload):
        nonlocal next_message
        next_message+=1
        return {'message_id':next_message}
    for _ in range(3):
        await deliver(send)
    async with Session() as db:
        parts=list(await db.scalars(select(TelegramDelivery).where(
            TelegramDelivery.dedup_key.startswith(f'approval:{call.id}:1:')).order_by(TelegramDelivery.dedup_key)))
    assert len(parts)==2 and all(part.status=='sent' for part in parts)
    assert 'reply_markup' not in parts[0].payload and 'reply_markup' in parts[1].payload
    def callback(index,message_id,version=1,sender=12345):
        return {'update_id':index,'callback_query':{'id':str(index),'from':{'id':sender},
            'message':{'message_id':int(message_id),'chat':{'id':12345,'type':'private'}},
            'data':f'pao:{action}:{call.id}:{version}'}}
    # Same proposal but no button, wrong version, or another sender must not work.
    await ingest(callback(2,parts[0].message_id),redis)
    await ingest(callback(3,parts[1].message_id,version=2),redis)
    await ingest(callback(4,parts[1].message_id,sender=999),redis)
    async with Session() as db:
        assert (await db.get(ToolCall,call.id)).status=='pending'
    await ingest(callback(5,parts[1].message_id),redis)
    await ingest(callback(5,parts[1].message_id),redis)
    await ingest(callback(6,parts[1].message_id),redis)
    async with Session() as db:
        result=await db.get(ToolCall,call.id)
        assert result.status==expected and result.version==2
        events=list(await db.scalars(select(ToolAudit.event).where(ToolAudit.tool_call_id==call.id)))
        assert events.count('approval.approve' if action=='a' else 'approval.reject')==1


@pytest.mark.parametrize('code,approval_status,execution_status,event',[
    ('aa','approved','queued','approval.approve'),
    ('ar','rejected','cancelled','approval.reject'),
])
async def test_ads_approval_details_and_decision_never_call_meta(
    client,peer,ads_approval,monkeypatch,code,approval_status,execution_status,event
):
    monkeypatch.setattr(action_service,'MetaClient',lambda *_:pytest.fail('Approval callback must not call Meta'))
    await collect();await collect()
    send=AsyncMock(return_value={'message_id':501})
    await deliver(send)
    async with Session() as db:
        delivery=await db.scalar(select(TelegramDelivery).where(
            TelegramDelivery.dedup_key.startswith(f'ads-approval:{ads_approval}:1:')))
        assert delivery.status=='sent'
        buttons=delivery.payload['reply_markup']['inline_keyboard']
        assert {button['callback_data'].split(':')[1] for row in buttons for button in row}=={'aa','ar','ad'}

    def callback(index,action_code,message_id=501,sender=12345):
        return {'update_id':index,'callback_query':{'id':str(index),'from':{'id':sender},
            'message':{'message_id':message_id,'chat':{'id':12345,'type':'private'}},
            'data':f'pao:{action_code}:{ads_approval}:1'}}

    # Details is read-only; a callback from another identity or message cannot decide.
    await ingest(callback(20,'ad'),app.state.redis)
    await ingest(callback(21,code,sender=999),app.state.redis)
    await ingest(callback(22,code,message_id=999),app.state.redis)
    async with Session() as db:
        assert (await db.get(AdAction,ads_approval)).approval_status=='pending'

    await ingest(callback(23,code),app.state.redis)
    await ingest(callback(23,code),app.state.redis)
    async with Session() as db:
        action=await db.get(AdAction,ads_approval)
        assert action.approval_status==approval_status and action.execution_status==execution_status
        assert action.decision_channel=='telegram' and action.version==2
        events=list(await db.scalars(select(AdActionAudit.event).where(AdActionAudit.action_id==ads_approval)))
        assert events.count(event)==1

    # Terminal execution state is delivered once as a separate result notification.
    if code=='aa':
        async with Session.begin() as db:
            action=await db.get(AdAction,ads_approval);action.execution_status='simulated';action.version+=1
        await collect();await collect()
        async with Session() as db:
            results=list(await db.scalars(select(TelegramDelivery).where(
                TelegramDelivery.dedup_key.startswith(f'ads-result:{ads_approval}:simulated:'))))
            assert len(results)==1
