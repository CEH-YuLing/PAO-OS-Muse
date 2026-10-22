"""Read-only Phase 18 verification; never records microphone or persists content."""
import asyncio,json,re
from pathlib import Path
import httpx
from sqlalchemy import text
from pao.auth import issue_token
from pao.db import engine
from pao.voice import engine as voice_engine
from pao.config import settings
async def main():
    async with engine.connect() as db:
        user=await db.scalar(text('select id from users order by created_at limit 1'));revision=await db.scalar(text('select version_num from alembic_version'));count=await db.scalar(text('select count(*) from voice_interactions'))
    headers={'Authorization':'Bearer '+issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready=(await client.get('http://127.0.0.1:8000/ready')).status_code;page=await client.get('http://127.0.0.1:3100/')
        assets=sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))',page.text)));codes=[(await client.get('http://127.0.0.1:3100'+x)).status_code for x in assets]
        status=(await client.get('http://127.0.0.1:8000/v1/voice/status',headers=headers)).json();autopilot=(await client.get('http://127.0.0.1:8000/v1/ads/autopilot/status',headers=headers)).json();automation=(await client.get('http://127.0.0.1:8000/v1/automation/status',headers=headers)).json()
    report={'revision':revision,'ready':ready,'web':page.status_code,'assets_all_200':bool(assets) and all(x==200 for x in codes),'voice_interactions':count,'voice_status':status,'automation_status':automation,'meta_write_enabled':settings().meta_write_enabled,'autopilot_global_enabled':autopilot.get('global_enabled'),'provider_write_attempted':False}
    assert revision=='0017' and ready==page.status_code==200 and report['assets_all_200'];assert status['enabled'] and status['stt_ready'] and status['tts_ready'];assert automation['enabled'] and automation['namespace']=='default';assert not settings().meta_write_enabled and not autopilot.get('global_enabled')
    Path('.runtime/phase-18-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));await engine.dispose()
asyncio.run(main())
