"""Read-only smoke check against the running PAO API and its real local database."""

import asyncio
import json

import httpx
from sqlalchemy import select

from pao.auth import issue_token
from pao.db import Session, engine
from pao.models import Member, User


async def main() -> None:
    async with Session() as db:
        identity = (
            await db.execute(
                select(User.id, Member.workspace_id)
                .join(Member, Member.user_id == User.id)
                .where(User.active.is_(True))
                .order_by(User.created_at)
                .limit(1)
            )
        ).one()

    headers = {"Authorization": f"Bearer {issue_token(str(identity.id))}"}
    base = "http://127.0.0.1:8000"
    async with httpx.AsyncClient(base_url=base, timeout=20, trust_env=False) as client:
        invalid_login = await client.post(
            "/v1/auth/token",
            json={"email": "baseline-invalid@example.test", "password": "invalid-baseline-password"},
        )
        me = await client.get("/v1/me", headers=headers)
        sessions = await client.get(
            "/v1/sessions", params={"workspace_id": str(identity.workspace_id)}, headers=headers
        )
        tasks = await client.get(
            "/v1/tasks", params={"workspace_id": str(identity.workspace_id)}, headers=headers
        )
        memories = await client.get(
            "/v1/memory", params={"workspace_id": str(identity.workspace_id)}, headers=headers
        )
        telegram = await client.get("/v1/telegram/status", headers=headers)

        responses = [me, sessions, tasks, memories, telegram]
        assert all(response.status_code == 200 for response in responses)
        assert invalid_login.status_code == 401

        session_rows = sessions.json()
        detail = None
        if session_rows:
            detail_response = await client.get(f"/v1/sessions/{session_rows[0]['id']}", headers=headers)
            assert detail_response.status_code == 200
            detail = detail_response.json()

    telegram_status = telegram.json()
    assert telegram_status.get("enabled") and telegram_status.get("configured")
    report = {
        "invalid_login_rejected": True,
        "bearer_auth_accepted": bool(me.json().get("workspaces")),
        "sessions": len(session_rows),
        "session_detail_checked": detail is not None,
        "messages_in_latest_session": len(detail.get("messages", [])) if detail else 0,
        "tasks": len(tasks.json()),
        "memories": len(memories.json()),
        "telegram": {
            "enabled": telegram_status.get("enabled"),
            "configured": telegram_status.get("configured"),
            "mode": telegram_status.get("mode"),
            "allowed_peers": telegram_status.get("allowed_peers"),
            "delivery_issues": len(telegram_status.get("delivery_issues", [])),
        },
    }
    print(json.dumps(report, ensure_ascii=True))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
