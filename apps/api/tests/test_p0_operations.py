import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pao.modules.operations import health, checkpoint
from pao.modules.operations.request_trace import RequestTrace


async def test_worker_lease_present_missing_and_error():
    for ttl, expected in ((15000,True),(0,False),(-2,False)):
        result=await health.lease(SimpleNamespace(pttl=AsyncMock(return_value=ttl)),health.WORKER_KEY)
        assert result['healthy'] is expected
    result=await health.lease(SimpleNamespace(pttl=AsyncMock(side_effect=RuntimeError('private'))),'key')
    assert result['healthy'] is None and 'private' not in json.dumps(result)


async def test_disabled_bridge_does_not_read_redis():
    redis=SimpleNamespace(pttl=AsyncMock())
    result=await health.lease(redis,health.BRIDGE_KEY,False)
    assert result['status']=='disabled' and result['healthy'] is None
    redis.pttl.assert_not_awaited()


async def test_catalog_operations_is_authenticated_and_honest(client,identity):
    assert (await client.get('/v1/platform/catalog')).status_code==401
    response=await client.get('/v1/platform/catalog',headers=identity['owner'])
    operations=response.json()['operations']
    assert operations['worker']['scope']=='liveness_only'
    assert operations['production_reboot_accepted'] is False


async def test_trace_has_safe_schema_and_server_generated_correlation(caplog):
    messages=[]
    async def app(scope,receive,send):
        await send({'type':'http.response.start','status':200,'headers':[]})
        await send({'type':'http.response.body','body':b'private response'})
    scope={'type':'http','method':'GET','path':'/secret/private',
           'query_string':b'token=private-token','headers':[(b'authorization',b'private-credential')]}
    async def receive():return {'type':'http.request','body':b'private prompt'}
    async def send(message):messages.append(message)
    with caplog.at_level('INFO',logger='pao.request'):
        await RequestTrace(app)(scope,receive,send)
    record=json.loads(next(r.message for r in caplog.records if r.name=='pao.request'))
    assert set(record)=={'event','request_id','method','status','duration_ms',
                         'started_at','timestamp','route','client_ip','client_source',
                         'actor_id','workspace_id','multiple_workspaces'}
    assert record['route'] is None and record['actor_id'] is None
    assert len(record['request_id'])==32
    assert (b'x-request-id',record['request_id'].encode()) in messages[0]['headers']
    for private in ('private-token','private-credential','private prompt','private response','/secret/private'):
        assert private not in caplog.text


async def test_trace_exception_text_is_not_logged(caplog):
    async def app(scope,receive,send):raise ValueError('secret-provider-url')
    async def noop(*args):pass
    import pytest
    with caplog.at_level('INFO',logger='pao.request'),pytest.raises(ValueError):
        await RequestTrace(app)({'type':'http','method':'GET'},noop,noop)
    assert 'secret-provider-url' not in caplog.text
    assert json.loads(caplog.records[-1].message)['status']==500


def test_checkpoint_excludes_env_runtime_and_dependencies(tmp_path):
    (tmp_path/'apps/api').mkdir(parents=True)
    (tmp_path/'apps/api/code.py').write_text('pass\n',encoding='utf-8')
    (tmp_path/'.env').write_text('private-secret',encoding='utf-8')
    (tmp_path/'apps/api/.env').write_text('private-secret',encoding='utf-8')
    (tmp_path/'apps/api/node_modules').mkdir()
    (tmp_path/'apps/api/node_modules/private.js').write_text('private-secret',encoding='utf-8')
    archive=tmp_path/'backup.zip'
    manifest=checkpoint.archive(tmp_path,archive)
    assert set(manifest)=={'apps/api/code.py'}
    checkpoint.verify(archive,manifest)
    import pytest
    with pytest.raises(FileExistsError):
        checkpoint.archive(tmp_path,archive)


def test_checkpoint_rejects_tampered_manifest(tmp_path):
    (tmp_path/'apps').mkdir()
    (tmp_path/'apps/code.py').write_text('pass\n',encoding='utf-8')
    archive=tmp_path/'backup.zip'
    manifest=checkpoint.archive(tmp_path,archive)
    manifest['apps/code.py']='0'*64
    import pytest
    with pytest.raises(ValueError,match='hash mismatch'):
        checkpoint.verify(archive,manifest)


async def test_disabled_telegram_bridge_has_no_provider_call(monkeypatch):
    path=Path(__file__).resolve().parents[3]/'scripts/telegram_bridge.py'
    spec=importlib.util.spec_from_file_location('bridge_under_test',path)
    bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
    monkeypatch.setattr(bridge,'settings',lambda:SimpleNamespace(telegram_enabled=False,telegram_bot_token=''))
    forbidden=AsyncMock(side_effect=AssertionError('No Telegram network permitted'))
    monkeypatch.setattr(bridge,'bot_api',forbidden)
    assert await bridge.main() is None
    forbidden.assert_not_awaited()
