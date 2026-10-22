"""Read private-chat ID candidates without acknowledging or deleting updates."""
import asyncio
from sqlalchemy import text
from pao.db import engine
from pao.telegram import bot_api
from pao.config import settings

async def main():
    if not settings().telegram_bot_token:
        raise SystemExit('Store token with setup_telegram.py --token first')
    async with engine.connect() as db:
        if not await db.scalar(text('SELECT pg_try_advisory_lock(600005)')):
            raise SystemExit('Stop the Telegram bridge before reading setup candidates')
        info=await bot_api('getWebhookInfo',{})
        if info.get('url'):
            raise SystemExit('Webhook configured; use a known Telegram numeric ID')
        updates=await bot_api('getUpdates',{'timeout':0,'limit':100,'allowed_updates':['message','callback_query']})
        candidates=set()
        for update in updates:
            message=update.get('message',{})
            sender=message.get('from',{});chat=message.get('chat',{})
            if chat.get('type')=='private' and not sender.get('is_bot') and sender.get('id')==chat.get('id'):
                candidates.add((sender['id'],chat['id']))
        for user_id,chat_id in sorted(candidates):
            print(f'user_id={user_id} chat_id={chat_id}')
        if not candidates:
            print('Open your bot chat, send /start, then run this command again.')
        print('Only whitelist your own verified ID. No permissions were granted.')
    await engine.dispose()

asyncio.run(main())
