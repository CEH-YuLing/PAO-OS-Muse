from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as Obj
from uuid import uuid4
import pytest
from pao.modules.business.outcomes import aggregate,compare

STAMP=datetime(2026,10,1,tzinfo=timezone.utc)


def action(**kw):
    return Obj(id='test-action',executed_at=STAMP,dry_run=False,execution_status='succeeded',**kw)


def metrics():
    result=[]
    for offset in range(-168,168):
        stamp=STAMP+timedelta(hours=offset)
        result.append(Obj(id=str(offset),day=stamp.date(),hour=stamp.hour,timezone='UTC',
            currency='USD',attribution='7d_click',spend=10,clicks=20,
            purchase=1 if offset<0 else 2,revenue=100 if offset<0 else 200))
    return result


def test_all_windows_observed_not_causal():
    result=compare(action(),metrics(),[],STAMP+timedelta(days=8),execution_verified=True)
    assert all(r['status']=='observed' and r['causal_effect_proven'] is False for r in result.values())
    assert result['24h']['delta']['purchase']=='24'


@pytest.mark.parametrize('kind',['missing','currency','attribution','duplicate','null'])
def test_invalid_evidence_is_insufficient(kind):
    rows=metrics()
    if kind=='missing':rows=[r for r in rows if r.id!='0']
    elif kind=='duplicate':rows.append(rows[168])
    elif kind=='null':rows[168].revenue=None
    elif kind=='currency':rows[168].currency='VND'
    else:rows[168].attribution='1d_click'
    result=compare(action(),rows,[],STAMP+timedelta(days=8),execution_verified=True)
    assert result['24h']['status']=='insufficient'


def test_pending_and_unverified():
    assert compare(action(),[],[],STAMP,execution_verified=True)['24h']['status']=='pending'
    assert compare(action(),metrics(),[],STAMP+timedelta(days=8),execution_verified=False)['24h']['status']=='insufficient'


def test_simulation_cannot_claim_real_outcome():
    a=action();a.dry_run=True
    assert compare(a,metrics(),[],STAMP+timedelta(days=8),execution_verified=True)['24h']['reason']=='real_execution_not_verified'


def test_partial_hour_and_confounders():
    a=action();a.executed_at+=timedelta(minutes=1)
    assert compare(a,metrics(),[],STAMP+timedelta(days=8),execution_verified=True)['24h']['reason']=='hourly_resolution_insufficient'
    other=action();other.id='other';other.executed_at+=timedelta(hours=1)
    result=compare(action(),metrics(),[other],STAMP+timedelta(days=8),execution_verified=True)['24h']
    assert result['status']=='observed' and result['confounders']==[{'kind':'other_resource_action','action_id':'other'}]
    assert result['causal_effect_proven'] is False


def test_dst_ambiguous_hour_is_insufficient():
    r=Obj(id='fold',day=datetime(2026,11,1).date(),hour=1,timezone='America/New_York',
        currency='USD',attribution='7d_click',spend=1,clicks=1,purchase=1,revenue=1)
    start=datetime(2026,11,1,5,tzinfo=timezone.utc)
    result=aggregate([r],start,start+timedelta(hours=1))
    assert result['complete'] is False and result['ambiguous_dst'] is True


async def test_missing_action_route_and_auth(client,identity):
    url='/v1/ads/actions/'+str(uuid4())+'/outcomes'
    assert (await client.get(url)).status_code==401
    assert (await client.get(url,headers=identity['owner'])).status_code==404
