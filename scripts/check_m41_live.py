"""Read-only M4.1 local rollout gate; never emit business events."""
import asyncio
from pathlib import Path

import httpx
from sqlalchemy import text

from pao.config import ROOT, settings
from pao.db import engine


async def main():
    config = settings()
    if ROOT.resolve() != Path('F:/PAO-ACOS') or not config.database_url.endswith('/pao_acos_local'):
        raise SystemExit('ACOS local only')
    assert not config.business_events_enabled, 'Live producer must remain disabled'
    for flag in ('meta_write_enabled', 'telegram_enabled', 'temporal_enabled',
                 'ads_autopilot_global_enabled', 'meta_autopilot_enabled'):
        assert not getattr(config, flag), flag
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) == '0035'
            assert await db.scalar(text('SELECT count(*) FROM business_events')) == 0
            assert await db.scalar(text('SELECT count(*) FROM business_outbox')) == 0
        async with httpx.AsyncClient(timeout=10) as client:
            for url in ('http://127.0.0.1:8100/health', 'http://127.0.0.1:8100/ready',
                        'http://127.0.0.1:3200/'):
                assert (await client.get(url)).status_code == 200, url
        print('PASS M4.1 live:0035; producer disabled; zero events/outbox; API/Web200; outbound flags off')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
