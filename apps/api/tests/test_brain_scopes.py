from uuid import uuid4
import time

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from pao.auth import Principal
from pao.config import settings
from pao.db import Session
from pao.models import Brain, BrainMember, Brand, Member, Memory, Workspace
from pao.modules.brains.access import default_brain, legacy_facts, require_brain


@pytest.fixture
def brains_on(monkeypatch):
    monkeypatch.setattr(settings(), 'brain_manager_enabled', True)


def actor(user_id):
    return Principal(user_id, int(time.time()) + 600)


async def test_default_is_idempotent_and_does_not_copy_facts(identity, brains_on):
    async with Session.begin() as db:
        who = actor(identity['user_id'])
        first = await default_brain(db, who, identity['workspace'])
        second = await default_brain(db, who, identity['workspace'])
        assert first.id == second.id and first.legacy_default
        assert await db.scalar(select(func.count()).select_from(Memory)) == 0


async def test_private_brain_not_visible_even_to_other_workspace_owner(identity, brains_on):
    async with Session.begin() as db:
        brain = await default_brain(db, actor(identity['user_id']), identity['workspace'])
        others = list(await db.scalars(select(Member).where(Member.workspace_id == identity['workspace'],
                                                          Member.user_id != identity['user_id'])))
        others[0].role = 'owner'
        await db.flush()
        with pytest.raises(HTTPException) as error:
            await require_brain(db, actor(others[0].user_id), brain.id)
        assert error.value.status_code == 404


async def test_legacy_mapping_keeps_user_brand_and_grant_privacy(identity, brains_on):
    async with Session.begin() as db:
        wid, owner = identity['workspace'], identity['user_id']
        brand = Brand(workspace_id=wid, name='A')
        db.add(brand); await db.flush()
        other = await db.scalar(select(Member.user_id).where(Member.workspace_id == wid, Member.user_id != owner))
        private = await default_brain(db, actor(owner), wid)
        branded = await default_brain(db, actor(owner), wid, brand.id)
        custom = Brain(workspace_id=wid, owner_id=owner, name='Custom')
        db.add(custom); await db.flush()
        for uid, bid, key in ((owner,None,'own'),(owner,brand.id,'brand'),(other,None,'other')):
            db.add(Memory(workspace_id=wid,user_id=uid,brand_id=bid,key=key,value=key,
                          fingerprint=key.ljust(64,'0'),status='active',importance=3))
        db.add(BrainMember(brain_id=private.id,workspace_id=wid,user_id=other,role='editor'))
        await db.flush()
        assert [x.key for x in await legacy_facts(db, actor(owner), private.id)] == ['own']
        assert [x.key for x in await legacy_facts(db, actor(owner), branded.id)] == ['brand']
        assert await legacy_facts(db, actor(owner), custom.id) == []
        assert await legacy_facts(db, actor(other), private.id) == []
        assert await db.scalar(select(func.count()).select_from(Memory)) == 3


async def test_viewer_cannot_write_with_editor_grant(identity, brains_on):
    async with Session.begin() as db:
        wid = identity['workspace']
        brain = await default_brain(db, actor(identity['user_id']), wid)
        other = await db.scalar(select(Member).where(Member.workspace_id == wid,Member.user_id != identity['user_id']))
        other.role = 'viewer'
        db.add(BrainMember(brain_id=brain.id,workspace_id=wid,user_id=other.user_id,role='editor'))
        await db.flush()
        assert (await require_brain(db, actor(other.user_id), brain.id)).id == brain.id
        with pytest.raises(HTTPException) as error:
            await require_brain(db, actor(other.user_id), brain.id, write=True)
        assert error.value.status_code == 403


async def test_archive_blocks_new_writes_but_preserves_read(identity, brains_on):
    from pao.models import now
    async with Session.begin() as db:
        who = actor(identity['user_id'])
        brain = await default_brain(db, who, identity['workspace'])
        brain.archived_at = now(); await db.flush()
        with pytest.raises(HTTPException) as error:
            await require_brain(db, who, brain.id, write=True)
        assert error.value.status_code == 409
        assert (await require_brain(db, who, brain.id, allow_archived=True)).id == brain.id


async def test_disabled_gate_denies_known_id(identity, monkeypatch):
    monkeypatch.setattr(settings(),'brain_manager_enabled',False)
    async with Session() as db:
        with pytest.raises(HTTPException) as error:
            await require_brain(db, actor(identity['user_id']), uuid4())
        assert error.value.status_code == 503


async def test_composite_fk_blocks_cross_workspace_brand(identity):
    async with Session() as db:
        workspace = Workspace(name='Different tenant')
        db.add(workspace); await db.flush()
        brand = Brand(workspace_id=workspace.id,name='Foreign')
        db.add(brand); await db.flush()
        db.add(Brain(workspace_id=identity['workspace'],owner_id=identity['user_id'],brand_id=brand.id,name='Invalid'))
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()
