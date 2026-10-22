"""Inspect the user's cached native connection. GET only; no CLI invocation."""
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from pao.auth import issue_token
from pao.config import settings

WID = 'ef221310-5afc-4c21-9f9e-4aa9bf4b3e79'
UID = '165b1fa6-f443-4f66-bddb-51eb5b6e6fa5'


async def main():
    assert ROOT == Path('F:/PAO-ACOS')
    url = make_url(settings().database_url)
    assert (url.host, url.port, url.database) == ('127.0.0.1', 15432, 'pao_acos_local')
    engine = create_async_engine(url, connect_args={'server_settings': {
        'default_transaction_read_only': 'on', 'statement_timeout': '10000'}})
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SHOW transaction_read_only')) == 'on'
            row = (await db.execute(text('SELECT u.auth_version FROM users u JOIN workspace_members m '
                'ON m.user_id=u.id WHERE u.id=:uid AND m.workspace_id=:wid '
                "AND u.active IS TRUE AND m.role IN ('owner','admin')"), {'uid': UID, 'wid': WID})).one()
            # Diagnostic identity is used only for GET, never user consent/mutations.
            headers = {'Authorization': 'Bearer ' + issue_token(UID, row.auth_version)}
    finally:
        await engine.dispose()
    async with httpx.AsyncClient(trust_env=False, timeout=20) as client:
        response = await client.get(f'http://127.0.0.1:8100/v1/workspaces/{WID}/antigravity-native', headers=headers)
        assert response.status_code == 200
        state = response.json()
        assert state['workspace_id'] == WID and state['actor_id'] == UID
        result = {key: state[key] for key in ('status', 'models', 'observed_at', 'inference_enabled',
            'credentials_stored_in_PAO', 'busy', 'provider_support_confirmed')}
        result['health'] = {path: (await client.get('http://127.0.0.1:8100' + path)).status_code
                            for path in ('/health', '/ready')}
        result['health']['web'] = (await client.get('http://127.0.0.1:3200/')).status_code
        result.update(diagnostic_requests_get_only=True, provider_cli_calls=0, model_prompts=0)
    folder = ROOT / '.runtime' / ('antigravity-connected-check-' + uuid4().hex)
    folder.mkdir()
    with (folder / 'receipt.json').open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
    print(json.dumps({'folder': str(folder), **result}))


if __name__ == '__main__':
    asyncio.run(main())
