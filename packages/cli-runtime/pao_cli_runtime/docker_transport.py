"""Fixed local Docker invocation, isolated profile volume and bounded lifecycle.

Native PAO authority/ledger are mandatory callers, not implemented by this file.
No public command/argv/env, host mounts, remote Docker, token copy or retries.
"""
import asyncio
from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import re
import tempfile
from uuid import UUID

from .codex_protocol import CodexExecParser, json_object
from .codex_worker import BINARY_SHA256, VERSION
from .contracts import CliFailure, Limits
from .transport import child_environment


def canonical(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise CliFailure('cli_contract_invalid') from None
    return value


@dataclass(frozen=True)
class ImagePin:
    image_id: str
    binary_sha256: str
    binary_version: str

    def __post_init__(self):
        if (not isinstance(self.image_id, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', self.image_id)
                or self.binary_sha256 != BINARY_SHA256 or self.binary_version != VERSION):
            raise CliFailure('cli_contract_invalid')


class DockerTransport:
    def __init__(self, image: ImagePin, limits=Limits(timeout_seconds=90)):
        if not isinstance(image, ImagePin) or not isinstance(limits, Limits):
            raise CliFailure('cli_contract_invalid')
        self.image, self.limits = image, limits
        self.cleanup_verified = False

    @staticmethod
    def docker():
        if os.name == 'nt':
            return ['C:/Program Files/Docker/Docker/resources/bin/docker.exe', '--host',
                    'npipe:////./pipe/dockerDesktopLinuxEngine']
        return ['/usr/bin/docker', '--host', 'unix:///var/run/docker.sock']

    async def command(self, args, env, timeout=15):
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(*self.docker(), *args, env=env,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            **({'creationflags': 0x08000000} if os.name == 'nt' else {})))
        try:
            process = await asyncio.shield(spawn)
        except asyncio.CancelledError:
            process = await spawn
            await self.close_client(process)
            raise
        try:
            async with asyncio.timeout(timeout):
                output, error = await process.communicate()
                if len(output) + len(error) > 262144:
                    raise CliFailure('cli_output_limit')
                if process.returncode:
                    raise CliFailure('cli_docker_failed')
                return output
        finally:
            await self.close_client(process)

    @staticmethod
    async def close_client(process):
        async def discard(reader):
            while await reader.read(8192):
                pass
        if process.returncode is None:
            process.kill()
        # A cancelled paused reader can otherwise deadlock Process.wait on
        # Windows after a flood. Drain/discard both pipes after containment ends.
        async with asyncio.timeout(5):
            await asyncio.gather(discard(process.stdout), discard(process.stderr), process.wait())

    async def check_profile(self, pin, env):
        for key in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
            canonical(pin.get(key))
        if pin.get('binary_sha256') != self.image.binary_sha256 or pin.get('binary_version') != self.image.binary_version:
            raise CliFailure('cli_binary_changed')
        if pin.get('runtime_image_id') != self.image.image_id:
            raise CliFailure('cli_binary_changed')
        volume = 'pao-cli-profile-' + UUID(pin['profile_id']).hex
        raw = await self.command(['volume', 'inspect', volume], env)
        try:
            rows = json.loads(raw)
            expected = {'pao.cli.' + key: pin[key] for key in
                        ('workspace_id','actor_id','connection_id','device_id','profile_id')}
            if (not isinstance(rows, list) or len(rows) != 1 or rows[0]['Name'] != volume
                    or rows[0].get('Driver') != 'local' or rows[0].get('Options')
                    or rows[0].get('Labels') != expected):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise CliFailure('cli_profile_binding_invalid') from None
        raw = await self.command(['image', 'inspect', self.image.image_id], env)
        try:
            info = json.loads(raw)[0]
            labels = info['Config'].get('Labels') or {}
            if (info['Id'] != self.image.image_id or info['Config']['User'] != '65534:65534'
                    or labels.get('pao.cli.version') != VERSION
                    or labels.get('pao.cli.binary-sha256') != BINARY_SHA256):
                raise ValueError()
        except (ValueError, KeyError, TypeError, IndexError):
            raise CliFailure('cli_binary_changed') from None
        return volume

    async def invoke(self, pin, attempt_id, prompt, authorize):
        canonical(attempt_id)
        if not callable(authorize) or not isinstance(prompt, str):
            raise CliFailure('cli_contract_invalid')
        raw = json.dumps({'model': pin.get('model'), 'prompt': prompt}, ensure_ascii=False).encode()
        if len(raw) > self.limits.max_input_bytes:
            raise CliFailure('cli_input_limit')
        cid = None
        creation_attempted = False
        name = 'pao-cli-attempt-' + UUID(attempt_id).hex
        process = None
        tasks = []
        self.cleanup_verified = False
        async def access():
            try:
                if await authorize(pin) is not True:
                    raise ValueError()
            except asyncio.CancelledError:
                raise
            except Exception:
                raise CliFailure('cli_access_denied') from None
        with tempfile.TemporaryDirectory(prefix='pao-cli-docker-') as config:
            env = child_environment(config)
            env['DOCKER_CONFIG'] = config
            try:
                await access()
                volume = await self.check_profile(pin, env)
                async with asyncio.timeout(self.limits.timeout_seconds):
                    # Create-before-start plus stdin handshake ensures no prompt
                    # is sent before containment and a fresh authority check.
                    creation_attempted = True
                    created = await self.command(['create', '--pull=never', '--interactive', '--name', name,
                        '--label', 'pao.cli.attempt_id=' + attempt_id, '--network=bridge', '--read-only',
                        '--tmpfs', '/tmp:rw,noexec,nosuid,size=128m', '--cap-drop=ALL',
                        '--security-opt=no-new-privileges', '--pids-limit=64', '--memory=768m', '--cpus=1',
                        '--user=65534:65534', '--mount', f'type=volume,source={volume},target=/profile',
                        '--entrypoint=python', self.image.image_id, '-B', '-m', 'pao_cli_runtime.codex_worker'], env)
                    cid = created.decode('ascii').strip()
                    if not re.fullmatch(r'[0-9a-f]{64}', cid):
                        raise CliFailure('cli_docker_failed')
                    await access()
                    spawn = asyncio.create_task(asyncio.create_subprocess_exec(*self.docker(), 'start', '--attach', '--interactive', cid,
                        env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        **({'creationflags': 0x08000000} if os.name == 'nt' else {})))
                    try:
                        process = await asyncio.shield(spawn)
                    except asyncio.CancelledError:
                        process = await spawn
                        raise
                    parser = CodexExecParser(self.limits)
                    async def stdout():
                        while chunk := await process.stdout.read(8192):
                            parser.feed(chunk)
                    async def stderr():
                        count = 0
                        while chunk := await process.stderr.read(8192):
                            count += len(chunk)
                            if count > self.limits.max_output_bytes:
                                raise CliFailure('cli_output_limit')
                    async def watchdog():
                        while process.returncode is None:
                            await access()
                            await asyncio.sleep(.25)
                    tasks = [asyncio.create_task(stdout()), asyncio.create_task(stderr()), asyncio.create_task(watchdog())]
                    await access()
                    process.stdin.write(raw)
                    await process.stdin.drain()
                    process.stdin.close()
                    waiter = asyncio.create_task(process.wait())
                    tasks.append(waiter)
                    # FIRST_EXCEPTION aborts on reader/watchdog failure; without
                    # failures it waits for exit AND both pipe EOFs. Do not cancel
                    # readers at leader exit and truncate the terminal event.
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
                    for task in done:
                        if task.exception():
                            raise task.exception()
                    await access()
                    result = parser.finish(await waiter)
                    return replace(result, mode='codex_cli_live', provider_inference_verified=True)
            except TimeoutError:
                raise CliFailure('cli_timeout') from None
            finally:
                for task in tasks:
                    task.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                if not cid and creation_attempted:
                    # A cancelled/timed-out docker create may have committed in
                    # the daemon before the CLI returned the ID. Recover by exact
                    # generated name+label, never scan or remove other resources.
                    try:
                        info = json.loads(await self.command(['inspect', name], env))[0]
                        candidate = info['Id']
                        if (re.fullmatch(r'[0-9a-f]{64}', candidate)
                                and info['Config']['Labels'].get('pao.cli.attempt_id') == attempt_id):
                            cid = candidate
                    except Exception:
                        pass
                if cid:
                    try:
                        info = json.loads(await self.command(['inspect', cid], env))[0]
                        if info['Id'] != cid or info['Config']['Labels'].get('pao.cli.attempt_id') != attempt_id:
                            raise ValueError()
                        # Removal is scoped to the exact freshly-created ID and
                        # label, never by wildcard/name/PID. The profile persists.
                        await self.command(['rm', '--force', cid], env)
                        self.cleanup_verified = True
                    except Exception:
                        self.cleanup_verified = False
                else:
                    self.cleanup_verified = not creation_attempted
                if process:
                    try:
                        await self.close_client(process)
                    except Exception:
                        self.cleanup_verified = False
                if not self.cleanup_verified:
                    raise CliFailure('cli_cleanup_failed')
