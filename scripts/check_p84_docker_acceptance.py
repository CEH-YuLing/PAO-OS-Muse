"""Actual pinned image tests with synthetic identities and NO login/provider calls."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.docker_transport import ImagePin, DockerTransport
from pao_cli_runtime.profile_transport import ProfileAdmin
from pao_cli_runtime.codex_worker import BINARY_SHA256, VERSION
from pao_cli_runtime.contracts import CliFailure


async def profile_test(image, folder):
    pin = {**{k:str(uuid4()) for k in ('workspace_id','actor_id','connection_id','device_id','profile_id')},
           'binary_sha256':BINARY_SHA256,'binary_version':VERSION,'runtime_image_id':image,
           'model':'synthetic-offline-no-auth'}
    admin = ProfileAdmin(ImagePin(image, BINARY_SHA256, VERSION))
    volume = 'pao-cli-profile-' + pin['profile_id'].replace('-', '')
    state = {'synthetic_only': True, 'provider_calls':0, 'login_started':False, 'profile':pin,
             'volume_removed':False, 'pass':False}
    try:
        initialized = await admin.operation(pin, 'initialize')
        status = await admin.operation(pin, 'status')
        state.update(initialized=initialized == {'initialized':True},
                     unauthenticated=status['auth_mode'] == 'not_authenticated')
        transport = DockerTransport(ImagePin(image, BINARY_SHA256, VERSION))
        async def authorize(_):
            return True  # Only this explicit no-auth operator fixture, not native PAO consent.
        denied = False
        try:
            await transport.invoke(pin, str(uuid4()), 'Synthetic no-auth test only.', authorize)
        except CliFailure as error:
            denied = error.code == 'cli_provider_failed'
            state['failure_code'] = error.code
        state.update(worker_denied_without_auth=denied, container_cleanup_verified=transport.cleanup_verified)
        # Wrong SME cannot use a profile merely by knowing the profile UUID.
        wrong = {**pin, 'workspace_id':str(uuid4())}
        cross_denied = False
        try:
            await transport.invoke(wrong, str(uuid4()), 'Synthetic scope test.', authorize)
        except CliFailure as error:
            cross_denied = error.code == 'cli_profile_binding_invalid'
        state['cross_workspace_denied'] = cross_denied
        state['pass'] = all(state[k] for k in ('initialized','unauthenticated','worker_denied_without_auth',
                                              'container_cleanup_verified','cross_workspace_denied'))
    finally:
        # Only the randomly-created synthetic volume, labels verified before
        # removal. No real login ever ran against it; no other profile touched.
        raw = subprocess.check_output(['docker','volume','inspect',volume], timeout=15)
        value = json.loads(raw)[0]
        expected = {'pao.cli.'+k:pin[k] for k in ('workspace_id','actor_id','connection_id','device_id','profile_id')}
        if value['Name'] == volume and value.get('Labels') == expected and value.get('Driver') == 'local' and not value.get('Options'):
            subprocess.run(['docker','volume','rm',volume], check=True, capture_output=True, timeout=15)
            state['volume_removed'] = True
        (folder / 'profile-test.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    ImagePin(args.image, BINARY_SHA256, VERSION)
    folder = ROOT / '.runtime' / ('p84-docker-acceptance-' + uuid4().hex)
    folder.mkdir()
    fixtures = []
    for mode in ([], ['tool-injection']):
        command = ['docker','run','--rm','--pull=never','--network=none','--read-only',
            '--tmpfs','/tmp:rw,noexec,nosuid,size=128m','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--pids-limit=64','--memory=768m','--cpus=1','--user=65534:65534',args.image,*mode]
        result = subprocess.run(command, capture_output=True, timeout=55)
        name = 'tool-injection' if mode else 'normal'
        (folder / (name + '.log')).write_bytes(result.stdout + result.stderr)
        try:
            value = json.loads(result.stdout)
        except ValueError:
            value = {'pass':False}
        fixtures.append({'mode':name,'returncode':result.returncode,'pass':result.returncode == 0 and value.get('pass') is True})
    profile = asyncio.run(profile_test(args.image, folder))
    state = {'pass':all(v['pass'] for v in fixtures) and profile['pass'] and profile['volume_removed'],
             'image':args.image,'fixtures':fixtures,'profile_pass':profile['pass'],
             'synthetic_volume_removed':profile['volume_removed'], 'real_subscription_calls':0,
             'native_PAO_job_test':False, 'whole_P84_C_accepted':False, 'production_accepted':False}
    (folder / 'receipt.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    print(folder)
    print(json.dumps(state))
    raise SystemExit(0 if state['pass'] else 1)


if __name__ == '__main__':
    main()
