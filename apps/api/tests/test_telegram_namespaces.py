"""S3.1A real DB namespace/ledger gates; no credential or provider transport."""
from importlib import import_module
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.db import Session,engine
from pao.models import (Workspace,Member,TelegramConnection,TelegramPeer,TelegramUpdate,
    TelegramDelivery,ChannelBinding,ChannelInbound,ChannelOutbox,ChannelAudit,Run)
from pao.modules.channels import service,telegram_helpers
from pao.modules.studio.contracts import digest
from test_channels import channels_on
from test_telegram import peer,update


@pytest.fixture
async def namespaces(identity):
    async with Session.begin() as db:
        space=Workspace(name='Namespace SME B');db.add(space);await db.flush()
        db.add(Member(workspace_id=space.id,user_id=identity['user_id'],role='owner'))
        connections=[];peers=[];bindings=[]
        for wid,bot in ((identity['workspace'],'111'),(space.id,'222')):
            connection=TelegramConnection(workspace_id=wid,owner_id=identity['user_id'],bot_user_id=bot)
            db.add(connection);await db.flush();connections.append(connection)
            who=TelegramPeer(connection_id=connection.id,workspace_id=wid,user_id=identity['user_id'],
                telegram_user_id='12345',chat_id='12345')
            db.add(who);await db.flush();peers.append(who)
            binding=ChannelBinding(connection_id=connection.id,workspace_id=wid,actor_id=identity['user_id'],
                channel='telegram',identity_hash=service.identity('telegram','12345:12345',connection.id),
                peer_id=who.id,kind='personal',mode='quiet')
            db.add(binding);await db.flush();bindings.append(binding)
    return connections,peers,bindings


async def test_two_bots_same_ids_update_keys_and_outbox_independent(client,namespaces):
    connections,peers,bindings=namespaces
    assert connections[0].status==connections[1].status=='staged'
    assert bindings[0].identity_hash!=bindings[1].identity_hash
    async with Session.begin() as db:
        for connection,peer,binding in zip(connections,peers,bindings):
            db.add(TelegramUpdate(connection_id=connection.id,peer_id=peer.id,update_id=123))
            await telegram_helpers.queue(db,peer,'same-update','😀'*2000)
            await telegram_helpers.queue(db,peer,'same-update','😀'*2000)
            await service.queue(db,binding,'same-update','Namespace fixture')
            await service.queue(db,binding,'same-update','Namespace fixture')
            db.add(ChannelInbound(connection_id=connection.id,workspace_id=binding.workspace_id,binding_id=binding.id,
                external_key=digest('123'),content_hash=digest('fixture'),body='Fixture',status='quiet'))
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramUpdate))==2
        assert await db.scalar(select(func.count()).select_from(TelegramDelivery))==4 # two Unicode parts per bot
        assert await db.scalar(select(func.count()).select_from(ChannelOutbox))==2
        assert await db.scalar(select(func.count()).select_from(ChannelInbound))==2
        assert len({row.id for row in await db.scalars(select(TelegramUpdate))})==2


@pytest.mark.parametrize('kind',['peer','update','delivery','binding','inbound','outbox','audit'])
async def test_cross_namespace_and_cross_sme_children_denied(client,namespaces,kind):
    connections,peers,bindings=namespaces;a,b=connections
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            if kind=='peer':row=TelegramPeer(connection_id=a.id,workspace_id=b.workspace_id,user_id=a.owner_id,telegram_user_id='99',chat_id='99')
            elif kind=='update':row=TelegramUpdate(connection_id=a.id,peer_id=peers[1].id,update_id=88)
            elif kind=='delivery':row=TelegramDelivery(connection_id=a.id,peer_id=peers[1].id,dedup_key='cross',payload={})
            elif kind=='binding':row=ChannelBinding(connection_id=a.id,workspace_id=a.workspace_id,actor_id=a.owner_id,channel='telegram',peer_id=peers[1].id,identity_hash='c'*64,kind='personal')
            else:
                model={'inbound':ChannelInbound,'outbox':ChannelOutbox,'audit':ChannelAudit}[kind]
                extra={'external_key':'cross','body':'fixture','status':'quiet'} if kind=='inbound' else {'request_key':'cross','body':'fixture','kind':'manual'} if kind=='outbox' else {'request_key':'cross','actor_id':a.owner_id,'data':{}}
                row=model(connection_id=a.id,workspace_id=b.workspace_id,binding_id=bindings[1].id,content_hash='a'*64,**extra)
            db.add(row);await db.flush()


@pytest.mark.parametrize('kind',['peer','update','delivery'])
async def test_same_namespace_duplicate_still_denied(client,namespaces,kind):
    connection=namespaces[0][0];peer=namespaces[1][0]
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            if kind=='peer':db.add(TelegramPeer(connection_id=connection.id,workspace_id=connection.workspace_id,user_id=connection.owner_id,telegram_user_id='12345',chat_id='12345'))
            elif kind=='update':db.add_all([TelegramUpdate(connection_id=connection.id,peer_id=peer.id,update_id=7) for _ in range(2)])
            else:db.add_all([TelegramDelivery(connection_id=connection.id,peer_id=peer.id,dedup_key='same',payload={}) for _ in range(2)])
            await db.flush()


@pytest.mark.parametrize('kind',['peer','update','delivery'])
async def test_unmapped_legacy_uniqueness_is_preserved(client,identity,peer,kind):
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            if kind=='peer':db.add(TelegramPeer(workspace_id=peer.workspace_id,user_id=peer.user_id,telegram_user_id=peer.telegram_user_id,chat_id=peer.chat_id))
            elif kind=='update':db.add_all([TelegramUpdate(peer_id=peer.id,update_id=7) for _ in range(2)])
            else:db.add_all([TelegramDelivery(peer_id=peer.id,dedup_key='same',payload={}) for _ in range(2)])
            await db.flush()


async def test_staged_rows_never_route_or_send_with_global_token(client,namespaces,channels_on,monkeypatch):
    from pao.config import settings
    from pao.telegram import ingest,deliver
    monkeypatch.setattr(settings(),'telegram_enabled',True)
    monkeypatch.setattr(settings(),'telegram_bot_token','fixture-no-network')
    redis=AsyncMock();send=AsyncMock(side_effect=AssertionError('No provider'))
    async with Session.begin() as db:
        for peer,binding in zip(namespaces[1],namespaces[2]):
            assert not await telegram_helpers.permitted(db,peer)
            with pytest.raises(HTTPException) as exc:await service.actor(db,binding)
            assert exc.value.detail=='telegram_connection_transport_pending'
            await telegram_helpers.queue(db,peer,'staged','Fixture')
            await service.queue(db,binding,'staged','Fixture')
    await ingest(update(),redis);await deliver(send);await service.send_one(send)
    send.assert_not_awaited();redis.incr.assert_not_awaited()
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run))==0
        assert await db.scalar(select(func.count()).select_from(TelegramUpdate))==0
        assert all(row.status=='queued' for row in await db.scalars(select(TelegramDelivery)))
        assert all(row.status=='queued' and row.attempts==0 for row in await db.scalars(select(ChannelOutbox)))


@pytest.mark.parametrize('kind',['connection','peer','binding','update','delivery','inbound','outbox'])
async def test_namespace_history_not_rebound(client,namespaces,kind):
    connections,peers,bindings=namespaces;a,b=connections
    async with Session.begin() as db:
        db.add(TelegramUpdate(connection_id=a.id,peer_id=peers[0].id,update_id=71))
        await telegram_helpers.queue(db,peers[0],'immutable','Fixture')
        await service.queue(db,bindings[0],'immutable','Fixture')
        db.add(ChannelInbound(connection_id=a.id,workspace_id=a.workspace_id,binding_id=bindings[0].id,
            external_key='immutable',content_hash='a'*64,body='Fixture',status='quiet'))
    model={'connection':TelegramConnection,'peer':TelegramPeer,'binding':ChannelBinding,'update':TelegramUpdate,
        'delivery':TelegramDelivery,'inbound':ChannelInbound,'outbox':ChannelOutbox}[kind]
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            row=await db.scalar(select(model).order_by(model.created_at).limit(1))
            if kind=='connection':row.workspace_id=b.workspace_id
            else:row.connection_id=b.id
            await db.flush()


async def test_legacy_assignment_requires_new_versioned_mapping_not_repin(client,namespaces,peer):
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            row=await db.get(TelegramPeer,peer.id);row.connection_id=namespaces[0][0].id;await db.flush()
    async with Session() as db:assert (await db.get(TelegramPeer,peer.id)).connection_id is None


async def test_populated_downgrade_native_guard_atomic(client,namespaces):
    module=import_module('migrations.versions.0059_telegram_connection_namespaces')
    async with engine.connect() as db:
        before=await db.scalar(text('SELECT version_num FROM alembic_version'))
        try:
            def run(connection):
                with Operations.context(MigrationContext.configure(connection)):module.downgrade()
            with pytest.raises(RuntimeError,match='Telegram connection history'):await db.run_sync(run)
        finally:await db.rollback()
        assert await db.scalar(text('SELECT version_num FROM alembic_version'))==before
        assert await db.scalar(text('SELECT count(*) FROM telegram_connections'))==2


async def test_revoke_is_monotonic_and_delete_refused(client,namespaces):
    ident=namespaces[0][0].id
    async with Session.begin() as db:
        row=await db.get(TelegramConnection,ident);row.status='revoked';row.version=2
    for action in ('resurrect','delete'):
        with pytest.raises(DBAPIError):
            async with Session.begin() as db:
                row=await db.get(TelegramConnection,ident)
                if action=='delete':await db.delete(row)
                else:row.status='staged';row.version=3
                await db.flush()
