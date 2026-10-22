"""Local model smoke test; audio stays in memory and is never sent externally."""
import asyncio,json
from pathlib import Path
from pao.voice import engine

async def main():
    status=engine.status();assert status['enabled'] and status['stt_ready'] and status['tts_ready'],status
    audio,tts_ms=await engine.synthesize('Xin chào PAO. Đây là kiểm tra giọng nói cục bộ.')
    assert audio.startswith(b'RIFF') and len(audio)>1000
    text,language,stt_ms=await engine.transcribe(audio,'.wav')
    assert text.strip()
    report={'status':status,'tts_bytes':len(audio),'tts_ms':tts_ms,'stt_text':text,'language':language,'stt_ms':stt_ms}
    Path('.runtime/phase-18-voice-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
asyncio.run(main())
