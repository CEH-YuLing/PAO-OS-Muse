import re,unicodedata
from uuid import UUID,uuid5
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,func
from ...access import owned_session
from ...auth import Principal,principal
from ...config import settings
from ...db import database
from ...models import Message,LearningProposal,LearningAudit,BrainNote,now
from ..brains.access import require_brain
from ..brains.notes import add_note
from ..studio.contracts import Closed,BAD_TEXT,digest

router=APIRouter(prefix='/v1/learning',tags=['learning-review'])
SECRET=re.compile(r'(?i)([0-9a-f]{32}|api[_ -]?key\s*[:=]|secret\s*[:=]|password\s*[:=]|mật khẩu\s*[:=]|bỏ qua.*(quy tắc|hướng dẫn))')


def enabled():
    if not settings().learning_review_enabled:raise HTTPException(409,'learning_review_disabled')


def safe(value):
    normalized=unicodedata.normalize('NFKC',value)
    if (any(unicodedata.category(c) in ('Cf','Cs') or (unicodedata.category(c)=='Cc' and c not in '\n\r\t') for c in value)
        or BAD_TEXT.search(normalized) or SECRET.search(normalized)):
        raise HTTPException(422,'learning_content_requires_redaction')


async def source(db,who,ident,workspace_id):
    message=await db.get(Message,str(ident))
    if not message or message.workspace_id!=workspace_id:raise HTTPException(404,'learning_source_not_found')
    await owned_session(db,message.session_id,who,True)
    if message.role!='user' or message.status!='completed':raise HTTPException(409,'learning_source_not_eligible')
    return message,digest({'id':message.id,'session_id':message.session_id,'content':message.content,'role':message.role})


def view(row):
    return {'id':row.id,'brain_id':row.brain_id,'source_id':row.source_id,'source_hash':row.source_hash,
        'candidate':row.candidate,'fingerprint':row.fingerprint,'status':row.status,'note_id':row.note_id,
        'diff':{'before':None,'after':row.candidate},'promotion_target':'data_only_note',
        'automatic_promotion':False,'policy_or_code_modified':False}


class LearningProposalInput(Closed):
    source_id:str=Field(pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    candidate:str=Field(min_length=3,max_length=2000)


@router.post('/brains/{brain_id}/proposals')
async def propose(brain_id:UUID,body:LearningProposalInput,who:Principal=Depends(principal),db=Depends(database)):
    enabled();brain=await require_brain(db,who,brain_id,True,lock=True)
    message,source_hash=await source(db,who,body.source_id,brain.workspace_id)
    safe(body.candidate)
    if body.candidate not in message.content:raise HTTPException(422,'learning_candidate_must_quote_source')
    fingerprint=digest({'source_hash':source_hash,'candidate':body.candidate})
    saved=await db.scalar(select(LearningProposal).where(LearningProposal.brain_id==brain.id,
        LearningProposal.actor_id==who.id,LearningProposal.fingerprint==fingerprint))
    if saved:return view(saved)
    # Same workspace owner row serializes daily budget across different brains.
    from ...models import User
    await db.get(User,who.id,with_for_update=True)
    day=now().replace(hour=0,minute=0,second=0,microsecond=0)
    count=await db.scalar(select(func.count(LearningProposal.id)).where(LearningProposal.actor_id==who.id,
        LearningProposal.workspace_id==brain.workspace_id,LearningProposal.created_at>=day))
    from ...models import ArtifactLearningProposal
    count+=await db.scalar(select(func.count(ArtifactLearningProposal.id)).where(ArtifactLearningProposal.actor_id==who.id,
        ArtifactLearningProposal.workspace_id==brain.workspace_id,ArtifactLearningProposal.created_at>=day))
    if count>=10:raise HTTPException(429,'learning_daily_budget_exhausted')
    row=LearningProposal(workspace_id=brain.workspace_id,brain_id=brain.id,actor_id=who.id,
        source_id=message.id,source_hash=source_hash,candidate=body.candidate,fingerprint=fingerprint)
    db.add(row);await db.flush()
    db.add(LearningAudit(proposal_id=row.id,actor_id=who.id,action='proposed',data={'fingerprint':fingerprint,'source_hash':source_hash}))
    await db.commit();return view(row)


# Register on the existing router; no duplicate application/router ownership.
from .artifacts import register
register(router)


@router.get('/brains/{brain_id}/proposals')
async def list_proposals(brain_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    enabled();brain=await require_brain(db,who,brain_id)
    return [view(row) for row in await db.scalars(select(LearningProposal).where(
        LearningProposal.brain_id==brain.id,LearningProposal.actor_id==who.id).order_by(LearningProposal.created_at.desc()).limit(100))]


class LearningReviewInput(Closed):
    fingerprint:str=Field(min_length=64,max_length=64)
    decision:Literal['promote','reject','revert']


@router.post('/proposals/{proposal_id}/review')
async def review(proposal_id:UUID,body:LearningReviewInput,who:Principal=Depends(principal),db=Depends(database)):
    enabled();row=await db.get(LearningProposal,str(proposal_id))
    if not row or row.actor_id!=who.id:raise HTTPException(404,'learning_proposal_not_found')
    brain=await require_brain(db,who,row.brain_id,True,lock=True)
    row=await db.scalar(select(LearningProposal).where(LearningProposal.id==row.id).with_for_update().execution_options(populate_existing=True))
    if body.fingerprint!=row.fingerprint:raise HTTPException(409,'learning_review_changed')
    target={'promote':'promoted','reject':'rejected','revert':'reverted'}[body.decision]
    if row.status==target:return view(row)
    source_hash=row.source_hash
    if body.decision!='revert':
        _,source_hash=await source(db,who,row.source_id,row.workspace_id)
        if source_hash!=row.source_hash:raise HTTPException(409,'learning_source_changed')
        safe(row.candidate)
    if body.decision=='revert':
        if row.status!='promoted':raise HTTPException(409,'learning_not_promoted')
        note=await db.get(BrainNote,row.note_id,with_for_update=True)
        if not note or note.brain_id!=brain.id or note.revision!=1 or note.content_version!=1 or note.trashed_at:
            raise HTTPException(409,'learning_note_changed_manual_review_required')
        note.trashed_at=now();note.revision+=1;brain.revision+=1
    else:
        if row.status!='pending':raise HTTPException(409,'learning_already_reviewed')
        if body.decision=='promote':
            note=await add_note(db,brain,who,'Reviewed conversation excerpt',row.candidate)
            row.note_id=note.id
    row.status=target
    ident=str(uuid5(UUID(row.id),'review:'+target))
    db.add(LearningAudit(id=ident,proposal_id=row.id,actor_id=who.id,action=target,
        data={'fingerprint':row.fingerprint,'source_hash':source_hash,'note_id':row.note_id,'data_only':True}))
    await db.commit();return view(row)
