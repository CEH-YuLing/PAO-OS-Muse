"""Owner-only, data-only legacy namespace handoff. Never read/copy a bot token."""
import re
from fastapi import HTTPException
from sqlalchemy import select,func,text,or_
from pao.access import membership
from pao.config import settings
from pao.models import (User,Member,ChatSession,Run,TelegramConnection,TelegramPeer,TelegramUpdate,TelegramDelivery,
    ChannelBinding,ChannelInbound,ChannelOutbox,TelegramLegacyMapping,TelegramLegacyPeerMap,TelegramLegacyMappingAudit)
from pao.modules.studio.contracts import digest
from .service import identity

async def owner(db,wid,who,lock=False):
    member=await membership(db,wid,who)
    if lock:member=await db.get(Member,(wid,who.id),with_for_update=True,populate_existing=True)
    user=await db.get(User,who.id,with_for_update=lock,populate_existing=True)
    if not member or member.role!='owner' or not user or not user.active:raise HTTPException(403,'telegram_mapping_owner_required')

async def lease(db):
    if not await db.scalar(text('SELECT pg_try_advisory_xact_lock(600005)')):raise HTTPException(409,'telegram_bridge_busy')

def public(mapping,connection):
    return {'mapping_id':mapping.id,'connection_id':connection.id,'workspace_id':mapping.workspace_id,'owner_id':mapping.owner_id,
        'version':connection.version,'status':connection.status,'peer_count':mapping.snapshot['peer_count'],
        'binding_count':mapping.snapshot['binding_count'],'held_delivery_count':mapping.snapshot['held_delivery_count'],
        'authority':'storage_only','transport_active':False,'provider_calls':False,'history_rewritten':False}

async def current(db,wid):
    row=await db.scalar(select(TelegramLegacyMapping).where(TelegramLegacyMapping.workspace_id==wid))
    return public(row,await db.get(TelegramConnection,row.connection_id)) if row else None

async def snapshot(db,wid,who,lock=False):
    await owner(db,wid,who,lock)
    result={'workspace_id':wid,'eligible':False,'reason':'no_legacy_peers','expected_version':0,'preview_hash':None,
        'peer_count':0,'binding_count':0,'held_delivery_count':0,'peers':[],
        'authority':'storage_only','transport_active':False,'provider_calls':False,'history_rewritten':False}
    async def blocked(reason):return {**result,'reason':reason},[],[],None
    if await db.scalar(select(TelegramConnection.id).where(TelegramConnection.kind=='legacy').limit(1)):
        return await blocked('legacy_already_mapped')
    if settings().telegram_enabled:return await blocked('host_telegram_must_be_off')
    if await db.scalar(select(TelegramPeer.id).where(TelegramPeer.connection_id.is_(None),TelegramPeer.workspace_id!=wid).limit(1)):
        return await blocked('legacy_scope_conflict')
    query=select(TelegramPeer).where(TelegramPeer.connection_id.is_(None),TelegramPeer.workspace_id==wid).order_by(TelegramPeer.id).limit(101)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    peers=list(await db.scalars(query))
    if not peers:return result,[],[],None
    if len(peers)>100:return await blocked('legacy_peer_limit')
    ids=[row.id for row in peers]
    query=select(ChannelBinding).where(ChannelBinding.channel=='telegram',ChannelBinding.connection_id.is_(None)).order_by(ChannelBinding.id).limit(101)
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    bindings=list(await db.scalars(query))
    if len(bindings)>100 or any(row.workspace_id!=wid or row.peer_id not in ids for row in bindings):return await blocked('legacy_scope_conflict')
    by_peer={row.peer_id:row for row in bindings};member_data=[]
    for peer in peers:
        if not re.fullmatch(r'[1-9][0-9]{0,15}',peer.telegram_user_id) or peer.telegram_user_id!=peer.chat_id:
            return await blocked('legacy_private_destination_required')
        user=await db.get(User,peer.user_id,with_for_update=lock,populate_existing=True)
        member=await db.get(Member,(wid,peer.user_id),with_for_update=lock,populate_existing=True)
        binding=by_peer.get(peer.id)
        if not user or not user.active or not member or member.role=='viewer' or (binding and (binding.actor_id!=peer.user_id or (binding.kind=='customer' and member.role!='operator'))):
            return await blocked('legacy_actor_unavailable')
        member_data.append([peer.user_id,user.active,member.role])
        for sid in {peer.session_id,binding.session_id if binding else None}-{None}:
            chat=await db.get(ChatSession,sid)
            if not chat or chat.workspace_id!=wid or chat.user_id!=peer.user_id:return await blocked('legacy_session_scope_invalid')
            if await db.scalar(select(Run.id).where(Run.session_id==sid,Run.status.in_(('queued','running'))).limit(1)):
                return await blocked('legacy_active_run')
    bid=[row.id for row in bindings]
    if await db.scalar(select(TelegramDelivery.id).where(TelegramDelivery.peer_id.in_(ids),TelegramDelivery.status=='sending').limit(1)) or await db.scalar(
        select(ChannelOutbox.id).where(ChannelOutbox.binding_id.in_(bid),ChannelOutbox.status=='sending').limit(1)):
        return await blocked('legacy_delivery_inflight')
    projected={};held=0
    for model,parent,col,fields in (
        (TelegramUpdate,TelegramUpdate.peer_id,ids,['id','update_id','peer_id','run_id','created_at']),
        (TelegramDelivery,TelegramDelivery.peer_id,ids,['id','peer_id','dedup_key','status','message_id','updated_at']),
        (ChannelInbound,ChannelInbound.binding_id,bid,['id','binding_id','external_key','run_id','status','purged_at']),
        (ChannelOutbox,ChannelOutbox.binding_id,bid,['id','binding_id','request_key','status','attempts','remote_id','updated_at'])):
        rows=(await db.execute(select(*(getattr(model,key) for key in fields)).where(parent.in_(col)).order_by(model.id).limit(10001))).all()
        if len(rows)>10000:return await blocked('legacy_history_limit')
        data=[[value.isoformat() if hasattr(value,'isoformat') else value for value in row] for row in rows]
        projected[model.__tablename__]=data
        if model in (TelegramDelivery,ChannelOutbox):held+=sum(row[fields.index('status')] in ('queued','unknown','failed') for row in rows)
    state={'workspace_id':wid,'owner_id':who.id,'members':member_data,
        'peers':[[p.id,p.user_id,p.telegram_user_id,p.chat_id,p.enabled,p.session_id] for p in peers],
        'bindings':[[b.id,b.peer_id,b.actor_id,b.brain_id,b.session_id,b.kind,b.mode,b.enabled,b.outbound_confirmed,b.retention_days,b.version] for b in bindings],
        'ledger':projected}
    sha=digest(state)
    info={'peer_count':len(peers),'binding_count':len(bindings),'held_delivery_count':held,'source_hash':sha}
    return {**result,**{k:v for k,v in info.items() if k!='source_hash'},'eligible':True,'reason':'ready','preview_hash':sha,
        'peers':[{'source_peer_id':p.id,'actor_id':p.user_id,'telegram_user_id':p.telegram_user_id,'chat_id':p.chat_id,'bound':p.id in by_peer} for p in peers]},peers,bindings,info

async def apply(db,wid,who,body):
    await lease(db);await owner(db,wid,who,True)
    key=str(body.request_key);fingerprint=digest(body.model_dump(mode='json'))
    saved=await db.scalar(select(TelegramLegacyMapping).where(TelegramLegacyMapping.workspace_id==wid,TelegramLegacyMapping.owner_id==who.id,TelegramLegacyMapping.request_key==key))
    if saved:
        if saved.content_hash!=fingerprint:raise HTTPException(409,'telegram_mapping_key_conflict')
        return public(saved,await db.get(TelegramConnection,saved.connection_id))
    preview,peers,bindings,info=await snapshot(db,wid,who,True)
    if not preview['eligible']:raise HTTPException(409,preview['reason'])
    if body.expected_version!=0 or preview['preview_hash']!=body.preview_hash:raise HTTPException(409,'telegram_mapping_preview_stale')
    connection=TelegramConnection(workspace_id=wid,owner_id=who.id,kind='legacy',bot_user_id=None,status='staged',version=1)
    db.add(connection);await db.flush()
    mapping=TelegramLegacyMapping(workspace_id=wid,connection_id=connection.id,owner_id=who.id,request_key=key,
        preview_hash=body.preview_hash,content_hash=fingerprint,snapshot=info,generation=1)
    db.add(mapping);await db.flush();by_peer={row.peer_id:row for row in bindings}
    for old in peers:
        peer=TelegramPeer(workspace_id=wid,user_id=old.user_id,telegram_user_id=old.telegram_user_id,chat_id=old.chat_id,
            connection_id=connection.id,session_id=None,enabled=False)
        db.add(peer);await db.flush();source=by_peer.get(old.id);target=None
        if source:
            target=ChannelBinding(workspace_id=wid,actor_id=source.actor_id,connection_id=connection.id,
                channel='telegram',identity_hash=identity('telegram',peer.telegram_user_id+':'+peer.chat_id,connection.id),
                peer_id=peer.id,kind=source.kind,retention_days=source.retention_days,brain_id=None,session_id=None,
                mode='quiet',enabled=False,outbound_confirmed=False,version=1)
            db.add(target);await db.flush()
        db.add(TelegramLegacyPeerMap(workspace_id=wid,mapping_id=mapping.id,source_peer_id=old.id,peer_id=peer.id,
            source_binding_id=source.id if source else None,binding_id=target.id if target else None))
    db.add(TelegramLegacyMappingAudit(workspace_id=wid,mapping_id=mapping.id,actor_id=who.id,request_key=key,content_hash=fingerprint,action='apply',version=1))
    await db.commit();return public(mapping,connection)

async def revoke(db,wid,who,body):
    await lease(db);await owner(db,wid,who,True)
    mapping=await db.get(TelegramLegacyMapping,str(body.mapping_id))
    if not mapping or mapping.workspace_id!=wid:raise HTTPException(404,'telegram_mapping_not_found')
    fingerprint=digest(body.model_dump(mode='json'));key=str(body.request_key)
    saved=await db.scalar(select(TelegramLegacyMappingAudit).where(TelegramLegacyMappingAudit.workspace_id==wid,TelegramLegacyMappingAudit.actor_id==who.id,TelegramLegacyMappingAudit.request_key==key))
    connection=await db.get(TelegramConnection,mapping.connection_id,with_for_update=True,populate_existing=True)
    if saved:
        if saved.mapping_id!=mapping.id or saved.content_hash!=fingerprint:raise HTTPException(409,'telegram_mapping_key_conflict')
        return public(mapping,connection)
    if connection.version!=body.version or connection.status!='staged':raise HTTPException(409,'telegram_mapping_version_conflict')
    connection.status='revoked';connection.version+=1
    db.add(TelegramLegacyMappingAudit(workspace_id=wid,mapping_id=mapping.id,actor_id=who.id,request_key=key,content_hash=fingerprint,action='revoke',version=connection.version))
    await db.commit();return public(mapping,connection)
