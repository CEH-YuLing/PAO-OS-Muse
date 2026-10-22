"""Isolated UI test process only: synthetic Telegram HTTP, never production."""
import os,re,json
if os.environ.get('PAO_S3_BROWSER_TEST')!='1':raise SystemExit('Test process opt-in required')
from sqlalchemy.engine import make_url
from pao.config import settings
url=make_url(settings().database_url)
if not re.fullmatch('pao_s3_browser_[0-9a-f]{32}',url.database or '') or url.host!='127.0.0.1' or url.port!=15432:
    raise SystemExit('Owned browser database only')
import httpx
hooks={};pending={}


def fixture(request):
    if request.url.host!='api.telegram.org':raise AssertionError('No external I/O in S3 browser')
    method=request.url.path.rsplit('/',1)[-1];bot=request.url.path.split('/bot',1)[1].split(':',1)[0]
    if bot not in ('333','444'):raise AssertionError('Synthetic fixture bots only')
    body=json.loads(request.content)
    if method=='getMe':result={'id':int(bot),'is_bot':True,'username':'PAO_fixture_bot'}
    elif method=='getWebhookInfo':result={'url':hooks.get(bot,''),'pending_update_count':0}
    elif method=='setWebhook':hooks[bot]=body['url'];result=True
    elif method=='deleteWebhook':hooks.pop(bot,None);result=True
    elif method=='getUpdates':result=pending.pop(bot,[])
    else:raise AssertionError('Browser acceptance must not send messages')
    return httpx.Response(200,json={'ok':True,'result':result})


from fastapi import HTTPException,Request
from sqlalchemy import select
from pao.main import app
from pao.db import Session
from pao.models import TelegramConnection,TelegramBotIdentity
from pao.modules.channels import telegram_polling as polling,telegram_runtime as rt
import hmac
httpx.AsyncHTTPTransport=lambda **kwargs:httpx.MockTransport(fixture)


@app.post('/fixture/telegram-update',include_in_schema=False)
async def inject(request:Request):
    if not hmac.compare_digest(request.headers.get('x-fixture-key',''),os.environ['PAO_S3_BROWSER_KEY']):raise HTTPException(403)
    body=await request.json()
    if body.get('bot')!='333' or type(body.get('command')) is not str or not re.fullmatch(r'/start pao_[A-Za-z0-9_-]{32}',body['command']):raise HTTPException(422)
    async with Session() as db:
        c=await db.scalar(select(TelegramConnection).where(TelegramConnection.bot_user_id=='333'))
        if not c:raise HTTPException(409)
        pin=rt.RuntimePin(c.workspace_id,c.id,c.owner_id,c.version,c.bot_user_id)
    pending['333']=[{'update_id':100,'message':{'from':{'id':888,'is_bot':False},'chat':{'id':888,'type':'private'},'text':body['command']}}]
    result=await polling.poll_once(pin,app.state.redis,transport=httpx.MockTransport(fixture))
    return {'processed':result.processed}


if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=18100,access_log=False,log_level='error')
