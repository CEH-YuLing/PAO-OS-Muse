"""Create fresh local-only credentials for the isolated ACOS smoke environment."""
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    if '--update-local-ports' in sys.argv:
        original = target.read_text(encoding='utf-8')
        if 'pao_acos_local' not in original:
            raise SystemExit('Refusing to edit a non-ACOS environment.')
        target.write_text(original.replace(':55432/pao_acos_local', ':15432/pao_acos_local')
                          .replace(':56379/0', ':16379/0'), encoding='utf-8')
        raise SystemExit('Updated isolated local ports; credentials preserved.')
    raise SystemExit('.env already exists; left unchanged')
pg, redis, jwt = (secrets.token_hex(32) for _ in range(3))
target.write_text(
    f'DATABASE_URL=postgresql+asyncpg://pao:{pg}@127.0.0.1:15432/pao_acos_local\n'
    f'POSTGRES_PASSWORD={pg}\nREDIS_PASSWORD={redis}\n'
    f'REDIS_URL=redis://:{redis}@127.0.0.1:16379/0\nJWT_SECRET={jwt}\n'
    'POSTGRES_USER=pao\nPOSTGRES_DB=pao_acos_local\n'
    'TELEGRAM_ENABLED=false\nMETA_ENABLED=false\nMETA_WRITE_ENABLED=false\n'
    'GOOGLE_ADS_ENABLED=false\nADS_AUTOPILOT_GLOBAL_ENABLED=false\n'
    'TEMPORAL_ENABLED=false\nVOICE_ENABLED=false\n'
    'OLLAMA_URL=http://127.0.0.1:11434\n'
    'OLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M\n',
    encoding='utf-8',
)
print('Created ignored .env for isolated ACOS local services; no secrets printed.')
