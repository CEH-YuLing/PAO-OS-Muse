"""Cross-worker local inference cap via PostgreSQL connection-scoped lock.

Crash/cancel/connection close releases the lock. No file locks or global PID kills.
"""
import asyncio
import inspect
from functools import wraps
from contextlib import asynccontextmanager
from sqlalchemy import text
from ...config import settings


@asynccontextmanager
async def local_slot():
    if not settings().chat_features_enabled:
        yield
        return
    from ...db import engine
    async with engine.connect() as db:
        async with db.begin():
            acquired = False
            try:
                async with asyncio.timeout(3):
                    while not acquired:
                        acquired = bool(await db.scalar(text('SELECT pg_try_advisory_xact_lock(7030701)')))
                        if not acquired: await asyncio.sleep(.05)
            except TimeoutError:
                from ..engines.contract import EngineFailure
                raise EngineFailure('engine_local_busy') from None
            yield


def limited(method):
    if inspect.isasyncgenfunction(method):
        @wraps(method)
        async def stream(*args, **kwargs):
            async with local_slot():
                source = method(*args, **kwargs)
                try:
                    async for item in source:
                        yield item
                finally:
                    await source.aclose()
        return stream
    @wraps(method)
    async def call(*args, **kwargs):
        async with local_slot():
            return await method(*args, **kwargs)
    return call
