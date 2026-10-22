"""Derived means bounded extractive composition, not invented model facts.

All promotion stays data-only; source text never grants execution authority.
"""
import hashlib
from uuid import UUID,uuid5
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field
from sqlalchemy import select,func
from ...auth import Principal,principal
from ...db import database
from ...models import ArtifactLearningProposal as Proposal,ArtifactLearningAudit as Audit,LearningProposal,BrainFile,BrainNote,User,now
from ..brains.access import require_brain
from ..brains.notes import add_note,detail
from ..brains.files import validate_bytes
from ..studio.contracts import Closed,digest

class Segment(Closed):
    start:int=Field(ge=0,le=1048576)
    end:int=Field(ge=1,le=1048576)
class ArtifactInput(Closed):
    source_id:UUID=Field(strict=False)
    derivation:Literal['quote','extractive_summary_v1']='quote'
    candidate:str|None=Field(default=None,min_length=3,max_length=2000)
    segments:list[Segment]=Field(default_factory=list,max_length=5)
class ArtifactCreate(ArtifactInput):
    confirmation_hash:str=Field(pattern='^[a-f0-9]{64}$')
class ArtifactReview(Closed):
    fingerprint:str=Field(pattern='^[a-f0-9]{64}$')
    decision:Literal['promote','reject','revert']

async def source(db,who,brain,ident):
    row=await db.scalar(select(BrainFile).where(BrainFile.id==str(ident),BrainFile.brain_id==brain.id,BrainFile.workspace_id==brain.workspace_id).with_for_update())
    if not row:raise HTTPException(404,'learning_source_not_found')
    if row.trashed_at:raise HTTPException(409,'learning_source_not_eligible')
    raw=bytes(row.content)
    if row.sha256!=hashlib.sha256(raw).hexdigest() or row.size!=len(raw):raise HTTPException(409,'learning_source_integrity_invalid')
    text=validate_bytes(raw)
    from .api import safe
    safe(text)
    return row,text,digest({'id':row.id,'brain_id':brain.id,'revision':row.revision,'sha256':row.sha256,'name':row.name,'mime':row.mime})

def derive(body,text,source_hash):
    from .api import safe
    segments=[]
    if body.derivation=='quote':
        if not body.candidate or body.segments or body.candidate not in text:raise HTTPException(422,'learning_candidate_must_quote_source')
        start=text.index(body.candidate);candidate=body.candidate
        segments=[{'start':start,'end':start+len(candidate),'text_hash':digest(candidate)}]
    else:
        if body.candidate is not None or len(body.segments)<2:raise HTTPException(422,'learning_derivation_invalid')
        end=0;parts=[]
        for segment in body.segments:
            if segment.start<end or not segment.start<segment.end<=len(text):raise HTTPException(422,'learning_segments_invalid')
            part=text[segment.start:segment.end];parts.append(part);end=segment.end
            segments.append({'start':segment.start,'end':segment.end,'text_hash':digest(part)})
        candidate='\n'.join(parts)
    if not 3<=len(candidate)<=2000:raise HTTPException(422,'learning_candidate_bounds')
    safe(candidate)
    fingerprint=digest({'source_hash':source_hash,'candidate':candidate,'derivation':body.derivation,'segments':segments})
    return candidate,segments,fingerprint

def view(row):
    return {'id':row.id,'brain_id':row.brain_id,'source_id':row.source_id,'source_hash':row.source_hash,'candidate':row.candidate,
        'fingerprint':row.fingerprint,'derivation':row.derivation,'segments':row.segments,'status':row.status,'note_id':row.note_id,
        'diff':{'before':None,'after':row.candidate},'promotion_target':'data_only_note','automatic_promotion':False,
        'policy_or_code_modified':False,'model_calls':False}

def register(router):
    @router.post('/brains/{brain_id}/artifact-preview')
    async def preview_artifact(brain_id:UUID,body:ArtifactInput,who:Principal=Depends(principal),db=Depends(database)):
        from .api import enabled
        enabled();brain=await require_brain(db,who,brain_id,True,lock=True)
        row,text,source_hash=await source(db,who,brain,body.source_id)
        candidate,segments,fingerprint=derive(body,text,source_hash)
        return {'candidate':candidate,'segments':segments,'source_hash':source_hash,'confirmation_hash':fingerprint,
            'source_id':row.id,'derivation':body.derivation,'diff':{'before':None,'after':candidate},'creates_note':False,'model_calls':False}

    @router.post('/brains/{brain_id}/artifact-proposals')
    async def propose_artifact(brain_id:UUID,body:ArtifactCreate,who:Principal=Depends(principal),db=Depends(database)):
        from .api import enabled
        enabled();brain=await require_brain(db,who,brain_id,True,lock=True)
        row,text,source_hash=await source(db,who,brain,body.source_id);candidate,segments,fingerprint=derive(body,text,source_hash)
        if body.confirmation_hash!=fingerprint:raise HTTPException(409,'learning_preview_changed')
        saved=await db.scalar(select(Proposal).where(Proposal.brain_id==brain.id,Proposal.actor_id==who.id,Proposal.fingerprint==fingerprint))
        if saved:return view(saved)
        await db.get(User,who.id,with_for_update=True)
        day=now().replace(hour=0,minute=0,second=0,microsecond=0)
        count=0
        for Model in (LearningProposal,Proposal):
            count+=await db.scalar(select(func.count(Model.id)).where(Model.actor_id==who.id,Model.workspace_id==brain.workspace_id,Model.created_at>=day))
        if count>=10:raise HTTPException(429,'learning_daily_budget_exhausted')
        saved=Proposal(workspace_id=brain.workspace_id,brain_id=brain.id,actor_id=who.id,source_id=row.id,source_hash=source_hash,candidate=candidate,fingerprint=fingerprint,derivation=body.derivation,segments=segments)
        db.add(saved);await db.flush();db.add(Audit(proposal_id=saved.id,actor_id=who.id,action='proposed',data={'fingerprint':fingerprint,'source_hash':source_hash,'data_only':True}))
        await db.commit();return view(saved)

    @router.get('/brains/{brain_id}/artifact-proposals')
    async def list_artifact_proposals(brain_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
        from .api import enabled
        enabled();brain=await require_brain(db,who,brain_id)
        return [view(row) for row in await db.scalars(select(Proposal).where(Proposal.brain_id==brain.id,Proposal.actor_id==who.id).order_by(Proposal.created_at.desc()).limit(100))]

    @router.post('/artifact-proposals/{proposal_id}/review')
    async def review_artifact(proposal_id:UUID,body:ArtifactReview,who:Principal=Depends(principal),db=Depends(database)):
        from .api import enabled,safe
        enabled();row=await db.get(Proposal,str(proposal_id))
        if not row or row.actor_id!=who.id:raise HTTPException(404,'learning_proposal_not_found')
        brain=await require_brain(db,who,row.brain_id,True,lock=True)
        row=await db.scalar(select(Proposal).where(Proposal.id==row.id).with_for_update().execution_options(populate_existing=True))
        if body.fingerprint!=row.fingerprint:raise HTTPException(409,'learning_review_changed')
        target={'promote':'promoted','reject':'rejected','revert':'reverted'}[body.decision]
        if row.status==target:return view(row)
        if body.decision=='revert':
            if row.status!='promoted':raise HTTPException(409,'learning_not_promoted')
            note=await db.get(BrainNote,row.note_id,with_for_update=True)
            if not note or note.brain_id!=brain.id or note.revision!=1 or note.content_version!=1 or note.trashed_at:
                raise HTTPException(409,'learning_note_changed_manual_review_required')
            if (await detail(db,note))['content']!=row.candidate:raise HTTPException(409,'learning_note_changed_manual_review_required')
            note.trashed_at=now();note.revision+=1;brain.revision+=1
        else:
            if row.status!='pending':raise HTTPException(409,'learning_already_reviewed')
            _,text,source_hash=await source(db,who,brain,row.source_id)
            if source_hash!=row.source_hash:raise HTTPException(409,'learning_source_changed')
            safe(row.candidate)
            if body.decision=='promote':row.note_id=(await add_note(db,brain,who,'Reviewed artifact knowledge',row.candidate)).id
        row.status=target
        db.add(Audit(id=str(uuid5(UUID(row.id),'review:'+target)),proposal_id=row.id,actor_id=who.id,action=target,data={'fingerprint':row.fingerprint,'source_hash':row.source_hash,'note_id':row.note_id,'data_only':True}))
        await db.commit();return view(row)
