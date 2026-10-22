"""Read-only Phase 11 post-deployment verification; never performs a Meta write."""
import asyncio
import json
import re
from pathlib import Path

import httpx
from sqlalchemy import text

from pao.auth import issue_token
from pao.db import engine


async def main():
    async with engine.connect() as db:
        user = await db.scalar(text('select id from users order by created_at limit 1'))
        workspace = await db.scalar(
            text('select workspace_id from workspace_members where user_id=:uid limit 1'),
            {'uid': user},
        )
        revision = await db.scalar(text('select version_num from alembic_version'))
        counts = {
            table: await db.scalar(text(f'select count(*) from {table}'))
            for table in ('ads_actions', 'ads_action_audits')
        }

    headers = {'Authorization': 'Bearer ' + issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready = (await client.get('http://127.0.0.1:8000/ready')).status_code
        page = await client.get('http://127.0.0.1:3100/')
        assets = sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))', page.text)))
        asset_codes = [
            (await client.get('http://127.0.0.1:3100' + path)).status_code
            for path in assets
        ]
        status_response = await client.get(
            'http://127.0.0.1:8000/v1/ads/write-status', headers=headers
        )
        actions_response = await client.get(
            f'http://127.0.0.1:8000/v1/ads/actions?workspace_id={workspace}',
            headers=headers,
        )

    write_status = status_response.json()
    report = {
        'revision': revision,
        'ready': ready,
        'web': page.status_code,
        'asset_count': len(assets),
        'assets_all_200': bool(assets) and all(code == 200 for code in asset_codes),
        'write_status_api': status_response.status_code,
        'write_enabled': write_status.get('enabled'),
        'write_mode': write_status.get('mode'),
        'dry_run_default': write_status.get('dry_run_default'),
        'actions_api': actions_response.status_code,
        'actions_empty': actions_response.json() == [],
        'action_counts': counts,
        'provider_write_attempted': False,
    }
    assert report['revision'] == '0010'
    assert report['ready'] == report['web'] == 200
    assert report['assets_all_200']
    assert report['write_status_api'] == report['actions_api'] == 200
    assert report['write_enabled'] is False
    assert report['write_mode'] == 'copilot' and report['dry_run_default'] is True
    assert report['actions_empty'] and all(value == 0 for value in counts.values())
    Path('.runtime/phase-11-health.json').write_text(
        json.dumps(report, indent=2), encoding='utf-8'
    )
    print(json.dumps(report))
    await engine.dispose()


asyncio.run(main())
