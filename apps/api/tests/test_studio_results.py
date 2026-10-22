"""P6.2C first checkpoint: schema/exit receipts, no live executor."""
from copy import deepcopy
import pytest
from sqlalchemy import select

from pao.db import Session
from pao.models import StudioEvent
from pao.modules.studio.contracts import digest
from pao.modules.studio.results import fixture_echo, verify_result
from test_studio import SCHEMA, make, publish, studio


def contract(criteria=None):
    return {'input_schema': deepcopy(SCHEMA), 'output_schema': deepcopy(SCHEMA),
            'exit_criteria': criteria or []}


def test_receipt_hashes_are_stable_and_do_not_claim_model_execution():
    payload = contract(['non_empty:text', 'equals_input:text'])
    value = {'text': 'Only a fixture'}
    receipt = verify_result(payload, value, value)
    assert receipt == verify_result(deepcopy(payload), deepcopy(value), deepcopy(value))
    assert receipt['input_hash'] == receipt['output_hash'] == digest(value)
    assert receipt['contract_hash'] == digest(payload)
    assert receipt['receipt_hash'] == digest({k: v for k, v in receipt.items() if k != 'receipt_hash'})
    assert not receipt['model_executed'] and not receipt['model_weights_verified']
    assert 'Only a fixture' not in str(receipt)
    assert receipt['checks'] == payload['exit_criteria']


@pytest.mark.parametrize('input_value,output', [
    ({}, {'text': 'ok'}), ({'text': True}, {'text': 'ok'}),
    ({'text': 'ok'}, {}), ({'text': 'ok'}, {'text': 1}),
    ({'text': 'ok'}, {'text': 'ok', 'extra': 'no'}),
    ({'text': 'ok'}, {'text': 'x' * 81}),
])
def test_bad_schema_values_rejected(input_value, output):
    with pytest.raises(ValueError):
        verify_result(contract(), input_value, output)


@pytest.mark.parametrize('criteria,output', [
    (['non_empty:text'], ''), (['non_empty:text'], ' \t\n'),
    (['equals_input:text'], 'changed'), (['unknown:text'], 'ok'),
    (['non_empty:missing'], 'ok'), ([False], 'ok'),
])
def test_failed_or_unknown_exit_rules_are_not_receipts(criteria, output):
    with pytest.raises(ValueError):
        verify_result(contract(criteria), {'text': 'ok'}, {'text': output})


def test_echo_is_isolated_and_cannot_invent_required_output():
    original = {'text': 'Synthetic'}
    result = fixture_echo(contract(['equals_input:text']), original)
    result['output']['text'] = 'mutated'
    assert original == {'text': 'Synthetic'}
    assert result['origin'] == 'fixture_echo' and result['dry_run']
    incompatible = contract()
    incompatible['output_schema']['properties'] = {'answer': {'type': 'string', 'maxLength': 80}}
    incompatible['output_schema']['required'] = ['answer']
    with pytest.raises(ValueError):
        fixture_echo(incompatible, original)


def test_receipt_changes_when_contract_or_output_changes():
    first = verify_result(contract(), {'text': 'in'}, {'text': 'out'})
    assert first['receipt_hash'] != verify_result(contract(), {'text': 'in'}, {'text': 'other'})['receipt_hash']
    assert first['receipt_hash'] != verify_result(contract(['non_empty:text']), {'text': 'in'}, {'text': 'out'})['receipt_hash']


async def test_fixture_api_enforces_criteria_and_audits_only_hashes(client, identity, studio):
    agent = await publish(client, identity, await make(client, identity))
    payload = {'instruction': 'Return input text unchanged as JSON.',
               'agent_version_id': agent['version']['id'], **contract(['equals_input:text', 'non_empty:text'])}
    skill = await make(client, identity, 'skills', 'verified-echo', payload)
    url = f"/v1/studio/definitions/{skill['definition']['id']}/versions/{skill['version']['id']}/fixture"
    for expected in ('Changed fixture', '   '):
        response = await client.post(url, headers=identity['owner'],
            json={'input': {'text': 'Local fixture'}, 'expected_output': {'text': expected}})
        assert response.status_code == 422 and response.json()['detail'] == 'studio_fixture_invalid'
    async with Session() as db:
        assert not list(await db.scalars(select(StudioEvent).where(
            StudioEvent.version_id == skill['version']['id'], StudioEvent.action == 'fixture_passed')))
    response = await client.post(url, headers=identity['owner'],
        json={'input': {'text': 'Local fixture'}, 'expected_output': {'text': 'Local fixture'}})
    assert response.status_code == 200 and not response.json()['model_executed']
    async with Session() as db:
        event = await db.scalar(select(StudioEvent).where(
            StudioEvent.version_id == skill['version']['id'], StudioEvent.action == 'fixture_passed'))
        assert event.data['receipt']['contract_hash'] == skill['version']['hash']
        assert event.data['receipt']['checks'] == ['equals_input:text', 'non_empty:text']
        assert 'Local fixture' not in str(event.data)
