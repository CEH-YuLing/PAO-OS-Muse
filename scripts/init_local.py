"""Create local credentials once; never print secret values."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('.env already exists; left unchanged')
pg, redis, jwt = (secrets.token_hex(32) for _ in range(3))
target.write_text(f'DATABASE_URL=postgresql+asyncpg://pao:{pg}@127.0.0.1:5432/pao\n'
                  f'POSTGRES_PASSWORD={pg}\nREDIS_PASSWORD={redis}\n'
                  f'REDIS_URL=redis://:{redis}@127.0.0.1:6379/0\nJWT_SECRET={jwt}\n'
                  'OLLAMA_URL=http://127.0.0.1:11434\nOLLAMA_MODEL=qwen3:4b-instruct-2507-q4_K_M\n', encoding='utf-8')
print('Created ignored .env with random local credentials.')
