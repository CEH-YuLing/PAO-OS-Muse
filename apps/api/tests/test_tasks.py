from sqlalchemy import func, select

from pao.db import Session
from pao.models import Goal, Member, TaskActivity, TaskAttempt, TaskComment, TaskDependency


async def make_project(client, identity):
    response = await client.post('/v1/projects', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'name': 'Ra mắt Q4',
        'description': 'Kế hoạch phối hợp marketing và sales',
    })
    assert response.status_code == 201, response.text
    return response.json()


async def make_task(client, identity, project_id, **overrides):
    body = {'workspace_id': identity['workspace'], 'project_id': project_id,
            'title': 'Chuẩn bị creative', 'priority': 'high'}
    body.update(overrides)
    response = await client.post('/v1/tasks', headers=identity['owner'], json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_workspace_scope_permissions_and_filters(client, identity):
    project = await make_project(client, identity)
    task = await make_task(client, identity, project['id'])
    listed = await client.get('/v1/tasks', headers=identity['other'], params={
        'workspace_id': identity['workspace'], 'project_id': project['id'], 'status': 'draft'})
    assert listed.status_code == 200 and [row['id'] for row in listed.json()] == [task['id']]
    assert (await client.get('/v1/tasks', headers=identity['outsider'], params={
        'workspace_id': identity['workspace']})).status_code == 404

    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        member.role = 'viewer'
    denied = await client.post('/v1/tasks', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'title': 'Không được tạo'})
    assert denied.status_code == 403


async def test_versioned_update_completion_comment_and_activity(client, identity):
    project = await make_project(client, identity)
    task = await make_task(client, identity, project['id'], status='ready',
                           success_criteria=['Creative được duyệt'])
    updated = await client.patch(f"/v1/tasks/{task['id']}", headers=identity['other'], json={
        'version': 1, 'status': 'completed', 'description': 'Đã duyệt creative',
        'evidence': [{'type': 'review', 'reference': 'review-1'}]})
    assert updated.status_code == 200, updated.text
    assert updated.json()['version'] == 2 and updated.json()['progress'] == 100
    assert updated.json()['completed_at'] is not None
    stale = await client.patch(f"/v1/tasks/{task['id']}", headers=identity['owner'], json={
        'version': 1, 'priority': 'critical'})
    assert stale.status_code == 409

    comment = await client.post(f"/v1/tasks/{task['id']}/comments", headers=identity['owner'],
                                json={'body': 'Kết quả đạt yêu cầu.'})
    assert comment.status_code == 201
    comments = await client.get(f"/v1/tasks/{task['id']}/comments", headers=identity['owner'])
    activity = await client.get(f"/v1/tasks/{task['id']}/activity", headers=identity['owner'])
    assert [row['body'] for row in comments.json()] == ['Kết quả đạt yêu cầu.']
    assert {row['event'] for row in activity.json()} == {'task.created', 'task.updated', 'comment.created'}
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TaskComment)) == 1
        assert await db.scalar(select(func.count()).select_from(TaskActivity)) == 3


async def test_dependency_validation_and_cycle_protection(client, identity):
    project = await make_project(client, identity)
    first = await make_task(client, identity, project['id'], title='Nghiên cứu')
    second = await make_task(client, identity, project['id'], title='Viết nội dung', dependencies=[first['id']])
    self_reference = await client.patch(f"/v1/tasks/{first['id']}", headers=identity['owner'], json={
        'version': first['version'], 'dependencies': [first['id']]})
    assert self_reference.status_code == 422
    cycle = await client.patch(f"/v1/tasks/{first['id']}", headers=identity['owner'], json={
        'version': first['version'], 'dependencies': [second['id']]})
    assert cycle.status_code == 422
    invalid_project = await client.post('/v1/tasks', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'project_id': '00000000-0000-0000-0000-000000000001',
        'title': 'Sai project'})
    assert invalid_project.status_code == 422


async def complete_attempt(client, identity, task, key):
    started = await client.post(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'], json={
        'request_key': key, 'input': {'task': task['title']}})
    assert started.status_code == 201, started.text
    attempt = started.json()
    finished = await client.patch(f"/v1/tasks/{task['id']}/attempts/{attempt['id']}",
                                  headers=identity['owner'], json={
        'version': 1, 'status': 'completed', 'result': {'summary': f"Đã làm {task['title']}"},
        'evidence': [{'type': 'artifact', 'reference': f"artifact:{attempt['id']}"}],
    })
    assert finished.status_code == 200, finished.text
    current = (await client.get(f"/v1/tasks/{task['id']}", headers=identity['owner'])).json()
    assert current['status'] == 'waiting_approval' and current['evidence']
    approved = await client.patch(f"/v1/tasks/{task['id']}", headers=identity['owner'], json={
        'version': current['version'], 'status': 'completed'})
    assert approved.status_code == 200, approved.text
    return approved.json()


async def test_goal_three_dependent_tasks_attempts_and_evidence_completion(client, identity):
    project = await make_project(client, identity)
    made_goal = await client.post('/v1/goals', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'project_id': project['id'],
        'title': 'Ra mắt chiến dịch', 'success_criteria': ['Ba đầu việc bắt buộc hoàn tất có evidence'],
    })
    assert made_goal.status_code == 201, made_goal.text
    goal = made_goal.json()
    activated = await client.patch(f"/v1/goals/{goal['id']}", headers=identity['owner'], json={
        'version': goal['version'], 'status': 'active'})
    assert activated.status_code == 200
    goal = activated.json()

    first = await make_task(client, identity, project['id'], goal_id=goal['id'], title='Nghiên cứu',
                            status='ready', success_criteria=['Có báo cáo nguồn'])
    second = await make_task(client, identity, project['id'], goal_id=goal['id'], title='Lập kế hoạch',
                             status='ready', success_criteria=['Có kế hoạch'], dependencies=[first['id']])
    third = await make_task(client, identity, project['id'], goal_id=goal['id'], title='Duyệt kế hoạch',
                            status='ready', success_criteria=['Có biên bản duyệt'], dependencies=[second['id']])

    blocked = await client.post(f"/v1/tasks/{second['id']}/attempts", headers=identity['owner'], json={
        'request_key': 'second-before-first', 'input': {}})
    assert blocked.status_code == 409
    premature = await client.patch(f"/v1/goals/{goal['id']}", headers=identity['owner'], json={
        'version': goal['version'], 'status': 'completed'})
    assert premature.status_code == 409

    first = await complete_attempt(client, identity, first, 'attempt-first-01')
    second = await complete_attempt(client, identity, second, 'attempt-second-01')
    third = await complete_attempt(client, identity, third, 'attempt-third-01')
    completed = await client.patch(f"/v1/goals/{goal['id']}", headers=identity['owner'], json={
        'version': goal['version'], 'status': 'completed'})
    assert completed.status_code == 200 and completed.json()['completed_at'] is not None
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Goal)) == 1
        assert await db.scalar(select(func.count()).select_from(TaskDependency)) == 2
        assert await db.scalar(select(func.count()).select_from(TaskAttempt)) == 3


async def test_attempt_idempotency_cancel_and_child_guard(client, identity):
    project = await make_project(client, identity)
    parent = await make_task(client, identity, project['id'], title='Parent', status='ready',
                             success_criteria=['Có kết quả'])
    child = await make_task(client, identity, project['id'], title='Child', status='ready',
                            success_criteria=['Có kết quả'], dependencies=[parent['id']])
    body = {'request_key': 'parent-attempt-01', 'input': {'scope': 'safe'}}
    first = await client.post(f"/v1/tasks/{parent['id']}/attempts", headers=identity['owner'], json=body)
    replay = await client.post(f"/v1/tasks/{parent['id']}/attempts", headers=identity['owner'], json=body)
    assert first.status_code == replay.status_code == 201
    assert first.json()['id'] == replay.json()['id']
    conflict = await client.post(f"/v1/tasks/{parent['id']}/attempts", headers=identity['owner'], json={
        **body, 'input': {'scope': 'different'}})
    assert conflict.status_code == 409
    current = (await client.get(f"/v1/tasks/{parent['id']}", headers=identity['owner'])).json()
    cancelled = await client.patch(f"/v1/tasks/{parent['id']}", headers=identity['owner'], json={
        'version': current['version'], 'status': 'cancelled'})
    assert cancelled.status_code == 200
    child_start = await client.post(f"/v1/tasks/{child['id']}/attempts", headers=identity['owner'], json={
        'request_key': 'child-attempt-01', 'input': {}})
    assert child_start.status_code == 409
    attempts = await client.get(f"/v1/tasks/{parent['id']}/attempts", headers=identity['owner'])
    assert attempts.json()[0]['status'] == 'cancelled'

    parent_only = await make_task(client, identity, project['id'], title='Parent tree', status='ready',
                                  success_criteria=['Có kết quả'])
    child_only = await make_task(client, identity, project['id'], title='Child tree', status='ready',
                                 parent_task_id=parent_only['id'], success_criteria=['Có kết quả'])
    blocked_by_parent = await client.post(f"/v1/tasks/{child_only['id']}/attempts",
                                          headers=identity['owner'], json={
        'request_key': 'child-parent-guard', 'input': {}})
    assert blocked_by_parent.status_code == 409


async def test_agent_cannot_bypass_attempt_state_machine(client, identity):
    project = await make_project(client, identity)
    task = await make_task(client, identity, project['id'], title='Agent work', status='ready',
                           kind='agent', source='pao', assignee_type='agent',
                           assignee_id='researcher', success_criteria=['Có evidence'])
    bypass = await client.patch(f"/v1/tasks/{task['id']}", headers=identity['owner'], json={
        'version': task['version'], 'status': 'running'})
    assert bypass.status_code == 409
    complete = await client.patch(f"/v1/tasks/{task['id']}", headers=identity['owner'], json={
        'version': task['version'], 'status': 'completed',
        'evidence': [{'type': 'manual', 'reference': 'not-an-attempt'}]})
    assert complete.status_code == 409
