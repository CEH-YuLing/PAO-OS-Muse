from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4
import pytest
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from pao.config import settings
from pao.db import Session
from pao.models import Member, MetaConnection, MetaOAuthState, MetaSyncJob, Workspace, now
from pao.integrations.meta import app_config

BASE='/v1/integrations/meta/app-config'
MARKER='synthetic-meta-app-secret-ONLY'


@pytest.fixture
def config_file(tmp_path,monkeypatch):
    # Explicit private installer compatibility; production/SaaS defaults off.
    monkeypatch.setattr(settings(),'meta_installation_config_enabled',True)
    path=tmp_path/'.env';key=Fernet.generate_key().decode()
    path.write_text('OTHER_SETTING=preserved\nMETA_APP_ID=123\nMETA_APP_SECRET='+MARKER+'\n'
                    'META_GRAPH_API_VERSION=v26.0\nMETA_REDIRECT_URI=http://127.0.0.1:3200/v1/integrations/meta/callback\n'
                    'INTEGRATION_ENCRYPTION_KEY='+key+'\n')
    monkeypatch.setattr(app_config,'ENV_PATH',path)
    for name in ('META_ENABLED','META_APP_ID','META_APP_SECRET','META_GRAPH_API_VERSION','META_REDIRECT_URI',
                 'INTEGRATION_ENCRYPTION_KEY',*app_config.SAFE_FLAGS):monkeypatch.delenv(name,raising=False)
    for field in ('meta_write_enabled','meta_autopilot_enabled','ads_autopilot_global_enabled'):
        monkeypatch.setattr(settings(),field,False)
    return path,key


async def body(client,identity):
    response=await client.get(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert response.status_code==200
    value=response.json()
    assert MARKER not in response.text and 'app_secret' not in value
    return {'app_id':'123','api_version':'v26.0','redirect_uri':value['redirect_uri'],'revision':value['revision']}


@pytest.mark.parametrize('actor,expected',[('owner',200),('other',403),('outsider',404)])
async def test_settings_read_permissions(client,identity,config_file,actor,expected):
    response=await client.get(BASE,params={'workspace_id':identity['workspace']},headers=identity[actor])
    assert response.status_code==expected and MARKER not in response.text
    if expected==200:assert response.headers['cache-control']=='no-store' and response.json()['secret_present']


async def test_save_preserves_secret_key_unrelated_and_stale_rejected(client,identity,config_file):
    path,key=config_file;payload=await body(client,identity)
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==200 and MARKER not in response.text
    values=dotenv_values(path)
    assert values['META_APP_SECRET']==MARKER and values['INTEGRATION_ENCRYPTION_KEY']==key
    assert values['OTHER_SETTING']=='preserved' and values['META_ENABLED']=='true'
    assert all(values[flag]=='false' for flag in app_config.SAFE_FLAGS)
    assert response.json()['restart_required'] and response.headers['cache-control']=='no-store'
    original=path.read_bytes()
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==409 and path.read_bytes()==original
    response=await client.post('/v1/integrations/meta/oauth/start',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert response.status_code==409 and response.json()['detail']=='meta_app_restart_required'


async def test_replace_secret_not_echoed_or_logged(client,identity,config_file,caplog):
    payload=await body(client,identity);payload.update(app_id='456',app_secret='new-synthetic-meta-secret')
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==200
    assert payload['app_secret'] not in response.text and payload['app_secret'] not in caplog.text
    assert dotenv_values(config_file[0])['META_APP_SECRET']==payload['app_secret']


@pytest.mark.parametrize('change',[
    {'app_secret':'bad-sensitive-marker'}, {'redirect_uri':'http://hostile.test/v1/integrations/meta/callback'},
    {'redirect_uri':'http://127.0.0.1:3200/v1/integrations/meta/callback\nINJECT=true'},
    {'api_version':'bad'}, {'write_enabled':True}, {'app_secret':{'secret':'raw-sensitive-marker'}},
])
async def test_invalid_inputs_do_not_echo_or_write(client,identity,config_file,change):
    # First marker is valid; add a newline to make the secret validation fail.
    if change.get('app_secret')=='bad-sensitive-marker':change={'app_secret':'bad-sensitive-marker\n'}
    payload=await body(client,identity);payload.update(change);before=config_file[0].read_bytes()
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==422 and config_file[0].read_bytes()==before
    assert 'sensitive-marker' not in response.text and MARKER not in response.text


async def test_unauthorized_write_cannot_change_file(client,identity,config_file):
    payload=await body(client,identity);before=config_file[0].read_bytes()
    for actor,expected in (('other',403),('outsider',404)):
        response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity[actor],json=payload)
        assert response.status_code==expected and config_file[0].read_bytes()==before


async def test_multiworkspace_global_mutation_refused(client,identity,config_file):
    async with Session.begin() as db:db.add(Workspace(name='Other tenant'))
    response=await client.get(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert response.status_code==409


@pytest.mark.parametrize('active',['token','oauth','sync'])
async def test_active_connections_oauth_sync_block_edits(client,identity,config_file,active):
    payload=await body(client,identity);before=config_file[0].read_bytes()
    async with Session.begin() as db:
        conn=MetaConnection(workspace_id=identity['workspace'],user_id=identity['user_id'],
                            token_ciphertext='fake-ciphertext' if active=='token' else None)
        db.add(conn);await db.flush()
        if active=='oauth':db.add(MetaOAuthState(digest='a'*64,browser_digest='b'*64,connection_id=conn.id,
                                connection_version=conn.version,expires_at=now()+timedelta(minutes=5)))
        if active=='sync':db.add(MetaSyncJob(connection_id=conn.id,connection_version=conn.version,
                            request_key=str(uuid4()),api_version='v26.0',kind='accounts'))
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==409 and config_file[0].read_bytes()==before


async def test_environment_override_refused(client,identity,config_file,monkeypatch):
    payload=await body(client,identity);before=config_file[0].read_bytes()
    monkeypatch.setenv('META_APP_ID','999')
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==409 and config_file[0].read_bytes()==before


async def test_write_failure_atomic_cleanup(client,identity,config_file):
    payload=await body(client,identity);before=config_file[0].read_bytes()
    with patch.object(app_config.os,'replace',side_effect=OSError('DO-NOT-ECHO-FAILURE')):
        response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert response.status_code==503 and 'DO-NOT-ECHO' not in response.text
    assert config_file[0].read_bytes()==before
    assert sorted(p.name for p in config_file[0].parent.iterdir())==['.env']


async def test_body_limit(client,identity,config_file):
    response=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],
                              json={'app_secret':'x'*9000})
    assert response.status_code==413 and 'xxx' not in response.text


@pytest.mark.parametrize('flag',['meta_write_enabled','meta_autopilot_enabled','ads_autopilot_global_enabled'])
async def test_runtime_write_gates_refuse_host_config_without_file_change(client,identity,config_file,monkeypatch,flag):
    payload=await body(client,identity);before=config_file[0].read_bytes()
    monkeypatch.setattr(settings(),flag,True)
    result=await client.put(BASE,params={'workspace_id':identity['workspace']},headers=identity['owner'],json=payload)
    assert result.status_code==409 and result.json()['detail']=='meta_app_requires_readonly_mode'
    assert config_file[0].read_bytes()==before
