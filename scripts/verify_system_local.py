"""Read-only final system snapshot for the local PAO deployment."""
import asyncio
import ctypes
import json
import re
from pathlib import Path

import httpx
from sqlalchemy import text

from pao.auth import issue_token
from pao.config import settings
from pao.db import engine


async def main() -> None:
    async with engine.connect() as db:
        user = await db.scalar(text("select id from users order by created_at limit 1"))
        revision = await db.scalar(text("select version_num from alembic_version"))
        table_count = await db.scalar(
            text("select count(*) from information_schema.tables where table_schema='public'")
        )
    headers = {"Authorization": "Bearer " + issue_token(str(user))}
    async with httpx.AsyncClient(timeout=15) as client:
        ready = await client.get("http://127.0.0.1:8000/ready")
        web = await client.get("http://127.0.0.1:3100/")
        assets = sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))', web.text)))
        asset_codes = [(await client.get("http://127.0.0.1:3100" + item)).status_code for item in assets]
        openapi = (await client.get("http://127.0.0.1:8000/openapi.json")).json()
        telegram = (await client.get("http://127.0.0.1:8000/v1/telegram/status", headers=headers)).json()
        voice = (await client.get("http://127.0.0.1:8000/v1/voice/status", headers=headers)).json()
        automation = (await client.get("http://127.0.0.1:8000/v1/automation/status", headers=headers)).json()
        autopilot = (await client.get("http://127.0.0.1:8000/v1/ads/autopilot/status", headers=headers)).json()

    process_file = Path(".runtime/processes.json")
    configured_processes = json.loads(process_file.read_text(encoding="utf-8"))
    process_alive = {}
    kernel32 = ctypes.windll.kernel32
    for name, record in configured_processes.items():
        handle = kernel32.OpenProcess(0x1000, False, int(record["id"]))
        process_alive[name] = bool(handle)
        if handle:
            kernel32.CloseHandle(handle)

    report = {
        "revision": revision,
        "public_tables": table_count,
        "api_ready": ready.status_code,
        "web": web.status_code,
        "assets_all_200": bool(assets) and all(code == 200 for code in asset_codes),
        "openapi_paths": len(openapi.get("paths", {})),
        "processes": process_alive,
        "telegram": telegram,
        "voice": voice,
        "automation": automation,
        "meta_write_enabled": settings().meta_write_enabled,
        "autopilot_global_enabled": autopilot.get("global_enabled"),
        "provider_write_attempted": False,
    }
    assert revision == "0022"
    # 64 application tables plus Alembic's own version table.
    assert table_count == 65
    assert ready.status_code == web.status_code == 200 and report["assets_all_200"]
    assert report["openapi_paths"] == 101
    assert all(process_alive.values()), process_alive
    assert telegram.get("enabled") and telegram.get("configured")
    assert voice.get("enabled") and voice.get("stt_ready") and voice.get("tts_ready")
    assert automation.get("enabled") and automation.get("namespace") == "default"
    assert not settings().meta_write_enabled and not autopilot.get("global_enabled")
    Path(".runtime/system-health.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
