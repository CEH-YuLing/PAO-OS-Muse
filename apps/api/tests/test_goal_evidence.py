"""Provenance reads from real PostgreSQL; no Temporal/provider/goal execution."""
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from pao.config import settings
from pao.db import Session
from pao.models import Goal, GoalExecution, GoalCommand, GoalEvent, Member, User, StudioExecution
from pao.modules.goals.evidence import verify_admission
from test_goal_admission import draft, goal_gates


async def admitted(client, identity):
    goal, plan, url, body = await draft(client, identity)
    response = await client.post(url, headers=identity['owner'], json=body)
    assert response.status_code == 201, response.text
    return goal, response.json(), body


async def test_evidence_read_is_gate_independent_and_has_no_side_effect(client, identity, goal_gates):
    goal, value, body = await admitted(client, identity)
    settings().goal_admission_enabled = False
    async with Session.begin() as db:
        row = await db.get(GoalExecution, value['execution_id'])
        snapshot = await verify_admission(db, row)
        assert snapshot['sha256'] == body['proposal']['snapshot_hash']
        assert await db.scalar(select(func.count(GoalEvent.id))) == 2
        assert await db.scalar(select(func.count(GoalCommand.id))) == 1
        assert await db.scalar(select(func.count(StudioExecution.id))) == 0
        assert row.status == 'starting' and row.sequence == 0


@pytest.mark.parametrize('field,value', [('title','Changed'), ('description','Changed'),
    ('success_criteria',['Different']), ('status','completed'), ('version',2), ('owner_id',None)])
async def test_source_mutation_without_version_bump_is_rejected(client, identity, goal_gates, field, value):
    goal, execution, body = await admitted(client, identity)
    async with Session.begin() as db:
        row = await db.get(Goal, goal['id'])
        if field == 'owner_id':
            value = await db.scalar(select(User.id).where(User.id != identity['user_id']).limit(1))
        setattr(row, field, value)
    async with Session() as db:
        row = await db.get(GoalExecution, execution['execution_id'])
        with pytest.raises(HTTPException) as error:
            await verify_admission(db, row)
        assert error.value.detail == 'goal_source_pin_changed'
    response = await client.post('/v1/goal-executions/'+execution['execution_id']+'/cancel',
        headers=identity['owner'], json={'request_key':str(uuid4())})
    assert response.status_code == 200 and response.json()['status'] == 'cancelled'


@pytest.mark.parametrize('kind', ['role','inactive'])
async def test_original_actor_authority_rechecked(client, identity, goal_gates, kind):
    goal, execution, body = await admitted(client, identity)
    async with Session.begin() as db:
        if kind == 'role':
            member = await db.get(Member, (identity['workspace'], identity['user_id']))
            member.role = 'viewer'
        else:
            user = await db.get(User, identity['user_id']); user.active = False
    async with Session() as db:
        row = await db.get(GoalExecution, execution['execution_id'])
        with pytest.raises(HTTPException) as error:
            await verify_admission(db, row)
        assert error.value.status_code == 403


@pytest.mark.parametrize('field', ['envelope','admission_hash','temporal_id','initial_proposal'])
async def test_unpersisted_corrupted_identity_fails_closed(client, identity, goal_gates, field):
    goal, execution, body = await admitted(client, identity)
    async with Session() as db:
        row = await db.get(GoalExecution, execution['execution_id'])
        if field == 'envelope':
            corrupted = deepcopy(row.envelope); corrupted['actor_id'] = str(uuid4())
        elif field == 'initial_proposal':
            corrupted = deepcopy(row.initial_proposal); corrupted['snapshot_hash'] = 'b'*64
        else: corrupted = 'b'*64
        # Simulate an invalid adapter context without writing through DB triggers.
        from sqlalchemy.orm.attributes import set_committed_value
        set_committed_value(row, field, corrupted)
        with pytest.raises(HTTPException) as error:
            await verify_admission(db, row)
        assert error.value.detail == 'goal_admission_evidence_invalid'


@pytest.mark.parametrize('field', ['content_hash','payload','actor_id'])
async def test_start_command_evidence_is_checked(client, identity, goal_gates, field):
    goal, execution, body = await admitted(client, identity)
    async with Session() as db:
        row = await db.get(GoalExecution, execution['execution_id'])
        start = await db.scalar(select(GoalCommand).where(GoalCommand.execution_id == row.id))
        from sqlalchemy.orm.attributes import set_committed_value
        value = deepcopy(start.payload) if field == 'payload' else ('b'*64 if field == 'content_hash' else str(uuid4()))
        if field == 'payload': value['policy']['max_iterations'] += 1
        set_committed_value(start, field, value)
        with pytest.raises(HTTPException) as error:
            await verify_admission(db, row)
        assert error.value.detail == 'goal_admission_evidence_invalid'


@pytest.mark.parametrize('which', ['admitted','command'])
async def test_missing_immutable_audit_is_not_replaced_by_a_valid_hash(client, identity, goal_gates, which, monkeypatch):
    goal, execution, body = await admitted(client, identity)
    async with Session() as db:
        row = await db.get(GoalExecution, execution['execution_id'])
        missing = await db.scalar(select(GoalEvent.id).where(GoalEvent.action == which))
        original_get = db.get
        async def filtered_get(model, ident, **kwargs):
            if model is GoalEvent and ident == missing: return None
            return await original_get(model, ident, **kwargs)
        monkeypatch.setattr(db, 'get', filtered_get)
        with pytest.raises(HTTPException) as error:
            await verify_admission(db, row)
        assert error.value.detail == 'goal_admission_evidence_invalid'


async def test_approval_api_rejects_changed_content_even_with_same_version(client, identity, goal_gates):
    goal, execution, body = await admitted(client, identity)
    async with Session.begin() as db:
        source = await db.get(Goal, goal['id']); source.description = 'Changed without version bump'
        row = await db.get(GoalExecution, execution['execution_id'])
        row.status = 'waiting_approval'
        row.state = {'proposal_hash':'a'*64, 'proposal':body['proposal']}
    response = await client.post('/v1/goal-executions/'+execution['execution_id']+'/decision',
        headers=identity['owner'], json={'request_key':str(uuid4()), 'version':1,
            'proposal_hash':'a'*64, 'decision':'approve'})
    assert response.status_code == 409 and response.json()['detail'] == 'goal_source_pin_changed'
    async with Session() as db:
        assert await db.scalar(select(func.count(GoalCommand.id))) == 1
        assert await db.scalar(select(func.count(GoalEvent.id))) == 2
