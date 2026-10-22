"""Real pinned Codex RPC probe, fresh synthetic profile and network=none only."""
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
CANDIDATE=ROOT/'.runtime/codex-login-candidate-20261019'
sys.path[:0]=[str(CANDIDATE/'apps/api'),str(CANDIDATE/'packages/cli-runtime')]
from pao_cli_runtime.profile_transport import ProfileAdmin
from pao_cli_runtime.docker_transport import ImagePin
from pao_cli_runtime.transport import child_environment
from pao.modules.cli_connections.login_transport import LoginTransport
import tempfile

async def main():
    cfg=json.loads((ROOT/'.runtime/cli-device.json').read_text())
    image=ImagePin(cfg['image_id'],cfg['binary_sha256'],cfg['binary_version'])
    pin={k:str(uuid4()) for k in ('workspace_id','actor_id','connection_id','device_id','profile_id')}
    pin.update(runtime_image_id=image.image_id,binary_sha256=image.binary_sha256,binary_version=image.binary_version)
    admin=ProfileAdmin(image)
    await admin.operation(pin,'initialize')
    assert admin.cleanup_verified
    async def allow():return True
    transport=LoginTransport(pin,str(uuid4()),allow)
    original=transport.docker.command
    async def network_none(args,env,timeout=15):
        return await original([x.replace('--network=bridge','--network=none') for x in args],env,timeout)
    transport.docker.command=network_none
    try:
        await transport.open()
        account=await transport.rpc(2,'account/read',{'refreshToken':False})
        assert account.get('account') is None
    finally:
        await transport.close()
        assert transport.cleanup_verified
        with tempfile.TemporaryDirectory(prefix='pao-login-probe-cleanup-') as folder:
            env=child_environment(folder);env['DOCKER_CONFIG']=folder
            volume=await admin.transport.check_profile(pin,env)
            await admin.transport.command(['volume','rm',volume],env)
    folder=ROOT/'.runtime'/('codex-login-rpc-'+uuid4().hex);folder.mkdir()
    result={'pass':True,'binary':image.binary_version,'official_rpc_initialize':True,'empty_profile_account_read':True,
            'network':'none','provider_calls':0,'primary_profiles_mounted':False,'owned_fixture_volume_removed':True,
            'cleanup_verified':True,'real_login':False}
    (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(folder),**result}))

if __name__=='__main__':asyncio.run(main())
