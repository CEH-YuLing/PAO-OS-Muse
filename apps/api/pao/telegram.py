"""Telegram is a transport for the existing run and approval services, never an agent."""
import asyncio
import hmac
import json
from datetime import timedelta
from uuid import UUID
from types import SimpleNamespace
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, String, and_, or_
from sqlalchemy.dialects.postgresql import insert
from .auth import principal, Principal, rate_limit
from .config import settings
from .db import Session
from .models import (TelegramPeer, TelegramUpdate, TelegramDelivery, User, Member, ChatSession, Run,
    ToolCall, AdAction, AdsAutopilotPolicy, Goal, Task, now)
from .tool_gateway import decide
from .ads_actions import decide_action

router = APIRouter(prefix='/v1/telegram', tags=['telegram'])


# Compatibility aliases for existing router/bridge/tests.
from .modules.channels.telegram_helpers import permitted, queue,legacy_blocked


def action_text(action):
    before=json.dumps(action.before_state,ensure_ascii=False,sort_keys=True)
    proposed=json.dumps(action.proposed_state,ensure_ascii=False,sort_keys=True)
    mode='DRY-RUN' if action.dry_run else 'LIVE WRITE'
    return (f'PAO · ADS APPROVAL · {mode}\n{action.action_type} {action.resource_type} {action.resource_id}\n'
        f'Account: {action.account_id}\nBefore: {before}\nProposed: {proposed}\nReason: {action.reason}\n'
        f'Hết hạn: {action.approval_expires_at.isoformat()}\nVersion: {action.version}')


async def ingest(update, redis):
    if not settings().telegram_enabled:
        raise HTTPException(503, 'telegram_disabled')
    if not isinstance(update, dict) or type(update.get('update_id')) is not int or not 0 <= update['update_id'] < 2**63:
        raise HTTPException(422, 'invalid_update')
    from .modules.channels.service import telegram_ingest
    if await telegram_ingest(update,redis):return
    callback = update.get('callback_query')
    if callback is not None and not isinstance(callback, dict):
        return
    message = callback.get('message', {}) if isinstance(callback, dict) else update.get('message', {})
    if not isinstance(message, dict):
        return
    sender = callback.get('from', {}) if isinstance(callback, dict) else message.get('from', {})
    chat = message.get('chat', {})
    if not isinstance(sender, dict) or not isinstance(chat, dict) or chat.get('type') != 'private' or sender.get('is_bot'):
        return
    async with Session() as db:
        peer = await db.scalar(select(TelegramPeer).where(TelegramPeer.telegram_user_id == str(sender.get('id')),
            TelegramPeer.chat_id == str(chat.get('id')),TelegramPeer.connection_id.is_(None)).with_for_update())
        if not await permitted(db, peer):
            return
        if await db.scalar(select(TelegramUpdate.id).where(TelegramUpdate.update_id==update['update_id'],TelegramUpdate.connection_id.is_(None))):
            return
        await rate_limit(redis, 'telegram-in', peer.id, 20, 60)
        receipt = TelegramUpdate(update_id=update['update_id'], peer_id=peer.id)
        db.add(receipt)
        if callback:
            data = callback.get('data', '')
            try:
                prefix, action_code, object_id, version = data.split(':')
                UUID(object_id); version = int(version)
                if prefix != 'pao' or action_code not in ('a','r','aa','ar','ad'):
                    raise ValueError()
                key='approval' if action_code in ('a','r') else 'ads-approval'
                delivery = await db.scalar(select(TelegramDelivery).where(TelegramDelivery.peer_id == peer.id,
                    TelegramDelivery.dedup_key.startswith(f'{key}:{object_id}:{version}:'),
                    TelegramDelivery.status == 'sent', TelegramDelivery.message_id == str(message.get('message_id'))))
                # A long proposal can span several messages. Only the delivered
                # part that actually carries this button may authorize a decision.
                buttons = delivery.payload.get('reply_markup', {}).get('inline_keyboard', []) if delivery else []
                if not delivery or not any(button.get('callback_data') == data for row in buttons for button in row):
                    raise ValueError()
                if action_code in ('a','r'):
                    call = await db.get(ToolCall, object_id)
                    if not call or call.user_id != peer.user_id or call.workspace_id != peer.workspace_id:raise ValueError()
                    await decide(object_id, peer.user_id, 'approve' if action_code == 'a' else 'reject', version)
                    reply = 'Đã ghi nhận quyết định. Kết quả sẽ được thông báo sau khi thực thi.'
                else:
                    ads_action=await db.get(AdAction,object_id)
                    if not ads_action or ads_action.workspace_id!=peer.workspace_id:raise ValueError()
                    if action_code=='ad':reply=action_text(ads_action)
                    else:
                        result=await decide_action(object_id,peer.user_id,'approve' if action_code=='aa' else 'reject',version,'telegram')
                        reply=('Đã duyệt Ads action và đưa vào hàng đợi thực thi.' if result.approval_status=='approved'
                            else f'Ads approval: {result.approval_status}. Không có Meta write được thực hiện.')
            except (ValueError, TypeError, AttributeError, HTTPException):
                reply = 'Không thể duyệt: đề xuất đã thay đổi, hết hạn hoặc bạn không có quyền.'
            await queue(db, peer, f'callback:{update["update_id"]}', reply)
        else:
            content = message.get('text', '')
            if not isinstance(content, str):
                content = ''
            content = content.strip()
            if content in ('/start','/help'):
                await queue(db, peer, f'help:{update["update_id"]}', 'PAO: gửi yêu cầu bằng văn bản để giao việc. /new mở hội thoại mới; /status xem trạng thái; /tasks xem task; /goals xem mục tiêu; /cancel hủy yêu cầu đang chạy. Email/lịch hiện chỉ mô phỏng và cần bạn duyệt.')
            elif content == '/new':
                peer.session_id = None
                await queue(db, peer, f'new:{update["update_id"]}', 'Lượt tiếp theo sẽ dùng hội thoại mới. Yêu cầu cũ vẫn tiếp tục nếu đang chạy.')
            elif content in ('/cancel','/status'):
                run = await db.scalar(select(Run).where(Run.session_id == peer.session_id).order_by(Run.created_at.desc()).limit(1).with_for_update())
                if content == '/cancel' and run and run.status in ('queued','running'):
                    run.cancel_requested = True
                await queue(db, peer, f'status:{update["update_id"]}', f'Yêu cầu: {run.status}' + ('; đã yêu cầu hủy.' if run.cancel_requested else '') if run else 'Chưa có yêu cầu trong hội thoại này.')
            elif content == '/tasks':
                tasks = list(await db.scalars(select(Task).where(
                    Task.workspace_id == peer.workspace_id,
                    Task.status.notin_(('completed', 'cancelled')),
                ).order_by(Task.updated_at.desc()).limit(10)))
                text = 'Task đang mở:\n' + '\n'.join(
                    f'• {task.title} · {task.status} · {task.progress}%' for task in tasks
                ) if tasks else 'Không có task đang mở.'
                await queue(db, peer, f'tasks:{update["update_id"]}', text)
            elif content == '/goals':
                goals = list(await db.scalars(select(Goal).where(
                    Goal.workspace_id == peer.workspace_id,
                    Goal.status.in_(('draft', 'active', 'failed')),
                ).order_by(Goal.updated_at.desc()).limit(10)))
                text = 'Goal hiện tại:\n' + '\n'.join(
                    f'• {goal.title} · {goal.status}' for goal in goals
                ) if goals else 'Chưa có goal đang mở.'
                await queue(db, peer, f'goals:{update["update_id"]}', text)
            elif not content or len(content) > 2000 or content.startswith('/'):
                await queue(db, peer, f'invalid:{update["update_id"]}', 'Hãy gửi văn bản từ 1 đến 2000 ký tự hoặc dùng /help. Chưa hỗ trợ tệp/giọng nói.')
            else:
                if not peer.session_id:
                    session = ChatSession(workspace_id=peer.workspace_id, user_id=peer.user_id, title='Telegram', memory_enabled=False)
                    db.add(session); await db.flush(); peer.session_id = session.id
                # Lock the same conversation as the web transport, preserving one active run.
                session=await db.scalar(select(ChatSession).where(ChatSession.id == peer.session_id,
                    ChatSession.workspace_id == peer.workspace_id,ChatSession.user_id == peer.user_id).with_for_update())
                if not session:
                    raise HTTPException(403,'telegram_session_scope_mismatch')
                active = await db.scalar(select(Run.id).where(Run.session_id == peer.session_id, Run.status.in_(('queued','running'))))
                if active:
                    await queue(db, peer, f'busy:{update["update_id"]}', 'PAO đang xử lý yêu cầu trước. Hãy chờ kết quả hoặc dùng /cancel.')
                else:
                    # New requests share Web/Channels' owned admission, immutable
                    # engine/accounting/Brain pins and atomic dedup transaction.
                    # Never repair or repin old unaccounted queued work here.
                    from .modules.conversations.requests import admit_run
                    from .schemas import RunCreate
                    request=SimpleNamespace(state=SimpleNamespace(pao_retry_parent=None),
                        app=SimpleNamespace(state=SimpleNamespace(redis=redis)))
                    run=await admit_run(RunCreate(session_id=session.id,
                        request_key=f'telegram-{update["update_id"]}',message=content),
                        request,Principal(peer.user_id,0),db,commit=False)
                    receipt.run_id = run.id
                    await queue(db, peer, f'accepted:{run.id}', 'Đã nhận yêu cầu. PAO sẽ gửi kết quả khi hoàn tất.')
        await db.commit()
        return callback.get('id') if callback else None


async def collect():
    async with Session.begin() as db:
        if await legacy_blocked(db):return
        peers = list(await db.scalars(select(TelegramPeer).where(TelegramPeer.enabled.is_(True),TelegramPeer.connection_id.is_(None))))
        for peer in peers:
            if not await permitted(db, peer):
                continue
            final_exists = select(TelegramDelivery.id).where(
                TelegramDelivery.dedup_key == 'result:' + Run.id.cast(String) + ':0').exists()
            approval_exists = select(TelegramDelivery.id).where(TelegramDelivery.dedup_key ==
                'approval:' + ToolCall.id.cast(String) + ':' + ToolCall.version.cast(String) + ':0').exists()
            tool_result_exists = select(TelegramDelivery.id).where(TelegramDelivery.dedup_key ==
                'tool-result:' + ToolCall.id.cast(String) + ':0').exists()
            tools_waiting = select(ToolCall.id).where(ToolCall.run_id == Run.id, or_(
                and_(ToolCall.status == 'pending', ~approval_exists),
                and_(ToolCall.status.in_(('completed','failed','cancelled','rejected','expired','unknown')), ~tool_result_exists))).exists()
            runs = list(await db.scalars(select(Run).join(TelegramUpdate, TelegramUpdate.run_id == Run.id)
                .where(TelegramUpdate.peer_id == peer.id, or_(tools_waiting,
                    and_(Run.status.in_(('completed','failed','cancelled')), ~final_exists)))
                .order_by(Run.created_at).limit(100)))
            for run in runs:
                if run.status in ('completed','failed','cancelled'):
                    await queue(db, peer, f'result:{run.id}', f'PAO · {run.status}\n' + (run.response or 'Yêu cầu kết thúc mà chưa có câu trả lời.'))
                calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == run.id)))
                for call in calls:
                    if call.status == 'pending':
                        markup = {'inline_keyboard':[[{'text':'Duyệt mô phỏng','callback_data':f'pao:a:{call.id}:{call.version}'},
                            {'text':'Từ chối','callback_data':f'pao:r:{call.id}:{call.version}'}]]}
                        detail = f'PAO · Cần phê duyệt {call.name}\nChỉ mô phỏng, không gửi email/tạo lịch thật. Hết hạn sau 24 giờ.\n' + '\n'.join(f'{key}: {value}' for key,value in call.arguments.items())
                        await queue(db, peer, f'approval:{call.id}:{call.version}', detail, markup)
                    elif call.status in ('completed','failed','cancelled','rejected','expired','unknown'):
                        await queue(db, peer, f'tool-result:{call.id}', f'Công cụ {call.name}: {call.status}\n' + ('Mô phỏng; không thực hiện hành động bên ngoài.' if call.name != 'web.search' else 'Kết quả tìm kiếm được lưu cùng yêu cầu.'))
            member=await db.get(Member,(peer.workspace_id,peer.user_id))
            if member and member.role in ('owner','admin'):
                actions=list(await db.scalars(select(AdAction).where(AdAction.workspace_id==peer.workspace_id,
                    (AdAction.approval_status=='pending') | (AdAction.execution_status.in_(('simulated','succeeded','failed','unknown','stale','cancelled'))))
                    .order_by(AdAction.created_at).limit(100)))
                for action in actions:
                    if action.approval_status=='pending':
                        exists=await db.scalar(select(TelegramDelivery.id).where(TelegramDelivery.peer_id==peer.id,
                            TelegramDelivery.dedup_key.startswith(f'ads-approval:{action.id}:{action.version}:')))
                        if not exists:
                            approve='Duyệt dry-run' if action.dry_run else 'APPROVE GHI META'
                            markup={'inline_keyboard':[[{'text':approve,'callback_data':f'pao:aa:{action.id}:{action.version}'},
                                {'text':'Từ chối','callback_data':f'pao:ar:{action.id}:{action.version}'}],
                                [{'text':'Chi tiết','callback_data':f'pao:ad:{action.id}:{action.version}'}]]}
                            await queue(db,peer,f'ads-approval:{action.id}:{action.version}',action_text(action),markup)
                    else:
                        key=f'ads-result:{action.id}:{action.execution_status}'
                        exists=await db.scalar(select(TelegramDelivery.id).where(TelegramDelivery.peer_id==peer.id,
                            TelegramDelivery.dedup_key==key+':0'))
                        if not exists:
                            await queue(db,peer,key,f'PAO · Ads action {action.action_type}: {action.execution_status}\n'
                                f'Resource: {action.resource_type} {action.resource_id}\nError: {action.error_code or "—"}')
                frozen=list(await db.scalars(select(AdsAutopilotPolicy).where(
                    AdsAutopilotPolicy.workspace_id==peer.workspace_id,AdsAutopilotPolicy.emergency_frozen.is_(True))))
                for policy in frozen:
                    await queue(db,peer,f'autopilot-freeze:{policy.id}:{policy.version}',
                        f'PAO · AUTOPILOT EMERGENCY FREEZE\nAccount: {policy.account_id}\n'
                        f'Reason: {policy.freeze_reason or "unspecified"}\nMode: ADVISOR · Workspace: HALTED\nKhông tiếp tục Ads write tự động.')


class TelegramRateLimited(RuntimeError):
    """Positive provider rejection: safe to back off, unlike missing ACK."""

async def bot_api(method, payload):
    async with Session() as db:
        if await legacy_blocked(db):raise RuntimeError('telegram_legacy_mapped')
    # Token-bearing URL and transport exception must never enter application logs.
    try:
        async with httpx.AsyncClient(timeout=35, trust_env=False, follow_redirects=False) as client:
            response = await client.post(f'https://api.telegram.org/bot{settings().telegram_bot_token}/{method}', json=payload)
            data = response.json()
            if response.status_code==429 and isinstance(data,dict) and data.get('ok') is False and data.get('error_code')==429:
                raise TelegramRateLimited('telegram_rate_limited')
            if response.status_code != 200 or not data.get('ok'):
                raise ValueError()
            return data['result']
    except TelegramRateLimited:raise
    except Exception:
        raise RuntimeError('telegram_transport_unavailable') from None


async def deliver(send=bot_api):
    if not settings().telegram_enabled or not settings().telegram_bot_token:
        return
    async with Session.begin() as db:
        # A mapped namespace permanently retires host legacy transport. Do not
        # claim, cancel or reconcile its pre-mapping delivery ledger.
        if await legacy_blocked(db):return
        stale = list(await db.scalars(select(TelegramDelivery).where(TelegramDelivery.status == 'sending',
            TelegramDelivery.connection_id.is_(None),
            TelegramDelivery.updated_at < now()-timedelta(seconds=90)).with_for_update(skip_locked=True)))
        for row in stale:
            row.status = 'unknown'; row.error_code = 'delivery_interrupted'
        row = await db.scalar(select(TelegramDelivery).where(TelegramDelivery.status == 'queued')
            .where(TelegramDelivery.connection_id.is_(None))
            .order_by(TelegramDelivery.created_at, TelegramDelivery.id).with_for_update(skip_locked=True).limit(1))
        if not row:
            return
        peer = await db.get(TelegramPeer, row.peer_id)
        if not await permitted(db, peer):
            row.status = 'cancelled'; return
        row.status = 'sending'; row.updated_at = now(); row_id = row.id; payload = row.payload
    try:
        result = await send('sendMessage', payload)
        message_id = str(result['message_id']); error = None
    except Exception:
        message_id = None; error = 'delivery_uncertain'
    async with Session.begin() as db:
        row = await db.get(TelegramDelivery, row_id, with_for_update=True)
        row.status = 'unknown' if error else 'sent'; row.message_id = message_id
        row.error_code = error; row.updated_at = now()


@router.post('/webhook')
async def webhook(request: Request):
    config = settings()
    if not config.telegram_enabled or config.telegram_mode != 'webhook':
        raise HTTPException(503, 'telegram_webhook_disabled')
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if len(config.telegram_webhook_secret) < 32 or not hmac.compare_digest(secret.encode(), config.telegram_webhook_secret.encode()):
        raise HTTPException(403, 'invalid_webhook_secret')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 65536:
            raise HTTPException(413, 'update_too_large')
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(422, 'invalid_update')
    callback_id = await ingest(payload, request.app.state.redis)
    if callback_id:
        try:
            await bot_api('answerCallbackQuery', {'callback_query_id':callback_id})
        except RuntimeError:
            pass
    return {'ok':True}


@router.get('/status')
async def status(who: Principal = Depends(principal)):
    async with Session() as db:
        blocked=await legacy_blocked(db)
        peers = list(await db.scalars(select(TelegramPeer.id).where(TelegramPeer.user_id == who.id, TelegramPeer.enabled.is_(True))))
        issues = list(await db.scalars(select(TelegramDelivery).where(TelegramDelivery.peer_id.in_(peers),
            TelegramDelivery.status.in_(('unknown','failed'))).order_by(TelegramDelivery.created_at.desc()).limit(20)))
    return {'enabled':settings().telegram_enabled and not blocked, 'configured':bool(settings().telegram_bot_token),
        'mode':settings().telegram_mode, 'allowed_peers':len(peers),
        'delivery_issues':[{'id':r.id,'status':r.status,'error_code':r.error_code} for r in issues]}


from .modules.channels.legacy_mapping_api import mount as mount_legacy_mapping
mount_legacy_mapping(router)
