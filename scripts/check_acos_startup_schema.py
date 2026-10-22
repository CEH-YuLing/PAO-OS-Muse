"""Read-only startup gate. Starting PAO must never perform a schema rollout."""
import argparse
import asyncio
import json
from pathlib import Path
import re

REVIEWED_REVISION = '0077'


def local_url(raw):
    from sqlalchemy.engine import make_url
    url = make_url(raw)
    if (url.drivername, url.host, url.port, url.database, url.username) != (
            'postgresql+asyncpg', '127.0.0.1', 15432, 'pao_acos_local', 'pao'):
        raise ValueError('acos_startup_database_scope_denied')
    return url


def validate_revision(rows, expected):
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9]{4}', expected):
        raise ValueError('explicit_reviewed_revision_required')
    if list(rows) != [expected]:
        raise ValueError('acos_schema_release_required')
    return {'pass': True, 'revision': expected, 'read_only': True, 'migration_executed': False}


async def check(raw, expected=REVIEWED_REVISION):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    # Validate the pin before opening any database connection.
    validate_revision([expected], expected)
    url = local_url(raw)
    engine = create_async_engine(url, connect_args={'server_settings': {
        'default_transaction_read_only': 'on', 'statement_timeout': '5000',
        'application_name': 'pao_startup_schema_readonly'}})
    try:
        async with engine.connect() as db:
            if await db.scalar(text('SHOW transaction_read_only')) != 'on':
                raise ValueError('startup_readonly_required')
            rows = list(await db.scalars(text('SELECT version_num FROM alembic_version')))
            return validate_revision(rows, expected)
    finally:
        await engine.dispose()


def main():
    from pao.config import ROOT, settings
    if ROOT.resolve() != Path('F:/PAO-ACOS'):
        raise ValueError('acos_checkout_required')
    parser = argparse.ArgumentParser(description='Kiểm schema chỉ đọc; không nâng cấp database.')
    parser.add_argument('--expected', default=REVIEWED_REVISION)
    args = parser.parse_args()
    result = asyncio.run(check(settings().database_url, args.expected))
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print a URL, key, SQLAlchemy traceback or configuration values.
        code = str(error) if type(error) is ValueError and re.fullmatch(r'[a-z_]+', str(error)) else 'startup_schema_check_failed'
        print(json.dumps({'pass': False, 'code': code, 'migration_executed': False,
            'help': 'Schema chưa đúng bản đã duyệt. Tạo và kiểm chứng checkpoint, thử phục hồi clone rồi dùng quy trình phát hành riêng; khởi động thường không tự migrate.'}, ensure_ascii=False))
        raise SystemExit(2)
