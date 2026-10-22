"""P0.3B.1 characterization only: retain current Task behavior before extraction."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import HTTPException
from pao import task_api as api


def test_attempt_fingerprint_canonical_unicode_and_run_identity():
    run = UUID('00000000-0000-0000-0000-000000000001')
    first = {'b': ['Tiếng Việt', 2], 'a': {'z': 1}}
    reordered = {'a': {'z': 1}, 'b': ['Tiếng Việt', 2]}
    raw = json.dumps({'input': first, 'run_id': str(run)}, sort_keys=True,
                     ensure_ascii=False, separators=(',', ':'))
    expected = hashlib.sha256(raw.encode()).hexdigest()
    assert api.attempt_fingerprint(first, run) == expected
    assert api.attempt_fingerprint(reordered, str(run)) == expected
    assert api.attempt_fingerprint(first, None) != expected
    assert api.attempt_fingerprint({'b': [2, 'Tiếng Việt'], 'a': {'z': 1}}, run) != expected


def test_bounded_json_uses_serialized_character_length_and_keeps_identity():
    value = {'text': 'ấ😀'}
    size = len(json.dumps(value, ensure_ascii=False))
    assert api.bounded_json(value, size) is value
    assert api.bounded_json(value) is value
    with pytest.raises(ValueError, match='Dữ liệu có cấu trúc quá lớn'):
        api.bounded_json(value, size - 1)


def test_criteria_strip_drop_blank_and_preserve_none():
    assert api.clean_criteria(None) is None
    assert api.clean_criteria(['  done  ', ' ', '\t', 'x' * 500]) == ['done', 'x' * 500]
    assert api.clean_criteria([' ']) == []
    with pytest.raises(ValueError, match='Mỗi tiêu chí tối đa 500 ký tự'):
        api.clean_criteria(['x' * 501])


def test_current_task_and_goal_transition_matrices():
    assert api.TASK_TRANSITIONS == {
        'draft': {'ready', 'cancelled'},
        'ready': {'running', 'blocked', 'completed', 'cancelled'},
        'running': {'waiting_approval', 'blocked', 'failed', 'cancelled'},
        'waiting_approval': {'completed', 'running', 'failed', 'cancelled'},
        'blocked': {'ready', 'failed', 'cancelled'},
        'failed': {'ready', 'running', 'cancelled'},
        'cancelled': {'ready', 'running'}, 'completed': set(),
    }
    assert api.GOAL_TRANSITIONS == {
        'draft': {'active', 'cancelled'},
        'active': {'completed', 'failed', 'cancelled'},
        'failed': {'active', 'cancelled'}, 'cancelled': {'active'}, 'completed': set(),
    }


async def test_dependency_empty_self_and_missing_workspace_guards():
    db = SimpleNamespace(scalars=AsyncMock(return_value=[]))
    assert await api.validate_dependencies(db, None, 'workspace') == []
    db.scalars.assert_not_awaited()
    with pytest.raises(HTTPException) as exc:
        await api.validate_dependencies(db, ['self'], 'workspace', 'self')
    assert exc.value.status_code == 422 and 'chính nó' in exc.value.detail
    db.scalars.assert_not_awaited()
    with pytest.raises(HTTPException) as exc:
        await api.validate_dependencies(db, ['missing'], 'workspace')
    assert exc.value.status_code == 422 and 'workspace' in exc.value.detail
    assert 'workspace' in db.scalars.await_args.args[0].compile().params.values()


async def test_dependency_transitive_cycle_and_valid_chain():
    db = SimpleNamespace(scalar=AsyncMock(return_value=False), scalars=AsyncMock(side_effect=[
        [SimpleNamespace(id='b')], ['c'], ['a']]))
    with pytest.raises(HTTPException) as exc:
        await api.validate_dependencies(db, ['b'], 'workspace', 'a')
    assert exc.value.status_code == 422 and 'vòng lặp' in exc.value.detail
    db.scalars = AsyncMock(side_effect=[[SimpleNamespace(id='b')], ['c'], []])
    assert await api.validate_dependencies(db, ['b'], 'workspace', 'a') == ['b']


async def test_parent_none_self_missing_and_transitive_cycle():
    db = SimpleNamespace(scalar=AsyncMock(return_value=None), get=AsyncMock())
    assert await api.validate_parent(db, None, 'workspace') is None
    db.scalar.assert_not_awaited()
    with pytest.raises(HTTPException) as exc:
        await api.validate_parent(db, 'a', 'workspace', 'a')
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await api.validate_parent(db, 'missing', 'workspace', 'a')
    assert exc.value.status_code == 422 and 'workspace' in exc.value.detail
    db.scalar = AsyncMock(side_effect=[SimpleNamespace(id='b', parent_task_id='a'), False])
    with pytest.raises(HTTPException) as exc:
        await api.validate_parent(db, 'b', 'workspace', 'a')
    assert exc.value.status_code == 422 and 'vòng lặp' in exc.value.detail
    db.get.assert_not_awaited()


async def test_execution_dependency_and_parent_completion_guards():
    task = SimpleNamespace(id='task', workspace_id='workspace', parent_task_id='parent')
    db = SimpleNamespace(scalars=AsyncMock(return_value=[SimpleNamespace(id='dep', status='ready')]),
                         get=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await api.ensure_dependencies_completed(db, task)
    assert exc.value.status_code == 409
    assert exc.value.detail == {'code': 'dependencies_incomplete', 'task_ids': ['dep']}
    db.get.assert_not_awaited()
    db.scalars = AsyncMock(return_value=[SimpleNamespace(id='dep', status='completed')])
    db.get = AsyncMock(return_value=SimpleNamespace(workspace_id='other', status='completed'))
    with pytest.raises(HTTPException) as exc:
        await api.ensure_dependencies_completed(db, task)
    assert exc.value.detail == {'code': 'parent_incomplete', 'task_id': 'parent'}
    db.get = AsyncMock(return_value=SimpleNamespace(workspace_id='workspace', status='completed'))
    assert await api.ensure_dependencies_completed(db, task) is None


async def test_characterize_completed_creation_progress_not_normalized(client, identity):
    # Observed inconsistency, not desired behavior: remove/update this expectation
    # in a separately authorized fix. Characterization must not silently repair it.
    response = await client.post('/v1/tasks', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'title': 'Completed baseline',
        'status': 'completed', 'progress': 27, 'success_criteria': ['Reviewed'],
        'evidence': [{'type': 'review', 'reference': 'synthetic'}],
    })
    assert response.status_code == 201, response.text
    row = response.json()
    assert row['status'] == 'completed' and row['completed_at'] is not None
    assert row['progress'] == 27
