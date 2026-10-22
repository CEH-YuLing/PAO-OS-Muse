from pao.config import settings


async def test_platform_catalog_is_authenticated_and_never_exposes_secrets(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'openai_api_key', 'secret-openai-value')
    assert (await client.get('/v1/platform/catalog')).status_code == 401
    response = await client.get('/v1/platform/catalog', headers=identity['owner'])
    assert response.status_code == 200
    payload = response.json()
    assert {row['key'] for row in payload['features']} >= {
        'self_learning', 'collaborators', 'skills', 'chatbot', 'tasks', 'recurring_tasks'
    }
    providers = {row['key']: row for row in payload['model_providers']}
    assert providers['ollama']['default'] is True
    assert providers['openai']['configured'] is True
    assert 'secret-openai-value' not in response.text

