import pytest
from pydantic import ValidationError
from pao import skills

PERIOD = {'start_date': '2026-10-01', 'end_date': '2026-10-05'}


def test_skill_contract_permissions_and_output_evaluator():
    pinned = skills.snapshot('daily-business-brief')
    assert len(pinned['hash']) == 64
    assert skills.validate_input('daily-business-brief', 'chief_of_staff', PERIOD) == PERIOD
    with pytest.raises(PermissionError):
        skills.validate_input('daily-business-brief', 'editor', PERIOD)
    with pytest.raises(PermissionError):
        skills.validate_input('daily-business-brief', 'chief_of_staff', PERIOD, ['email.mock_send'])
    with pytest.raises(ValidationError):
        skills.validate_input('daily-business-brief', 'chief_of_staff', {**PERIOD, 'workspace_id': 'other'})
    with pytest.raises(ValidationError):
        skills.validate_input('daily-business-brief', 'chief_of_staff', {**PERIOD, 'end_date': '2026-09-01'})
    with pytest.raises(ValidationError):
        skills.evaluate_result(pinned, {'status': 'completed', 'summary': 'Claim', 'source_references': []})
    missing = {'status': 'insufficient_data', 'summary': 'Missing connector',
               'source_references': [], 'missing_data': ['meta_connection']}
    assert skills.evaluate_result(pinned, missing)['status'] == 'insufficient_data'
    with pytest.raises(ValueError):
        skills.evaluate_result({**pinned, 'version': '9.9.9'}, missing)


async def test_skill_catalog_and_preflight_are_scoped(client, identity):
    url = f"/v1/skills?workspace_id={identity['workspace']}"
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=identity['outsider'])).status_code == 404
    catalog = await client.get(url, headers=identity['owner'])
    assert catalog.status_code == 200 and len(catalog.json()) == 3
    body = {'workspace_id': identity['workspace'], 'agent': 'chief_of_staff', 'input': PERIOD}
    url = '/v1/skills/daily-business-brief/validate'
    valid = await client.post(url, headers=identity['owner'], json=body)
    assert valid.status_code == 200 and valid.json()['execution_available'] is False
    assert (await client.post(url, headers=identity['outsider'], json=body)).status_code == 404
    for update, expected in [({'agent': 'editor'}, 403),
                             ({'requested_tools': ['ads.write']}, 403),
                             ({'input': {**PERIOD, 'end_date': 'bad'}}, 422)]:
        assert (await client.post(url, headers=identity['owner'], json={**body, **update})).status_code == expected
    assert (await client.post('/v1/skills/unreviewed/validate', headers=identity['owner'], json=body)).status_code == 404


async def make_skill_task(client, identity, **changes):
    response = await client.post('/v1/tasks', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'title': 'Daily brief', 'status': 'ready',
        'kind': 'agent', 'assignee_type': 'agent', 'assignee_id': 'chief_of_staff',
        'skill_id': 'daily-business-brief', 'success_criteria': ['Sourced report'], **changes,
    })
    assert response.status_code == 201, response.text
    return response.json()


async def test_attempt_pins_version_and_replay_survives_registry_update(client, identity, monkeypatch):
    task = await make_skill_task(client, identity)
    url = f"/v1/tasks/{task['id']}/attempts"
    body = {'request_key': 'skill-attempt-001', 'input': PERIOD}
    first = await client.post(url, headers=identity['owner'], json=body)
    assert first.status_code == 201, first.text
    old = first.json()['skill_snapshot']
    assert old['version'] == '1.0.0' and old['input_schema'] and old['output_schema']
    monkeypatch.setitem(skills.REGISTRY, 'daily-business-brief',
                        skills.REGISTRY['daily-business-brief'].model_copy(update={'version': '1.1.0'}))
    replay = await client.post(url, headers=identity['owner'], json=body)
    assert replay.json()['id'] == first.json()['id']
    assert replay.json()['skill_snapshot'] == old
    assert (await client.post(url, headers=identity['owner'], json={
        **body, 'input': {**PERIOD, 'end_date': '2026-10-06'}})).status_code == 409
    other = await make_skill_task(client, identity)
    second = await client.post(f"/v1/tasks/{other['id']}/attempts", headers=identity['owner'], json=body)
    assert second.json()['skill_snapshot']['version'] == '1.1.0'
    assert second.json()['skill_snapshot']['hash'] != old['hash']


@pytest.mark.parametrize('changes,input_value,expected', [
    ({'skill_id': 'unreviewed'}, PERIOD, 422),
    ({'assignee_id': 'editor'}, PERIOD, 403),
    ({}, {}, 422),
])
async def test_invalid_skill_attempt_does_not_change_task(client, identity, changes, input_value, expected):
    task = await make_skill_task(client, identity, **changes)
    response = await client.post(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'],
                                 json={'request_key': 'invalid-attempt-01', 'input': input_value})
    assert response.status_code == expected
    current = (await client.get(f"/v1/tasks/{task['id']}", headers=identity['owner'])).json()
    assert current['status'] == 'ready'
    attempts = await client.get(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'])
    assert attempts.json() == []


async def test_skill_completion_rejects_claims_without_sources_and_missing_data(client, identity):
    task = await make_skill_task(client, identity)
    start = await client.post(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'],
                              json={'request_key': 'evaluate-attempt-01', 'input': PERIOD})
    attempt = start.json()
    url = f"/v1/tasks/{task['id']}/attempts/{attempt['id']}"
    base = {'version': 1, 'status': 'completed', 'evidence': [{'type': 'report', 'reference': 'report:fixture'}]}
    bad = await client.patch(url, headers=identity['owner'], json={**base,
        'result': {'status': 'completed', 'summary': 'Claim', 'source_references': []}})
    assert bad.status_code == 422
    missing = await client.patch(url, headers=identity['owner'], json={**base,
        'result': {'status': 'insufficient_data', 'summary': 'Missing account',
                   'source_references': [], 'missing_data': ['meta_account']}})
    assert missing.status_code == 409
    valid = await client.patch(url, headers=identity['owner'], json={**base,
        'result': {'status': 'completed', 'summary': 'Sourced report', 'source_references': ['report:fixture']}})
    assert valid.status_code == 200 and valid.json()['skill_snapshot'] == attempt['skill_snapshot']
    current = (await client.get(f"/v1/tasks/{task['id']}", headers=identity['owner'])).json()
    assert current['status'] == 'waiting_approval'
