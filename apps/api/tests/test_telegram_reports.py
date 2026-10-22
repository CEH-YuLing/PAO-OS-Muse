"""Scoped manual/scheduled reports use native outbox and recheck Ads authority."""
from datetime import date,timedelta
from uuid import uuid4
import httpx,pytest
from sqlalchemy import select,func
from zoneinfo import ZoneInfo
from pao.db import Session
from pao.config import settings
from pao.models import ChannelBinding,ChannelOutbox,AdReportSchedule,MetaConnection,now
from pao.modules.channels import telegram_setup as setup,telegram_store as store,telegram_runtime as rt,telegram_sender as sender,telegram_reports as reports
from pao.modules.business.report_scheduler import schedule_reports
from test_telegram_scoped import enabled_bots
from test_telegram_setup import confirmed,auth
from test_reporting import seed,body
from test_telegram_sender import success


@pytest.fixture
async def report_ready(enabled_bots,identity,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];peer=await confirmed(f)
    async with rt.own_bot(pin) as lease:
        async with store._transaction(lease) as db:
            p=await store._profile(db,pin)
            b=await setup.grant(db,pin,p,f['owner'],peer,allow_chat=False,allow_reports=True,confirm_destination=True,version=0,request_key=str(uuid4()))
            binding=b.id
    monkeypatch.setattr(settings(),'meta_enabled',True)
    # Report delivery is entirely synthetic; do not depend on host App keys.
    # Preserve enabled_bots' ephemeral Fernet key used by its Telegram profiles.
    for name,value in {'meta_app_id':'123','meta_app_secret':'synthetic-report-app-secret',
        'meta_graph_api_version':'v25.0','meta_redirect_uri':'https://test/v1/integrations/meta/callback'}.items():
        monkeypatch.setattr(settings(),name,value)
    await seed(identity,[date(2026,1,8),now().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()-timedelta(days=1)])
    return f,binding


async def test_manual_report_explicit_bot_and_owner_destination_no_implicit_fallback(client,identity,report_ready):
    f,bid=report_ready;pin=f['pins'][0]
    result=await client.post('/v1/reports',headers=identity['owner'],json=body(identity));assert result.status_code==201,result.text
    rid=result.json()['report']['id']
    assert (await client.post('/v1/reports/'+rid+'/telegram',headers=identity['owner'])).status_code==409
    for _ in range(2):
        r=await client.post('/v1/reports/'+rid+'/telegram',params={'binding_id':bid},headers=identity['owner']);assert r.status_code==202,r.text
    async with Session() as db:
        rows=list(await db.scalars(select(ChannelOutbox)));assert len(rows)==1 and rows[0].connection_id==pin.connection_id
        outbox=rows[0].id
    calls=[]
    def provider(request):
        import json
        payload=json.loads(request.content);calls.append(payload)
        assert payload['chat_id']=='888'
        return httpx.Response(200,json=success(pin,payload))
    assert (await sender.send_once(pin,outbox,transport=httpx.MockTransport(provider))).disposition=='sent'
    assert len(calls)==1
    detail=await client.get('/v1/reports/'+rid,headers=identity['owner']);assert detail.json()['deliveries'][0]['status']=='sent'


@pytest.mark.parametrize('loss',['meta','reports','member','destination'])
async def test_queued_report_rechecks_current_report_and_destination_authority(client,identity,report_ready,loss):
    f,bid=report_ready;pin=f['pins'][0]
    rid=(await client.post('/v1/reports',headers=identity['owner'],json=body(identity))).json()['report']['id']
    assert (await client.post('/v1/reports/'+rid+'/telegram',params={'binding_id':bid},headers=identity['owner'])).status_code==202
    async with Session.begin() as db:
        outbox=await db.scalar(select(ChannelOutbox.id))
        if loss=='meta':(await db.scalar(select(MetaConnection))).status='disconnected'
        elif loss=='member':
            from pao.models import Member
            (await db.get(Member,(pin.workspace_id,f['owner']))).role='viewer'
        else:
            binding=await db.get(ChannelBinding,bid)
            if loss=='reports':binding.reports_enabled=False
            else:binding.outbound_confirmed=False
    calls=[]
    def deny(request):calls.append(request);raise AssertionError('revoked report must not send')
    try:await sender.send_once(pin,outbox,transport=httpx.MockTransport(deny))
    except rt.TelegramRuntimeError:pass
    assert not calls


async def test_schedule_pins_binding_and_revoke_does_not_choose_another_bot(client,identity,report_ready):
    f,bid=report_ready
    data={'workspace_id':identity['workspace'],'account_id':'act_1','kind':'daily','enabled':True,
        'delivery_hour':8,'weekday':None,'telegram':True,'telegram_binding_id':bid}
    result=await client.put('/v1/reports/configuration/schedules',json=data,headers=identity['owner']);assert result.status_code==200,result.text
    sid=result.json()['id']
    async with Session.begin() as db:(await db.get(AdReportSchedule,sid)).next_at=now()-timedelta(seconds=1)
    await schedule_reports({});await schedule_reports({})
    async with Session.begin() as db:
        assert await db.scalar(select(func.count()).select_from(ChannelOutbox))==1
        binding=await db.get(ChannelBinding,bid);binding.reports_enabled=False;binding.version+=1
        (await db.get(AdReportSchedule,sid)).next_at=now()-timedelta(seconds=1)
    await schedule_reports({})
    async with Session() as db:assert not (await db.get(AdReportSchedule,sid)).enabled
