"""Owner/admin channel management; customers never receive an internal JWT."""
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy import select
from pao.access import membership
from pao.auth import principal,Principal,rate_limit
from pao.db import database
from pao.config import settings
from pao.models import ChannelBinding,ChannelInbound,ChannelOutbox,ChannelAudit,TelegramPeer,Run,Member,now
from pao.modules.studio.contracts import Closed,digest
from typing import Literal
from . import service

router=APIRouter(prefix='/v1/channels',tags=['channels'])

async def manage(db,wid,who):
    member=await membership(db,wid,who)
    if member.role not in ('owner','admin'):raise HTTPException(403,'channel_management_denied')

async def owned(db,ident,who,lock=False):
    row=await db.get(ChannelBinding,str(ident),with_for_update=lock,populate_existing=lock)
    if not row:raise HTTPException(404,'channel_not_found')
    await manage(db,row.workspace_id,who)
    if lock and row.connection_id is not None:
        # Native setup/pairing/activation UI comes in S3.3. Existing endpoints
        # must not become an implicit authority to activate/edit scoped bots.
        raise HTTPException(503,'telegram_scoped_setup_pending')
    return row

def view(row):
    return {'id':row.id,'workspace_id':row.workspace_id,'actor_id':row.actor_id,'channel':row.channel,'brain_id':row.brain_id,
        'session_id':row.session_id,'kind':row.kind,'mode':row.mode,'enabled':row.enabled,'outbound_confirmed':row.outbound_confirmed,
        'retention_days':row.retention_days,'version':row.version}

class BindingIn(Closed):
    workspace_id:UUID=Field(strict=False)
    actor_id:UUID=Field(strict=False)
    channel:Literal['local','telegram']='local'
    external_identity:str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_:@. -]+$')
    kind:Literal['personal','customer']='personal'
    brain_id:str|None=Field(default=None,pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    peer_id:str|None=Field(default=None,pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    retention_days:int=Field(default=7,ge=1,le=30)

class Envelope(Closed):
    message_key:str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_:@. -]+$')
    text:str=Field(min_length=1,max_length=2000)

class Control(Closed):
    request_key:UUID=Field(strict=False)
    version:int=Field(ge=1)
    action:Literal['auto','human','quiet','enable','disable','allow_outbound','deny_outbound']
    confirm_destination:bool=False

class Reply(Closed):
    request_key:UUID=Field(strict=False)
    text:str=Field(min_length=1,max_length=2000)

class Reconcile(Closed):
    request_key:UUID=Field(strict=False)
    remote_id:str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_:-]+$')
    observed_delivered:Literal[True]

@router.get('/status')
async def status(workspace_id:UUID,who=Depends(principal),db=Depends(database)):
    await manage(db,str(workspace_id),who)
    return {'enabled':settings().channels_enabled,'customer_autoreply_enabled':settings().channel_autoreply_enabled,
        'implemented':['local','telegram'],'unimplemented':['zalo','slack','whatsapp'],'outbound_requires_destination_confirmation':True,
        'live_channel_accepted':False,'customer_profile':'grounded_excerpts_only_no_tools'}

@router.get('/bindings')
async def bindings(workspace_id:UUID,who=Depends(principal),db=Depends(database)):
    await manage(db,str(workspace_id),who)
    return [view(r) for r in await db.scalars(select(ChannelBinding).where(ChannelBinding.workspace_id==str(workspace_id)).order_by(ChannelBinding.created_at.desc()).limit(100))]

@router.post('/bindings',status_code=201)
async def create(body:BindingIn,request:Request,who=Depends(principal),db=Depends(database)):
    service.enabled();wid=str(body.workspace_id);await manage(db,wid,who)
    await rate_limit(request.app.state.redis,'channel-create',who.id,10,60)
    if body.kind=='personal' and str(body.actor_id)!=who.id:raise HTTPException(403,'personal_actor_must_be_self')
    fingerprint=service.identity(body.channel,body.external_identity)
    saved=await db.scalar(select(ChannelBinding).where(ChannelBinding.channel==body.channel,ChannelBinding.identity_hash==fingerprint))
    if saved:
        if saved.workspace_id!=wid:raise HTTPException(409,'channel_identity_already_bound')
        expected=(str(body.actor_id),body.kind,str(body.brain_id) if body.brain_id else None,str(body.peer_id) if body.peer_id else None,body.retention_days)
        if (saved.actor_id,saved.kind,saved.brain_id,saved.peer_id,saved.retention_days)!=expected:raise HTTPException(409,'channel_identity_conflict')
        return view(saved)
    row=ChannelBinding(workspace_id=wid,actor_id=str(body.actor_id),channel=body.channel,identity_hash=fingerprint,kind=body.kind,
        brain_id=str(body.brain_id) if body.brain_id else None,peer_id=str(body.peer_id) if body.peer_id else None,retention_days=body.retention_days,
        mode='quiet',enabled=True,outbound_confirmed=False,version=1)
    await service.actor(db,row)
    if row.brain_id:
        from pao.modules.brains.access import require_brain
        await require_brain(db,who,row.brain_id,True)
    if body.channel=='telegram':
        peer=await db.get(TelegramPeer,row.peer_id) if row.peer_id else None
        if not peer or peer.user_id!=row.actor_id or peer.workspace_id!=wid or fingerprint!=service.identity('telegram',peer.telegram_user_id+':'+peer.chat_id):raise HTTPException(422,'existing_allowlisted_peer_required')
        if body.kind=='customer':
            from pao.models import TelegramUpdate
            if peer.session_id or await db.scalar(select(TelegramUpdate.update_id).where(TelegramUpdate.peer_id==peer.id).limit(1)):
                raise HTTPException(409,'customer_peer_has_legacy_history')
    elif row.peer_id:raise HTTPException(422,'local_peer_invalid')
    from sqlalchemy.exc import IntegrityError
    db.add(row)
    try:await db.commit()
    except IntegrityError:await db.rollback();raise HTTPException(409,'channel_identity_conflict') from None
    return view(row)

@router.post('/bindings/{binding_id}/control')
async def control(binding_id:UUID,body:Control,who=Depends(principal),db=Depends(database)):
    row=await owned(db,binding_id,who,True)
    if body.action not in ('disable','human','quiet','deny_outbound'):service.enabled()
    await service.control(db,row,who,body);await db.commit();return view(row)

@router.post('/bindings/{binding_id}/inbound',status_code=202)
async def inbound(binding_id:UUID,body:Envelope,request:Request,who=Depends(principal),db=Depends(database)):
    row=await owned(db,binding_id,who,True)
    if row.channel!='local':raise HTTPException(403,'native_adapter_required')
    receipt=await service.ingest(db,row,body.message_key,body.text,request.app.state.redis)
    await db.commit()
    return {'id':receipt.id,'status':receipt.status,'run_id':receipt.run_id,'session_id':row.session_id}

@router.get('/bindings/{binding_id}/inbox')
async def inbox(binding_id:UUID,who=Depends(principal),db=Depends(database)):
    row=await owned(db,binding_id,who)
    values=[]
    for receipt in await db.scalars(select(ChannelInbound).where(ChannelInbound.binding_id==row.id).order_by(ChannelInbound.created_at.desc()).limit(100)):
        run=await db.get(Run,receipt.run_id) if receipt.run_id else None
        response=None
        if run:
            from pao.modules.knowledge.conversations import run_visible
            response=run.response if await run_visible(db,run,who) else '[Nguồn không còn được phép truy cập]'
        # A connection administrator is not implicitly the private actor. Never
        # expose that actor's inbound prompts merely through management rights.
        private=row.connection_id is not None and row.actor_id!=who.id
        values.append({'id':receipt.id,'status':receipt.status,'text':None if private else receipt.body,'run_id':receipt.run_id,'run_status':run.status if run else None,'response':None if private else response,'created_at':receipt.created_at,'purged':bool(receipt.purged_at)})
    return values

@router.post('/bindings/{binding_id}/reply',status_code=201)
async def reply(binding_id:UUID,body:Reply,request:Request,who=Depends(principal),db=Depends(database)):
    service.enabled();binding=await owned(db,binding_id,who,True);await service.actor(db,binding)
    if binding.mode!='human':raise HTTPException(409,'human_takeover_required')
    await rate_limit(request.app.state.redis,'channel-reply',who.id,20,60)
    row=await service.queue(db,binding,'manual:'+str(body.request_key),body.text,'manual')
    await db.commit();return {'id':row.id,'status':row.status,'external_send_performed':False}

@router.get('/bindings/{binding_id}/outbox')
async def outbox(binding_id:UUID,who=Depends(principal),db=Depends(database)):
    binding=await owned(db,binding_id,who)
    values=[]
    for r in await db.scalars(select(ChannelOutbox).where(ChannelOutbox.binding_id==binding.id).order_by(ChannelOutbox.created_at.desc()).limit(100)):
        visible=await service.result_visible(db,binding,r,who)
        values.append({'id':r.id,'status':r.status,'kind':r.kind,'attempts':r.attempts,'error_code':r.error_code,'remote_id':r.remote_id,
            'text':r.body if visible else '[Nguồn không còn được phép truy cập]'})
    return values

@router.post('/outbox/{delivery_id}/reconcile')
async def reconcile(delivery_id:UUID,body:Reconcile,who=Depends(principal),db=Depends(database)):
    delivery=await db.get(ChannelOutbox,str(delivery_id))
    if not delivery:raise HTTPException(404,'channel_delivery_not_found')
    binding=await owned(db,delivery.binding_id,who,True)
    delivery=await db.get(ChannelOutbox,delivery.id,with_for_update=True,populate_existing=True)
    key='reconcile:'+str(body.request_key);fingerprint=digest({'delivery_id':delivery.id,**body.model_dump(mode='json')})
    previous=await db.scalar(select(ChannelAudit).where(ChannelAudit.binding_id==binding.id,ChannelAudit.request_key==key))
    if previous:
        if previous.content_hash!=fingerprint:raise HTTPException(409,'channel_reconcile_key_conflict')
    else:
        if delivery.status!='unknown':raise HTTPException(409,'channel_delivery_not_unknown')
        delivery.status='sent';delivery.remote_id=body.remote_id;delivery.error_code=None;delivery.updated_at=now()
        db.add(ChannelAudit(workspace_id=binding.workspace_id,binding_id=binding.id,connection_id=binding.connection_id,actor_id=who.id,request_key=key,content_hash=fingerprint,data={'action':'manual_reconcile','delivery_id':delivery.id,'remote_id':body.remote_id,'owner_observation':True}))
    await db.commit();return {'id':delivery.id,'status':delivery.status,'remote_id':delivery.remote_id,'source':'owner_observation_not_provider_query'}

@router.get('/bindings/{binding_id}/audit')
async def audits(binding_id:UUID,who=Depends(principal),db=Depends(database)):
    row=await owned(db,binding_id,who)
    return [{'id':a.id,'data':a.data,'created_at':a.created_at} for a in await db.scalars(select(ChannelAudit).where(ChannelAudit.binding_id==row.id).order_by(ChannelAudit.created_at.desc()).limit(100))]

@router.post('/bindings/{binding_id}/purge-expired')
async def purge(binding_id:UUID,who=Depends(principal),db=Depends(database)):
    service.enabled();row=await owned(db,binding_id,who)
    return await service.purge_expired(row.id)
