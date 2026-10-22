"""Genuine HTTP/browser, synthetic microphone/local STT fixture; no live account."""
import asyncio,struct
from unittest.mock import AsyncMock
from uuid import uuid4
from pao.config import settings
from pao.voice import engine
from test_voice import voice
from test_voice_turns import turns
from test_channels import channels_on
from p6_browser_harness import browser
from pao.config import ROOT
from pao.modules.channels import service

async def test_p7_inbox_voice_browser(client,identity,channels_on,turns,monkeypatch):
    monkeypatch.setattr(settings(),'voice_max_audio_bytes',1000000)
    data=b'\0\0'*800
    wav=b'RIFF'+struct.pack('<I',36+len(data))+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,8000,16000,2,16)+b'data'+struct.pack('<I',len(data))+data
    engine.synthesize.return_value=(wav,10)
    original=engine.transcribe.return_value
    async def transcribe(*args):await asyncio.sleep(1);return original
    engine.transcribe.side_effect=transcribe
    chat=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace'],'title':'P7 voice fixture','memory_enabled':False})
    marker=ROOT/'.runtime'/('p7-delivery-marker-'+uuid4().hex)
    async def uncertain():
        for _ in range(600):
            if marker.exists():
                await service.send_one(AsyncMock(side_effect=TimeoutError()),'local');return
            await asyncio.sleep(.1)
        raise AssertionError('P7 browser did not reach uncertain-delivery handshake')
    task=asyncio.create_task(uncertain())
    try:
        report=await browser('scripts/verify_p7_browser.cjs','PAO_P7_BROWSER_FIXTURE',{'workspace':identity['workspace'],'actor':identity['user_id'],'session':chat.json()['id'],'marker':str(marker)},'p7')
        await asyncio.wait_for(task,5)
        assert report['synthetic_microphone'] is True and report['live_channel_accepted'] is False
    finally:task.cancel();await asyncio.gather(task,return_exceptions=True)
