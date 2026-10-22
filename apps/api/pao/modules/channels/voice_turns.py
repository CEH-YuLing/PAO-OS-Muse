"""Consent -> bounded local STT -> reviewed transcript -> shared Run -> scoped TTS."""
import hashlib
from datetime import timedelta
from typing import Literal
from uuid import UUID,uuid5
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import select
from pao.access import owned_session
from pao.auth import principal,rate_limit
from pao.config import settings
from pao.db import database
from pao.models import VoiceTurn,Run,now
from pao.schemas import RunCreate,RunOut
from pao.voice import engine,VoiceError
from pao.voice_api import CONTENT
from pao.modules.studio.contracts import Closed
from pao.modules.conversations.requests import admit_run
from pao.modules.conversations.state import finish

router=APIRouter(prefix='/v1/voice/turns',tags=['voice-turns'])

def enabled():
    if not settings().voice_enabled or not settings().voice_turns_enabled:raise HTTPException(409,'voice_turns_disabled')

class Create(Closed):
    session_id:UUID=Field(strict=False)
    request_key:UUID=Field(strict=False)
    consent_ephemeral_audio:Literal[True]
    consent_transcript_storage:Literal[True]

class Submit(Closed):
    version:int=Field(ge=1)
    confirm_transcript:Literal[True]

def view(row):
    return {'id':row.id,'session_id':row.session_id,'status':row.status,'version':row.version,'transcript':row.transcript,
        'run_id':row.run_id,'error_code':row.error_code,'language':row.language,'stt_latency_ms':row.duration_ms,
        'raw_audio_retained':False,'draft_retention_hours':24,'submitted_transcript_retention':'chat session policy'}

async def owned(db,ident,who,lock=False):
    row=await db.get(VoiceTurn,str(ident),with_for_update=lock,populate_existing=True)
    if not row or row.user_id!=who.id:raise HTTPException(404,'voice_turn_not_found')
    chat=await owned_session(db,row.session_id,who,True)
    if chat.workspace_id!=row.workspace_id:raise HTTPException(404,'voice_turn_not_found')
    return row

@router.post('',status_code=201)
async def create(body:Create,request:Request,who=Depends(principal),db=Depends(database)):
    enabled();chat=await owned_session(db,body.session_id,who,True)
    ident=str(uuid5(UUID(who.id),'voice:'+str(body.request_key)))
    existing=await db.get(VoiceTurn,ident)
    if existing:
        if existing.session_id!=chat.id:raise HTTPException(409,'voice_request_key_conflict')
        return view(existing)
    await rate_limit(request.app.state.redis,'voice-turn-create',who.id,10,60)
    row=VoiceTurn(id=ident,workspace_id=chat.workspace_id,session_id=chat.id,user_id=who.id,request_key=str(body.request_key))
    db.add(row)
    from sqlalchemy.exc import IntegrityError
    try:await db.commit()
    except IntegrityError:
        await db.rollback();row=await db.get(VoiceTurn,ident)
        if not row or row.session_id!=chat.id:raise HTTPException(409,'voice_request_key_conflict') from None
    return view(row)

@router.get('/{turn_id}')
async def get(turn_id:UUID,who=Depends(principal),db=Depends(database)):
    return view(await owned(db,turn_id,who))

@router.post('/{turn_id}/audio')
async def audio(turn_id:UUID,request:Request,who=Depends(principal),db=Depends(database)):
    enabled();await owned(db,turn_id,who);await db.rollback()
    media=request.headers.get('content-type','').split(';')[0].lower()
    if media not in CONTENT:raise HTTPException(415,'voice_audio_format_invalid')
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>settings().voice_max_audio_bytes:raise HTTPException(413,'voice_audio_too_large')
        data.extend(chunk)
    if len(data)<64:raise HTTPException(422,'voice_audio_empty')
    fingerprint=hashlib.sha256(data).hexdigest();row=await owned(db,turn_id,who,True)
    if row.audio_hash and row.audio_hash!=fingerprint:raise HTTPException(409,'voice_audio_key_conflict')
    if row.status in ('ready','submitted'):return view(row)
    if row.status!='created':raise HTTPException(409,'voice_turn_not_recordable')
    await rate_limit(request.app.state.redis,'voice-turn-stt',who.id,10,60)
    row.audio_hash=fingerprint;row.status='transcribing';row.version+=1;await db.commit()
    try:
        transcript,language,latency=await engine.transcribe(bytes(data),CONTENT[media])
        if not transcript.strip() or len(transcript)>2000:raise VoiceError('voice_transcript_size_invalid')
    except Exception as exc:
        row=await owned(db,turn_id,who,True)
        if row.status=='transcribing':row.status='failed';row.error_code=str(exc)[:64] if isinstance(exc,VoiceError) else 'stt_failed';row.version+=1
        await db.commit();raise HTTPException(503,'voice_stt_failed') from None
    finally:data.clear()
    enabled();row=await owned(db,turn_id,who,True)
    if row.status!='transcribing':raise HTTPException(409,'voice_turn_cancelled')
    row.status='ready';row.transcript=transcript.strip();row.language=language;row.duration_ms=latency;row.version+=1
    await db.commit();return view(row)

@router.post('/{turn_id}/submit',response_model=RunOut)
async def submit(turn_id:UUID,body:Submit,request:Request,who=Depends(principal),db=Depends(database)):
    enabled();row=await owned(db,turn_id,who,True)
    if row.status=='submitted':return await db.get(Run,row.run_id)
    if row.status!='ready' or row.version!=body.version:raise HTTPException(409,'voice_turn_not_ready')
    if row.created_at<now()-timedelta(hours=24):raise HTTPException(409,'voice_draft_expired')
    if not row.transcript or row.transcript.startswith('/'):raise HTTPException(422,'voice_command_requires_dashboard')
    run=await admit_run(RunCreate(session_id=row.session_id,request_key='voice-'+row.id,message=row.transcript),request,who,db,commit=False)
    row.run_id=run.id;row.status='submitted';row.version+=1;row.transcript=None
    await db.commit()
    try:await request.app.state.redis.enqueue_job('execute_run',run.id,_job_id='run:'+run.id)
    except Exception:pass  # Existing durable dispatcher recovers it.
    return run

@router.post('/{turn_id}/cancel')
async def cancel(turn_id:UUID,who=Depends(principal),db=Depends(database)):
    row=await owned(db,turn_id,who,True)
    if row.status!='cancelled':
        row.status='cancelled';row.version+=1;row.transcript=None
        run=await db.get(Run,row.run_id,with_for_update=True) if row.run_id else None
        if run and run.status in ('queued','running'):
            run.cancel_requested=True
            if run.status=='queued':await finish(db,run,'cancelled')
        await db.commit()
    return view(row)

@router.post('/{turn_id}/speech')
async def speech(turn_id:UUID,request:Request,who=Depends(principal),db=Depends(database)):
    enabled();row=await owned(db,turn_id,who)
    if row.status!='submitted' or not row.run_id:raise HTTPException(409,'voice_turn_not_submitted')
    run=await db.get(Run,row.run_id)
    from pao.modules.knowledge.conversations import run_visible
    from pao.modules.channels.service import check_run
    if not run or run.status!='completed' or run.cancel_requested:raise HTTPException(409,'voice_run_not_completed')
    if not await run_visible(db,run,who):raise HTTPException(403,'voice_source_revoked')
    try:await check_run(db,run)
    except PermissionError:raise HTTPException(403,'voice_channel_revoked') from None
    if not run.response or len(run.response)>2000:raise HTTPException(422,'voice_response_exceeds_local_tts_limit')
    ident,version,rid,text=row.id,row.version,run.id,run.response
    await rate_limit(request.app.state.redis,'voice-turn-tts',who.id,20,60);await db.rollback()
    try:data,latency=await engine.synthesize(text)
    except VoiceError:raise HTTPException(503,'voice_tts_failed') from None
    enabled();row=await owned(db,ident,who);run=await db.get(Run,rid,populate_existing=True)
    if row.status!='submitted' or row.version!=version or run.cancel_requested or run.response!=text:raise HTTPException(409,'voice_turn_cancelled')
    if not await run_visible(db,run,who):raise HTTPException(403,'voice_source_revoked')
    try:await check_run(db,run)
    except PermissionError:raise HTTPException(403,'voice_channel_revoked') from None
    return Response(data,media_type='audio/wav',headers={'Cache-Control':'no-store','X-Voice-Turn':ident,'X-Voice-TTS-Latency-Ms':str(latency)})

async def expire_drafts():
    from pao.db import Session
    async with Session.begin() as db:
        rows=await db.scalars(select(VoiceTurn).where(VoiceTurn.status.in_(('created','transcribing','ready','failed')),VoiceTurn.created_at<now()-timedelta(hours=24)).with_for_update(skip_locked=True).limit(100))
        for row in rows:row.status='cancelled';row.transcript=None;row.version+=1;row.error_code='draft_expired'
