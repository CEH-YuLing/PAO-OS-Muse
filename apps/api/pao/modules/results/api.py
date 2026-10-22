from uuid import UUID,uuid5
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field
from sqlalchemy import select
from ...access import membership
from ...auth import Principal,principal
from ...config import settings
from ...db import database
from ...models import StudioExecution,StudioEvent,ResultInboxReceipt,ResultDelivery,Member,now,GoalExecution,GoalResultReceipt,GoalResultDelivery,GoalEvent
from ..studio.contracts import Closed,digest

router=APIRouter(prefix='/v1/results',tags=['result-inbox'])
TERMINAL={'completed','cancelled','manual_review'}


def enabled():
    if not settings().result_inbox_enabled:raise HTTPException(409,'result_inbox_disabled')


async def source(db,ident,who):
    row=await db.get(StudioExecution,str(ident),with_for_update=True)
    if not row:
        row=await db.get(GoalExecution,str(ident),with_for_update=True)
        if not row:raise HTTPException(404,'result_not_found')
        await membership(db,row.workspace_id,who)
        from ..goals import runner
        from ..goals.evidence import verify_admission
        from temporalio.exceptions import ApplicationError
        from ..goals.control import TERMINAL as GOAL_TERMINAL
        if row.status not in GOAL_TERMINAL:raise HTTPException(409,'result_not_terminal')
        try:
            await verify_admission(db,row)
            control=await runner.reconstruct(db,row)
        except (ApplicationError,ValueError):raise HTTPException(409,'result_evidence_invalid')
        if not control:raise HTTPException(409,'result_evidence_invalid')
        event=await db.get(GoalEvent,runner.event_id(row,'transition:'+str(row.sequence)))
        return row,digest({'event_id':event.id,'data':event.data,'content_hash':event.content_hash})
    await membership(db,row.workspace_id,who)
    if row.status not in TERMINAL or row.status!=row.state.get('status'):
        raise HTTPException(409,'result_not_terminal')
    event=await db.get(StudioEvent,str(uuid5(UUID(row.id),'projection:'+str(row.sequence))))
    if (not event or event.action!='p62_projection' or event.workspace_id!=row.workspace_id or
        event.definition_id!=row.definition_id or event.actor_id!=row.actor_id or
        event.data.get('state')!=row.state):raise HTTPException(409,'result_evidence_invalid')
    return row,digest({'event_id':event.id,'data':event.data})

def models(row):
    return (GoalResultReceipt,GoalResultDelivery,'goal_dry_run') if isinstance(row,GoalExecution) else (ResultInboxReceipt,ResultDelivery,'studio_dry_run')


@router.get('/status')
async def status(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    return {'enabled':settings().result_inbox_enabled,'sources':['studio_dry_run','goal_dry_run'],
        'destinations':['in_app'],'external_delivery_enabled':False}


@router.get('')
async def inbox(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    enabled();wid=str(workspace_id);await membership(db,wid,who)
    rows=list(await db.scalars(select(StudioExecution).where(StudioExecution.workspace_id==wid,
        StudioExecution.status.in_(TERMINAL)).order_by(StudioExecution.updated_at.desc()).limit(100)))
    from ..goals.control import TERMINAL as GOAL_TERMINAL
    rows+=list(await db.scalars(select(GoalExecution).where(GoalExecution.workspace_id==wid,
        GoalExecution.status.in_(GOAL_TERMINAL)).order_by(GoalExecution.updated_at.desc()).limit(100)))
    rows=sorted(rows,key=lambda r:r.updated_at,reverse=True)[:100]
    result=[]
    for item in rows:
        row,fingerprint=await source(db,item.id,who)
        Receipt,Delivery,kind=models(row)
        receipt=await db.scalar(select(Receipt).where(Receipt.workspace_id==wid,
            Receipt.user_id==who.id,Receipt.source_id==row.id,Receipt.source_hash==fingerprint))
        notice=await db.scalar(select(Delivery).where(Delivery.source_id==row.id,Delivery.source_hash==fingerprint,Delivery.user_id==who.id,Delivery.status=='delivered'))
        result.append({'id':row.id,'source':kind,'status':row.status,'source_hash':fingerprint,
            'notification':bool(notice),'delivery_id':notice.id if notice else None,
            'read':receipt is not None,'acknowledged':bool(receipt and receipt.ack_at),
            'dry_run':True,'business_success_proven':False,'sequence':row.sequence})
    return result


class ResultMarkInput(Closed):
    source_hash:str
    action:Literal['read','ack']


@router.post('/{source_id}/receipt')
async def mark(source_id:UUID,body:ResultMarkInput,who:Principal=Depends(principal),db=Depends(database)):
    enabled();row,fingerprint=await source(db,source_id,who)
    if body.source_hash!=fingerprint:raise HTTPException(409,'result_source_changed')
    ident=str(uuid5(UUID(row.id),'receipt:'+who.id+':'+fingerprint))
    Receipt,_,_=models(row)
    saved=await db.get(Receipt,ident)
    if not saved:
        saved=Receipt(id=ident,workspace_id=row.workspace_id,user_id=who.id,
            source_id=row.id,source_hash=fingerprint);db.add(saved)
    if body.action=='ack' and not saved.ack_at:saved.ack_at=now()
    await db.commit()
    return {'read':True,'acknowledged':bool(saved.ack_at),'source_hash':fingerprint}


class ResultDeliveryInput(Closed):
    source_hash:str
    recipient_id:str=Field(pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    destination:Literal['in_app']='in_app'


@router.post('/{source_id}/deliveries')
async def deliver(source_id:UUID,body:ResultDeliveryInput,who:Principal=Depends(principal),db=Depends(database)):
    enabled();row,fingerprint=await source(db,source_id,who)
    await membership(db,row.workspace_id,who,write=True)
    if body.source_hash!=fingerprint:raise HTTPException(409,'result_source_changed')
    recipient=str(UUID(body.recipient_id))
    member=await db.get(Member,(row.workspace_id,recipient))
    if not member:raise HTTPException(404,'result_recipient_not_found')
    ident=str(uuid5(UUID(row.id),'delivery:'+recipient+':'+fingerprint+':in_app'))
    _,Delivery,_=models(row)
    saved=await db.get(Delivery,ident)
    if not saved:
        # Inbox source and recipient membership already exist in this DB.
        # Delivery is local visibility, not Telegram/email or a read ACK.
        saved=Delivery(id=ident,workspace_id=row.workspace_id,user_id=recipient,
            source_id=row.id,source_hash=fingerprint,status='pending',requested_by=who.id)
        db.add(saved)
    elif saved.status=='failed' and saved.attempts<5 and saved.requested_by==who.id:
        saved.status='pending';saved.error_code=None
    await db.commit()
    from .outbox import dispatch_one
    await dispatch_one(Delivery,ident)
    await db.refresh(saved)
    return delivery_view(saved)

def delivery_view(saved):
    return {'id':saved.id,'status':saved.status,'destination':'in_app','external_send':False,
        'recipient_id':saved.user_id,'source_hash':saved.source_hash,'attempts':saved.attempts,
        'error_code':saved.error_code,'delivered_at':saved.delivered_at}

@router.get('/{source_id}/deliveries')
async def deliveries(source_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    enabled();row,_=await source(db,source_id,who);member=await membership(db,row.workspace_id,who)
    _,Delivery,_=models(row)
    query=select(Delivery).where(Delivery.source_id==row.id).order_by(Delivery.created_at.desc()).limit(100)
    if member.role not in ('owner','admin'):query=query.where(Delivery.user_id==who.id)
    return [delivery_view(d) for d in await db.scalars(query)]
