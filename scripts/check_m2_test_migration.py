"""Roundtrip only the additive M2 column on dedicated pao_test, never local DB."""
import asyncio
import os
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from pao.config import settings


async def check(url, expected):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            revision = await db.scalar(text('SELECT version_num FROM alembic_version'))
            exists = await db.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='task_attempts' AND column_name='skill_artifact'"))
            assert revision == expected and exists == (1 if expected == '0024' else 0)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    test_url = settings().database_url.rsplit('/', 1)[0] + '/pao_test'
    assert test_url.endswith('/pao_test')
    env = {**os.environ, 'DATABASE_URL': test_url, 'PAO_TEST_DATABASE_URL': test_url}
    asyncio.run(check(test_url, '0024'))
    try:
        subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', '0023'], env=env, check=True)
        asyncio.run(check(test_url, '0023'))
    finally:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0024'], env=env, check=True)
    asyncio.run(check(test_url, '0024'))
    print('PASS migration 0024 -> 0023 -> 0024 on pao_test only; archive column restored')
