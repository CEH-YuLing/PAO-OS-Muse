"""Add an independent local search secret without replacing any existing credentials."""
import secrets
from pathlib import Path
target=Path(__file__).resolve().parents[1]/'.env'
if not target.exists():
    raise SystemExit('Run init_local.py first')
content=target.read_text(encoding='utf-8')
if not any(line.startswith('SEARXNG_SECRET=') and line.partition('=')[2].strip() for line in content.splitlines()):
    lines=[line for line in content.splitlines() if not line.startswith('SEARXNG_SECRET=')]
    target.write_text('\n'.join(lines)+'\nSEARXNG_SECRET='+secrets.token_hex(32)+'\n',encoding='utf-8')
print('Local search secret configured; existing credentials preserved.')
