"""Fixed local profile management. Human login stays in an official CLI terminal."""
import json
import os
import re
import tempfile
from uuid import UUID, uuid4
from .contracts import CliFailure
from .docker_transport import DockerTransport, ImagePin, canonical
from .transport import child_environment


class ProfileAdmin:
    def __init__(self, image: ImagePin):
        self.transport = DockerTransport(image)
        self.image = image
        self.cleanup_verified = False

    async def operation(self, pin, mode):
        self.cleanup_verified = False
        if mode not in ('initialize','status'):
            raise CliFailure('cli_contract_invalid')
        for key in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
            canonical(pin.get(key))
        with tempfile.TemporaryDirectory(prefix='pao-cli-profile-') as config:
            env = child_environment(config)
            env['DOCKER_CONFIG'] = config
            volume = 'pao-cli-profile-' + UUID(pin['profile_id']).hex
            if mode == 'initialize':
                labels = []
                for key in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
                    labels += ['--label', 'pao.cli.' + key + '=' + pin[key]]
                await self.transport.command(['volume','create','--driver','local',*labels,volume], env)
            # Label/driver/image checks must precede every mount, even on replay.
            await self.transport.check_profile(pin, env)
            operation = str(uuid4())
            name = 'pao-cli-profile-check-' + UUID(operation).hex
            cid = None
            attempted = False
            try:
                attempted = True
                args = ['create', '--pull=never', '--name', name, '--label', 'pao.cli.operation_id=' + operation,
                        '--network=none','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
                        '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=512m','--cpus=1',
                        '--mount', 'type=volume,source=' + volume + ',target=/profile',
                        '--user', '0:0' if mode == 'initialize' else '65534:65534']
                if mode == 'initialize':
                    args += ['--cap-add=CHOWN']
                args += ['--entrypoint=python', self.image.image_id, '-B','-m','pao_cli_runtime.profile_admin',mode]
                cid = (await self.transport.command(args, env)).decode('ascii').strip()
                if not re.fullmatch(r'[0-9a-f]{64}', cid):
                    raise CliFailure('cli_docker_failed')
                raw = await self.transport.command(['start','--attach',cid], env)
                value = json.loads(raw)
                if (mode == 'initialize' and value != {'initialized':True}) or (mode == 'status' and
                    (set(value) != {'auth_mode','binary_sha256','binary_version','provider_inference_verified'}
                     or value['auth_mode'] not in ('chatgpt','not_authenticated')
                     or value['binary_sha256'] != self.image.binary_sha256 or value['binary_version'] != self.image.binary_version
                     or value['provider_inference_verified'] is not False)):
                    raise CliFailure('cli_protocol_invalid')
                return value
            finally:
                cleanup = not attempted
                try:
                    info = json.loads(await self.transport.command(['inspect', cid or name], env))[0]
                    if (not re.fullmatch(r'[0-9a-f]{64}', info['Id'])
                            or info['Config']['Labels'].get('pao.cli.operation_id') != operation):
                        raise ValueError()
                    await self.transport.command(['rm','--force',info['Id']], env)
                    cleanup = True
                except Exception:
                    pass
                if not cleanup:
                    raise CliFailure('cli_cleanup_failed')
                self.cleanup_verified = True

    def login_command(self, pin):
        for key in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
            canonical(pin.get(key))
        volume = 'pao-cli-profile-' + UUID(pin['profile_id']).hex
        return [*self.transport.docker(), 'run','--rm','--interactive','--tty','--pull=never',
                '--network=bridge','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
                '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=512m',
                '--user=65534:65534','--mount','type=volume,source='+volume+',target=/profile',
                '--env','HOME=/profile','--env','CODEX_HOME=/profile/codex',
                '--entrypoint=/usr/local/bin/codex',self.image.image_id,'login','--device-auth']
