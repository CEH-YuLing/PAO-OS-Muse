from cryptography.fernet import Fernet
from sqlalchemy import select

from pao.config import settings
from pao.db import Session
from pao.models import ModelProviderConnection
from pao.gateway import OpenAICompatibleGateway
from pao.model_router import encrypt_key,gateway_for_workspace


async def test_provider_connection_is_encrypted_and_workspace_admin_controlled(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    monkeypatch.setattr('pao.model_api.fetch_models',lambda provider,key: _models(provider,key))
    body={'workspace_id':identity['workspace'],'api_key':'sk-super-secret-value'}
    denied=await client.post('/v1/model-providers/openai/connect',json=body,headers=identity['other'])
    assert denied.status_code==403
    response=await client.post('/v1/model-providers/openai/connect',json=body,headers=identity['owner'])
    assert response.status_code==200 and response.json()['is_default'] is True
    assert 'sk-super-secret-value' not in response.text and response.json()['key_hint']=='••••alue'
    async with Session() as db:
        row=await db.scalar(select(ModelProviderConnection))
        assert row.api_key_ciphertext!='sk-super-secret-value' and row.model=='gpt-4.1-mini'


async def _models(provider,key):
    assert key=='sk-super-secret-value'
    return ['gpt-4.1-mini','gpt-test']


async def test_provider_list_never_returns_key(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    response=await client.get('/v1/model-providers',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert response.status_code==200 and len(response.json())==4
    assert 'api_key' not in response.text and {x['provider'] for x in response.json()}=={'openai','anthropic','gemini','openrouter'}


async def test_workspace_default_cannot_resolve_unaccounted_cloud_gateway(client,identity,monkeypatch):
    from unittest.mock import Mock
    import pytest
    from pao import model_router
    from pao.modules.engines.contract import EngineFailure
    factory=Mock(wraps=model_router.cloud_gateway)
    monkeypatch.setattr(model_router,'cloud_gateway',factory)
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        db.add(ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',
            api_key_ciphertext=encrypt_key('sk-router-secret'),model='gpt-test',is_default=True))
    async with Session() as db:
        with pytest.raises(EngineFailure,match='^tenant_resource_accounting_required$'):
            await gateway_for_workspace(db,identity['workspace'])
    factory.assert_not_called()
