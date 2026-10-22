"""Model purpose and compatibility inventory; synthetic metadata, no provider I/O."""
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ChatSession, ModelProviderConnection, User
from pao.model_router import encrypt_key, fetch_model_catalog
from pao.modules.installation_ai import service
from pao.modules.installation_ai.catalog import normalize
from pao.modules.installation_ai.modalities import metadata, require_chat
from pao.modules.installation_ai.models import InstallationAIResource
from pao.modules.engines.contract import EngineFailure


@pytest.mark.parametrize('provider,name,kind',[
    ('openai','text-embedding-3-small','embedding'),('openai','gpt-image-2.5-flare','image'),
    ('openai','chatgpt-image-latest','image'),('openai','dall-e-3','image'),
    ('openai','sora-2','video'),('openai','whisper-1','audio'),('openai','tts-1','audio'),
    ('openai','gpt-realtime-2','audio'),('openai','gpt-4o-transcribe','audio'),
    ('openai','omni-moderation-latest','moderation'),('gemini','gemini-3.8-flash-tts','audio'),
    ('gemini','gemini-3.1-flash-lite-image','image'),('gemini','gemini-3.8-live','audio'),
    ('openrouter','vendor/text-embedding-v3','embedding'),
])
def test_non_chat_endpoint_is_not_advertised_as_chat(provider,name,kind):
    value=metadata(provider,name)
    assert value['output_modalities']==[kind] and value['chat_supported'] is False
    assert value['adapter']['image_generation'] is False
    with pytest.raises(ValueError,match='ai_model_not_chat_compatible'):require_chat(provider,name)


@pytest.mark.parametrize('name',['davinci-002','babbage-002','gpt-3.5-turbo-instruct'])
def test_legacy_completions_are_not_chat(name):
    assert metadata('openai',name)['chat_supported'] is False


@pytest.mark.parametrize('provider,name',[
    ('openai','gpt-6.1-sol'),('anthropic','claude-sonnet-4-6'),
    ('gemini','gemini-3.8-flash'),('codex_cli','native-provider-model'),
])
def test_text_model_is_not_image_capability_or_entitlement(provider,name):
    value=metadata(provider,name)
    assert value['chat_supported'] is True and value['availability']=='catalog_only'
    assert value['adapter']['input_modalities']==['text'] and not value['adapter']['native_tools']


def test_unknown_is_not_falsely_certified_and_provider_data_wins():
    assert metadata('openrouter','new-model')['chat_supported'] is None
    assert metadata('openrouter','gpt-image-name',{'provider_output_modalities':['text']})['chat_supported'] is True
    assert metadata('openrouter','model',{'provider_output_modalities':['embeddings']})['chat_supported'] is False


@pytest.mark.parametrize('values',[[],['unknown'],['text','text'],'text',[{}]])
def test_untrusted_modality_schema_fails(values):
    with pytest.raises(ValueError):normalize([{'model':'model','provider_output_modalities':values}])


def test_old_normalization_is_byte_shape_compatible_and_never_rewrites_input():
    row={'model':'old-model','reasoning_efforts':['high']}
    old=normalize([row])[0]
    assert set(old)=={'model','display_name','reasoning_efforts','default_effort','availability'}
    assert row=={'model':'old-model','reasoning_efforts':['high']}


@pytest.mark.parametrize('value',[None,[],42,{'connection_authority':[]},{'connection_authority':{'mode':'not-real'}}])
def test_compatibility_inventory_handles_legacy_shape_without_inventing_authority(value):
    from pao.modules.installation_ai.compatibility import mode
    assert mode(value)=='legacy_or_local'


async def test_openrouter_preserves_native_modalities_without_inference():
    requests=[]
    def handle(request):
        requests.append(request)
        assert request.method=='GET'
        return httpx.Response(200,json={'data':[{'id':'vendor/model','architecture':{'output_modalities':['image','text']}}]})
    rows=await fetch_model_catalog('openrouter','SYNTHETIC-KEY',httpx.MockTransport(handle))
    assert len(requests)==1 and rows[0]['provider_output_modalities']==['image','text']


@pytest.fixture
async def registry(identity,monkeypatch):
    monkeypatch.setattr(settings(),'installation_ai_enabled',True)
    monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
    async with Session.begin() as db:
        source=ModelProviderConnection(workspace_id=identity['workspace'],provider='openrouter',model='fixture-text',
            api_key_ciphertext=encrypt_key('SYNTHETIC-CAPABILITY-KEY'),status='connected',is_default=False)
        db.add(source);await db.flush()
        await service.capture(db,identity['user_id'],identity['workspace'],source.id,'api',[
            'fixture-text',{'model':'vendor/image-only','provider_output_modalities':['image']}])
        row=await db.scalar(select(InstallationAIResource));row.enabled=True
        return row.id


async def test_backend_blocks_non_chat_and_disable_still_works(client,identity,registry):
    async with Session.begin() as db:
        with pytest.raises(EngineFailure,match='ai_model_not_chat_compatible'):
            await service.config(db,identity['workspace'],identity['user_id'],None,registry,'vendor/image-only')
    response=await client.put('/v1/installation-ai/'+registry,headers=identity['owner'],json={
        'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'default_model':'vendor/image-only'})
    assert response.status_code==422
    response=await client.put('/v1/installation-ai/'+registry,headers=identity['owner'],json={
        'request_key':str(uuid4()),'expected_revision':1,'enabled':False,'default_model':'vendor/image-only'})
    assert response.status_code==200


async def test_preview_is_caller_scoped_no_mutation_no_private_ids(client,identity,registry):
    async with Session.begin() as db:
        own=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False)
        other_uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        other=ChatSession(workspace_id=identity['workspace'],user_id=other_uid,memory_enabled=False)
        db.add_all([own,other]);await db.flush()
        private_id=other.id
    before=None
    for _ in range(2):
        response=await client.get('/v1/installation-ai',params={'workspace_id':identity['workspace']},headers=identity['owner'])
        assert response.status_code==200
        value=response.json();preview=value['compatibility_preview']
        assert preview['read_only'] and sum(preview['sessions_by_authority'].values())==1
        assert not preview['automatic_migration'] and not preview['credentials_copied'] and not preview['history_repin']
        assert private_id not in response.text and 'SYNTHETIC-CAPABILITY-KEY' not in response.text
        assert value['resources'][0]['revision']==1
        assert before is None or preview==before
        before=preview
    member=await client.get('/v1/installation-ai',params={'workspace_id':identity['workspace']},headers=identity['other'])
    assert member.json()['compatibility_preview'] is None
    assert (await client.get('/v1/installation-ai',params={'workspace_id':identity['workspace']},headers=identity['outsider'])).status_code==404
