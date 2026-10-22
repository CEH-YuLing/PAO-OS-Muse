from datetime import datetime
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from fastapi.responses import Response
from pydantic import BaseModel,Field
from sqlalchemy.ext.asyncio import AsyncSession
from .access import membership,owned_session
from .auth import Principal,principal,rate_limit
from .config import settings
from .db import database
from .models import VoiceInteraction,now
from .voice import VoiceError,engine

router=APIRouter(prefix='/v1/voice',tags=['voice'])
CONTENT={'audio/webm':'.webm','audio/ogg':'.ogg','audio/wav':'.wav','audio/x-wav':'.wav','audio/mp4':'.mp4','audio/mpeg':'.mp3'}
class SpeechIn(BaseModel):
    workspace_id:UUID;session_id:UUID|None=None;text:str=Field(min_length=1,max_length=2000)
class TranscriptOut(BaseModel):text:str;language:str;duration_ms:int

@router.get('/status')
async def status(who:Principal=Depends(principal)):return {**engine.status(),'turns_enabled':settings().voice_turns_enabled,'raw_audio_retained':False,'real_microphone_accepted':False}

async def scope(db,workspace_id,session_id,who):
    await membership(db,str(workspace_id),who,True)
    if session_id:
        session=await owned_session(db,session_id,who,True)
        if session.workspace_id!=str(workspace_id):raise HTTPException(404,'Không tìm thấy hội thoại')

@router.post('/transcriptions',response_model=TranscriptOut)
async def transcribe(request:Request,workspace_id:UUID=Query(),session_id:UUID|None=Query(None),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    if settings().voice_turns_enabled:raise HTTPException(409,'use_scoped_voice_turns')
    await scope(db,workspace_id,session_id,who);await rate_limit(request.app.state.redis,'voice-stt',who.id,10,60)
    media=request.headers.get('content-type','').split(';')[0].lower()
    if media not in CONTENT:raise HTTPException(415,'Định dạng audio không hỗ trợ')
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>settings().voice_max_audio_bytes:raise HTTPException(413,'Audio quá lớn')
        chunks.append(chunk)
    if size<64:raise HTTPException(422,'Audio trống')
    audit=VoiceInteraction(workspace_id=str(workspace_id),user_id=who.id,session_id=str(session_id) if session_id else None,kind='stt',status='running',provider='faster-whisper',input_bytes=size)
    db.add(audit);await db.commit()
    try:text,language,duration=await engine.transcribe(b''.join(chunks),CONTENT[media])
    except VoiceError as exc:
        code=str(exc)[:64];audit.status='failed';audit.error_code=code;audit.completed_at=now();await db.commit()
        raise HTTPException(422 if code=='audio_too_long' else 503,'Audio dài quá giới hạn' if code=='audio_too_long' else 'STT local chưa sẵn sàng') from exc
    audit.status='completed';audit.duration_ms=duration;audit.language=language;audit.completed_at=now();await db.commit();return {'text':text,'language':language,'duration_ms':duration}

@router.post('/speech')
async def speech(body:SpeechIn,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    if settings().voice_turns_enabled:raise HTTPException(409,'use_scoped_voice_turns')
    await scope(db,body.workspace_id,body.session_id,who);await rate_limit(request.app.state.redis,'voice-tts',who.id,20,60)
    audit=VoiceInteraction(workspace_id=str(body.workspace_id),user_id=who.id,session_id=str(body.session_id) if body.session_id else None,kind='tts',status='running',provider=settings().voice_tts_provider,input_bytes=len(body.text.encode('utf-8')))
    db.add(audit);await db.commit()
    try:data,duration=await engine.synthesize(body.text)
    except VoiceError as exc:
        audit.status='failed';audit.error_code=str(exc)[:64];audit.completed_at=now();await db.commit();raise HTTPException(503,'TTS local chưa sẵn sàng') from exc
    audit.status='completed';audit.output_bytes=len(data);audit.duration_ms=duration;audit.completed_at=now();await db.commit()
    return Response(data,media_type='audio/wav',headers={'Cache-Control':'no-store','X-Voice-Interaction-Id':audit.id})
