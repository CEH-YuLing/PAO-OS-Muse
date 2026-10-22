"""Print readiness flags/counts only; never expose credentials or call Meta."""
import asyncio
import json
from sqlalchemy import func, select
from pao.config import settings
from pao.db import Session, engine
from pao.models import MetaConnection, AdReport, now


async def main():
    config = settings()
    if not config.database_url.endswith('/pao_acos_local'):
        raise SystemExit('Requires isolated ACOS local DB')
    try:
        async with Session() as db:
            connected = await db.scalar(select(func.count(MetaConnection.id)).where(
                MetaConnection.status == 'connected', MetaConnection.expires_at > now()))
            reports = await db.scalar(select(func.count(AdReport.id)))
        print(json.dumps({'meta_enabled': config.meta_enabled,
            'meta_write_enabled': config.meta_write_enabled,
            'app_id_present': bool(config.meta_app_id),
            'app_secret_present': bool(config.meta_app_secret),
            'unexpired_connections': connected, 'saved_reports': reports,
            'external_calls_made': False}))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
