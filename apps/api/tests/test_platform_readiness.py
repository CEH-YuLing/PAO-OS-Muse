from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from cryptography.fernet import Fernet
from pao.config import settings
from pao.db import Session
from pao.models import ModelProviderConnection, now
from pao.modules.platform.readiness import provider_state, state


async def test_catalog_credentials_do_not_imply_health_or_missing_adapters(client, identity, monkeypatch):
    config=settings()
    for name in ('openai_api_key','zalo_oa_access_token','botcake_api_token','tiktok_ads_access_token'):
        monkeypatch.setattr(config,name,'synthetic-secret-not-a-real-key')
    response=await client.get('/v1/platform/catalog',headers=identity['owner'])
    assert response.status_code==200
    body=response.json()
    assert body['readiness_version']=='p0-evidence-v1'
    integrations={r['key']:r for r in body['integrations']}
    for key in ('zalo','botcake','tiktok_ads'):
        r=integrations[key]
        assert r['status']=='available'
        assert r['readiness']==state(False,False,accepted=False,reason='adapter_not_implemented')
    providers={r['key']:r for r in body['model_providers']}
    assert providers['openai']['configured'] is True  # Compatibility label only.
    assert providers['openai']['readiness']['configured'] is False
    for rows in (body['features'],body['integrations'],body['model_providers']):
        assert all(r['readiness']['healthy'] is None for r in rows)
        assert all(r['readiness']['accepted'] is not True for r in rows)
    shadow=body['javis_compatibility']['fast_path']['readiness']
    assert not shadow['active'] and shadow['accepted'] is False
    assert 'synthetic-secret-not-a-real-key' not in response.text


async def test_catalog_workspace_scope_is_preserved(client, identity):
    url='/v1/platform/catalog?workspace_id='+identity['workspace']
    assert (await client.get(url,headers=identity['outsider'])).status_code==404
    assert (await client.get(url,headers=identity['owner'])).status_code==200


async def test_workspace_provider_check_is_not_acceptance(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        row=ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',
            api_key_ciphertext='synthetic-cipher-never-decrypted',model='synthetic-model',
            status='connected',is_default=True,last_checked_at=now(),model_count=2)
        db.add(row)
    url='/v1/platform/catalog?workspace_id='+identity['workspace']
    data=(await client.get(url,headers=identity['owner'])).json()
    r=next(r for r in data['model_providers'] if r['key']=='openai')['readiness']
    assert r['configured'] and r['active']
    assert r['healthy'] is None and r['accepted'] is None
    async with Session.begin() as db:
        saved=await db.get(ModelProviderConnection,row.id)
        saved.status='error';saved.last_error='synthetic-private-error';saved.last_checked_at=now()
    response=await client.get(url,headers=identity['owner'])
    r=next(r for r in response.json()['model_providers'] if r['key']=='openai')['readiness']
    assert r['healthy'] is False and not r['active']
    assert r['reason']=='recent_check_failed'
    assert 'synthetic-private-error' not in response.text
    assert 'synthetic-cipher-never-decrypted' not in response.text


def test_stale_and_future_provider_checks_are_unknown():
    clock=datetime.now(timezone.utc)
    config=SimpleNamespace(integration_encryption_key=Fernet.generate_key().decode())
    for checked in (clock-timedelta(minutes=16),clock+timedelta(minutes=1),None):
        row=SimpleNamespace(api_key_ciphertext='cipher',model='model',last_checked_at=checked,
                            status='error',last_error='private',is_default=False)
        assert provider_state(config,row,clock)['healthy'] is None


def test_active_requires_implementation_and_configuration():
    assert not state(False,True,active=True)['active']
    assert not state(True,False,active=True)['active']
    assert state(True,True,active=True)['active']
