"""Interactive local setup. Secrets are entered invisibly, never via command arguments."""
import argparse
import asyncio
import getpass
import re
import secrets
from pathlib import Path
from sqlalchemy import select
from pao.config import ROOT
from pao.db import Session, engine
from pao.models import TelegramPeer, User, Member

parser = argparse.ArgumentParser()
parser.add_argument('--token', action='store_true', help='Enter bot token invisibly and keep disabled until whitelist is configured')
parser.add_argument('--email', help='Existing PAO user email')
parser.add_argument('--user-id', help='Telegram numeric user ID')
parser.add_argument('--chat-id', help='Private Telegram chat ID (usually the same as user ID)')
parser.add_argument('--disable', action='store_true', help='Revoke the selected peer')
parser.add_argument('--enable', action='store_true', help='Enable transport after token and whitelist setup')
args = parser.parse_args()


def update_env(values):
    path = ROOT / '.env'
    lines = path.read_text(encoding='utf-8').splitlines()
    lines = [line for line in lines if line.split('=',1)[0] not in values]
    path.write_text('\n'.join(lines + [f'{key}={value}' for key,value in values.items()])+'\n', encoding='utf-8')


async def main():
    from pao.modules.channels.telegram_helpers import legacy_blocked
    async with Session() as db:
        if await legacy_blocked(db):raise SystemExit('Legacy Telegram is mapped; use SME setup, do not reuse the host token or rebind history.')
    if args.token:
        token = getpass.getpass('Bot token (hidden): ').strip()
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{20,}',token):
            raise SystemExit('Invalid token format; configuration unchanged')
        update_env({'TELEGRAM_BOT_TOKEN':token,'TELEGRAM_WEBHOOK_SECRET':secrets.token_urlsafe(32),'TELEGRAM_ENABLED':'false','TELEGRAM_MODE':'polling'})
        print('Token stored locally. Telegram remains disabled.')
    if args.email:
        if not args.user_id or not args.chat_id or not args.user_id.isdecimal() or args.chat_id != args.user_id:
            raise SystemExit('Provide matching positive numeric --user-id and --chat-id for a private chat')
        async with Session.begin() as db:
            user = await db.scalar(select(User).where(User.email == args.email.strip().lower(),User.active.is_(True)))
            members = list(await db.scalars(select(Member).where(Member.user_id == user.id))) if user else []
            if len(members) != 1 or members[0].role == 'viewer':
                raise SystemExit('Expected one writable workspace for this active PAO account')
            peer = await db.scalar(select(TelegramPeer).where(TelegramPeer.telegram_user_id == args.user_id,TelegramPeer.connection_id.is_(None)))
            if peer and (peer.user_id != user.id or peer.workspace_id != members[0].workspace_id):
                raise SystemExit('Peer already belongs to another account; do not rebind existing history')
            if not peer:
                peer = TelegramPeer(telegram_user_id=args.user_id,chat_id=args.chat_id,user_id=user.id,workspace_id=members[0].workspace_id)
                db.add(peer)
            peer.enabled = not args.disable
        print('Whitelist updated. No messages sent.')
    if args.enable:
        from pao.config import settings
        settings.cache_clear()
        async with Session() as db:
            peer = await db.scalar(select(TelegramPeer.id).where(TelegramPeer.enabled.is_(True),TelegramPeer.connection_id.is_(None)).limit(1))
        if not peer or not settings().telegram_bot_token:
            raise SystemExit('Configure token and whitelist first')
        update_env({'TELEGRAM_ENABLED':'true'})
        print('Telegram enabled in configuration. Restart API and bridge to apply.')
    await engine.dispose()

asyncio.run(main())
