"""Explicit operator command to register/remove a webhook; does not expose the API port."""
import argparse
import asyncio
from urllib.parse import urlsplit
from pao.config import settings
from pao.telegram import bot_api

parser=argparse.ArgumentParser()
parser.add_argument('--url',help='HTTPS URL ending in /v1/telegram/webhook on an operator-managed reverse proxy')
parser.add_argument('--remove',action='store_true')
args=parser.parse_args()

async def main():
    config=settings()
    if not config.telegram_bot_token:
        raise SystemExit('Configure token locally first')
    if args.remove and not args.url:
        await bot_api('deleteWebhook',{'drop_pending_updates':False})
        print('Webhook removed; pending updates preserved. Set TELEGRAM_MODE=polling and restart.')
        return
    parsed=urlsplit(args.url or '')
    if args.remove or parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path!='/v1/telegram/webhook':
        raise SystemExit('Provide a valid HTTPS webhook URL or --remove')
    if len(config.telegram_webhook_secret)<32:
        raise SystemExit('Configure a webhook secret of at least 32 characters')
    await bot_api('setWebhook',{'url':args.url,'secret_token':config.telegram_webhook_secret,
        'allowed_updates':['message','callback_query'],'drop_pending_updates':False})
    print('Webhook registered. Set TELEGRAM_MODE=webhook and restart API/bridge.')

asyncio.run(main())
