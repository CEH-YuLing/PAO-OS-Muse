"""Small independent I/O loop so local inference never blocks Telegram transport."""
import asyncio
import logging
import random
from arq import create_pool
from arq.connections import RedisSettings
from pao.config import settings
from pao.telegram import bot_api, ingest, collect, deliver
from pao.modules.operations.health import BRIDGE_KEY


async def main():
    config = settings()
    if not config.telegram_enabled or not config.telegram_bot_token:
        print('Telegram disabled or missing token; no network calls made.', flush=True)
        return
    if config.telegram_mode not in ('polling','webhook'):
        raise RuntimeError('Invalid Telegram mode')
    # Only one bridge per database, including across hosts.
    from pao.db import engine
    from sqlalchemy import text
    async with engine.connect() as lock:
        if not await lock.scalar(text('SELECT pg_try_advisory_lock(600005)')):
            raise RuntimeError('A Telegram bridge is already running')
        await lock.commit()
        from pao.modules.channels.telegram_helpers import legacy_blocked
        if await legacy_blocked(lock):
            print('Legacy Telegram mapped; global bridge blocked, no provider calls made.',flush=True)
            return
        redis = await create_pool(RedisSettings.from_dsn(config.redis_url))
        try:
            info = await bot_api('getWebhookInfo', {})
            if config.telegram_mode == 'polling' and info.get('url'):
                raise RuntimeError('Webhook is configured; remove it explicitly before polling')
            offset = 0
            failures = 0
            print('Telegram bridge ready', flush=True)
            while True:
                try:
                    if config.telegram_mode == 'polling':
                        updates = await bot_api('getUpdates', {'offset':offset, 'timeout':0,'limit':20,'allowed_updates':['message','callback_query']})
                        for update in updates:
                            callback_id = await ingest(update, redis)
                            if callback_id:
                                try:
                                    await bot_api('answerCallbackQuery', {'callback_query_id':callback_id})
                                except RuntimeError:
                                    pass
                            offset = update['update_id'] + 1
                    await collect()
                    from pao.modules.channels.service import send_one
                    async def send_channel(payload):
                        from pao.telegram import TelegramRateLimited
                        from pao.modules.channels.service import RetryableDelivery
                        try:return await bot_api('sendMessage',payload)
                        except TelegramRateLimited:raise RetryableDelivery() from None
                    await send_one(send_channel)
                    for _ in range(2):
                        await deliver()
                        await asyncio.sleep(1)
                    await redis.set(BRIDGE_KEY, 'alive', ex=15)
                    failures = 0
                    await asyncio.sleep(2)
                except Exception:
                    try:
                        await redis.delete(BRIDGE_KEY)
                    except Exception:
                        pass
                    # Never print provider URL/token or incoming private message.
                    print('Telegram temporarily unavailable; inspect local status and configuration.', flush=True)
                    failures = min(failures + 1, 5)
                    await asyncio.sleep(min(60, 2 ** failures) + random.uniform(0, 1))
        finally:
            try:
                await redis.delete(BRIDGE_KEY)
            except Exception:
                pass
            await redis.aclose()


logging.getLogger('httpx').setLevel(logging.WARNING)
if __name__ == '__main__':
    asyncio.run(main())
