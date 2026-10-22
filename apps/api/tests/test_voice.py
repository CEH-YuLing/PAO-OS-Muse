from unittest.mock import AsyncMock
from sqlalchemy import func,select
import pytest
from pao.config import settings
from pao.db import Session
from pao.models import VoiceInteraction
from pao.voice import engine

BASE='/v1/voice'
@pytest.fixture
def voice(monkeypatch):
    monkeypatch.setattr(settings(),'voice_enabled',True);monkeypatch.setattr(settings(),'voice_max_audio_bytes',1024)
    monkeypatch.setattr(engine,'status',lambda:{'enabled':True,'stt_ready':True,'tts_ready':True,'stt_device':'cpu','stt_compute_type':'int8','tts_provider':'windows_sapi','max_seconds':30})
    monkeypatch.setattr(engine,'transcribe',AsyncMock(return_value=('Xin chào PAO','vi',120)))
    monkeypatch.setattr(engine,'synthesize',AsyncMock(return_value=(b'RIFF'+b'0'*100,80)))

async def test_voice_status_fail_closed(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'voice_enabled',False)
    status=await client.get(BASE+'/status',headers=identity['owner']);assert status.status_code==200 and status.json()['enabled'] is False
    assert (await client.get(BASE+'/status')).status_code==401

async def test_local_stt_tts_audit_without_content(client,identity,voice):
    params={'workspace_id':identity['workspace']};audio=b'webm'+b'1'*100
    result=await client.post(BASE+'/transcriptions',params=params,content=audio,headers={**identity['owner'],'Content-Type':'audio/webm'})
    assert result.status_code==200 and result.json()['text']=='Xin chào PAO'
    speech=await client.post(BASE+'/speech',json={**params,'text':'Câu trả lời cục bộ'},headers=identity['owner']);assert speech.status_code==200 and speech.headers['content-type']=='audio/wav'
    async with Session() as db:
        rows=list(await db.scalars(select(VoiceInteraction).order_by(VoiceInteraction.created_at)))
        assert len(rows)==2 and rows[0].input_bytes==len(audio) and rows[1].output_bytes==104
        assert not hasattr(rows[0],'transcript') and not hasattr(rows[0],'audio')

async def test_voice_scope_format_and_size(client,identity,voice):
    params={'workspace_id':identity['workspace']};audio=b'x'*100
    assert (await client.post(BASE+'/transcriptions',params=params,content=audio,headers={**identity['outsider'],'Content-Type':'audio/webm'})).status_code==404
    assert (await client.post(BASE+'/transcriptions',params=params,content=audio,headers={**identity['owner'],'Content-Type':'text/plain'})).status_code==415
    assert (await client.post(BASE+'/transcriptions',params=params,content=b'x'*1100,headers={**identity['owner'],'Content-Type':'audio/webm'})).status_code==413
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(VoiceInteraction))==0

async def test_voice_provider_failure_is_safe(client,identity,voice):
    from pao.voice import VoiceError
    engine.transcribe.side_effect=VoiceError('stt_not_ready')
    result=await client.post(BASE+'/transcriptions',params={'workspace_id':identity['workspace']},content=b'x'*100,headers={**identity['owner'],'Content-Type':'audio/webm'})
    assert result.status_code==503 and 'sẵn sàng' in result.json()['detail']
    async with Session() as db:
        row=await db.scalar(select(VoiceInteraction));assert row.status=='failed' and row.error_code=='stt_not_ready'
