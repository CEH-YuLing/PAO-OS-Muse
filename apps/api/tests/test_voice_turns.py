"""Real HTTP/DB/shared Run, controlled local audio adapter; not real mic acceptance."""
import asyncio
from uuid import uuid4
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import VoiceTurn,Run,now
from pao.voice import engine
from pao.runtime import execute_run
from pao.modules.channels.voice_turns import expire_drafts
from test_voice import voice
from test_memory import Gateway

@pytest.fixture
def turns(voice,monkeypatch):
    monkeypatch.setattr(settings(),'voice_turns_enabled',True)
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)

async def create(client,identity,**changes):
    chat=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace'],'memory_enabled':False})
    body={'session_id':chat.json()['id'],'request_key':str(uuid4()),'consent_ephemeral_audio':True,'consent_transcript_storage':True,**changes}
    r=await client.post('/v1/voice/turns',headers=identity['owner'],json=body)
    return r,body

async def record(client,identity,row,audio=b'x'*100):
    return await client.post('/v1/voice/turns/'+row['id']+'/audio',headers={**identity['owner'],'Content-Type':'audio/webm'},content=audio)

async def test_turn_consent_scope_and_dedup(client,identity,turns):
    failed,_=await create(client,identity,consent_ephemeral_audio=False);assert failed.status_code==422
    r,body=await create(client,identity);assert r.status_code==201
    copies=await asyncio.gather(*(client.post('/v1/voice/turns',headers=identity['owner'],json=body) for _ in range(3)))
    assert all(x.status_code==201 and x.json()['id']==r.json()['id'] for x in copies)
    assert (await client.get('/v1/voice/turns/'+r.json()['id'],headers=identity['other'])).status_code==404
    row=(await record(client,identity,r.json())).json();assert row['status']=='ready' and not row['raw_audio_retained']
    assert (await record(client,identity,row)).json()['version']==row['version'];assert engine.transcribe.await_count==1
    assert (await record(client,identity,row,b'y'*100)).status_code==409

async def test_voice_submit_shared_run_once_and_scoped_speech(client,identity,turns):
    r,_=await create(client,identity);row=(await record(client,identity,r.json())).json()
    base='/v1/voice/turns/'+row['id'];body={'confirm_transcript':True,'version':row['version']}
    values=await asyncio.gather(*(client.post(base+'/submit',headers=identity['owner'],json=body) for _ in range(3)))
    assert all(x.status_code==200 for x in values),[x.text for x in values]
    assert len({x.json()['id'] for x in values})==1
    rid=values[0].json()['id'];await execute_run({'gateway':Gateway()},rid)
    speech=await client.post(base+'/speech',headers=identity['owner']);assert speech.status_code==200 and speech.headers['x-voice-turn']==row['id']
    engine.synthesize.assert_awaited_once_with('Đã nhận thông tin.')
    async with Session() as db:
        assert await db.scalar(select(func.count(Run.id)))==1
        assert (await db.get(VoiceTurn,row['id'])).transcript is None
    assert (await client.get('/v1/sessions/'+row['session_id'],headers=identity['owner'])).json()['messages']
    assert (await client.post(base+'/cancel',headers=identity['owner'])).json()['status']=='cancelled'
    assert (await client.post(base+'/speech',headers=identity['owner'])).status_code==409

async def test_cancel_during_stt_discards_late_transcript(client,identity,turns):
    started=asyncio.Event();release=asyncio.Event()
    async def slow(*args):started.set();await release.wait();return 'Late text','vi',10
    engine.transcribe.side_effect=slow
    r,_=await create(client,identity);row=r.json();task=asyncio.create_task(record(client,identity,row))
    await asyncio.wait_for(started.wait(),5)
    assert (await client.post('/v1/voice/turns/'+row['id']+'/cancel',headers=identity['owner'])).status_code==200
    release.set();assert (await asyncio.wait_for(task,5)).status_code==409
    async with Session() as db:
        assert (await db.get(VoiceTurn,row['id'])).transcript is None
        assert await db.scalar(select(func.count(Run.id)))==0

async def test_cancel_during_tts_discards_late_audio(client,identity,turns):
    r,_=await create(client,identity);row=(await record(client,identity,r.json())).json();base='/v1/voice/turns/'+row['id']
    rid=(await client.post(base+'/submit',headers=identity['owner'],json={'version':row['version'],'confirm_transcript':True})).json()['id']
    await execute_run({'gateway':Gateway()},rid)
    started=asyncio.Event();release=asyncio.Event()
    async def slow(*args):started.set();await release.wait();return b'RIFF'+b'0'*100,10
    engine.synthesize.side_effect=slow;task=asyncio.create_task(client.post(base+'/speech',headers=identity['owner']))
    await asyncio.wait_for(started.wait(),5);await client.post(base+'/cancel',headers=identity['owner']);release.set()
    assert (await asyncio.wait_for(task,5)).status_code==409

async def test_voice_commands_and_expired_drafts_cannot_run(client,identity,turns):
    engine.transcribe.return_value=('/approve tool-secret','vi',10)
    r,_=await create(client,identity);row=(await record(client,identity,r.json())).json()
    base='/v1/voice/turns/'+row['id'];body={'version':row['version'],'confirm_transcript':True}
    assert (await client.post(base+'/submit',headers=identity['owner'],json=body)).status_code==422
    async with Session.begin() as db:(await db.get(VoiceTurn,row['id'])).created_at=now()-timedelta(hours=25)
    await expire_drafts()
    assert (await client.get(base,headers=identity['owner'])).json()['transcript'] is None
    assert (await client.post(base+'/submit',headers=identity['owner'],json=body)).status_code==409

async def test_voice_feature_gate_and_cancel_rollback(client,identity,turns,monkeypatch):
    r,_=await create(client,identity);row=r.json();monkeypatch.setattr(settings(),'voice_turns_enabled',False)
    assert (await record(client,identity,row)).status_code==409
    assert (await client.post('/v1/voice/turns/'+row['id']+'/cancel',headers=identity['owner'])).status_code==200
