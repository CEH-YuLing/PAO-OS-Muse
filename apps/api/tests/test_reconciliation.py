from datetime import datetime, timezone

import pytest
from sqlalchemy import select, func

from pao.db import Session
from pao.models import AdReport
from test_business_tools import seed


def export(**changes):
    return {'account_id': 'act_1', 'period_start': '2026-10-01', 'period_end': '2026-10-05',
            'currency': 'VND', 'timezone': 'Asia/Ho_Chi_Minh', 'attribution': 'fixture',
            'exported_at': '2026-10-05T12:00:00+07:00', 'file_sha256': 'a'*64,
            'spend': '10', 'clicks': None, 'platform_reported_purchases': '2', **changes}


async def test_matches_not_business_verified_and_no_writes(client, identity):
    _, rid = await seed(identity, clicks=15)
    url = f'/v1/reports/{rid}/reconciliation-preview'
    response = await client.post(url, headers=identity['owner'], json=export(clicks=15))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['status'] == 'values_match' and result['business_verified'] is False
    assert result['provenance'] == 'user_supplied_not_authenticated'
    assert all(row['status'] == 'match' for row in result['metrics'])
    async with Session() as db:
        assert await db.scalar(select(func.count(AdReport.id))) == 1
        assert (await db.get(AdReport, rid)).spend == 10


@pytest.mark.parametrize('field,value', [('account_id', 'act_2'), ('currency', 'USD'),
    ('timezone', 'UTC'), ('attribution', 'different'), ('period_end', '2026-10-06')])
async def test_scope_mismatch_not_compared(client, identity, field, value):
    _, rid = await seed(identity)
    response = await client.post(f'/v1/reports/{rid}/reconciliation-preview',
        headers=identity['owner'], json=export(**{field: value}))
    assert response.status_code == 200
    assert response.json()['status'] == 'incomparable' and not response.json()['metrics']


@pytest.mark.parametrize('changes,status', [({'clicks': None}, 'insufficient_data'),
    ({'clicks': 0, 'spend': '0'}, 'mismatch'), ({'clicks': 0, 'spend': '10.000001'}, 'mismatch')])
async def test_unknown_zero_and_exact_decimal_difference(client, identity, changes, status):
    _, rid = await seed(identity, clicks=0)
    response = await client.post(f'/v1/reports/{rid}/reconciliation-preview',
        headers=identity['owner'], json=export(**changes))
    assert response.json()['status'] == status


@pytest.mark.parametrize('changes', [{'spend': True}, {'spend': 0.1}, {'spend': '-1'},
    {'spend': 'NaN'}, {'clicks': True}, {'timezone': 'bad/zone'}, {'period_end': '2026-11-05'},
    {'exported_at': '2026-10-05T12:00:00'}, {'workspace_id': 'escape'}])
async def test_invalid_export_rejected(client, identity, changes):
    _, rid = await seed(identity)
    response = await client.post(f'/v1/reports/{rid}/reconciliation-preview',
        headers=identity['owner'], json=export(**changes))
    assert response.status_code == 422


async def test_auth_owner_and_connection_version(client, identity):
    _, rid = await seed(identity)
    url = f'/v1/reports/{rid}/reconciliation-preview'
    assert (await client.post(url, json=export())).status_code == 401
    assert (await client.post(url, headers=identity['other'], json=export())).status_code == 404
    assert (await client.post(url, headers=identity['outsider'], json=export())).status_code == 404
    async with Session.begin() as db:
        report = await db.get(AdReport, rid)
        report.connection_version = 999
    assert (await client.post(url, headers=identity['owner'], json=export())).status_code == 404
