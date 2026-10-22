"""Read-only Phase 10 post-deployment verification; never prints credentials."""
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
        user=await db.scalar(text('select id from users order by created_at limit 1'))
        workspace=await db.scalar(text('select workspace_id from workspace_members where user_id=:uid limit 1'),{'uid':user})
        revision=await db.scalar(text('select version_num from alembic_version'))
        counts={table:await db.scalar(text(f'select count(*) from {table}')) for table in
            ('ad_targets','ads_rules','ad_intelligence_runs','ad_anomalies','ad_recommendations')}
    headers={'Authorization':'Bearer '+issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready=(await client.get('http://127.0.0.1:8000/ready')).status_code
        page=await client.get('http://127.0.0.1:3100/')
        assets=sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))',page.text)))
        asset_codes=[(await client.get('http://127.0.0.1:3100'+path)).status_code for path in assets]
        paths=[f'/v1/ads/targets?workspace_id={workspace}',f'/v1/ads/rules?workspace_id={workspace}&account_id=act_1',
            f'/v1/ads/anomalies?workspace_id={workspace}&account_id=act_1',f'/v1/ads/recommendations?workspace_id={workspace}&account_id=act_1']
        responses=[await client.get('http://127.0.0.1:8000'+path,headers=headers) for path in paths]
        agents=(await client.get('http://127.0.0.1:8000/v1/agents',headers=headers)).json()
    report={'revision':revision,'ready':ready,'web':page.status_code,'asset_count':len(assets),
        'assets_all_200':bool(assets) and all(code==200 for code in asset_codes),
        'intelligence_api':[row.status_code for row in responses],
        'intelligence_empty':all(row.json()==[] for row in responses),'performance_analyst_registered':
        any(row['key']=='performance_analyst' and row['enabled'] for row in agents),'intelligence_counts':counts}
    assert report['revision']=='0009' and report['ready']==report['web']==200
    assert report['assets_all_200'] and report['intelligence_api']==[200,200,200,200]
    assert report['intelligence_empty'] and report['performance_analyst_registered'] and all(value==0 for value in counts.values())
    Path('.runtime/phase-10-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));await engine.dispose()


asyncio.run(main())
