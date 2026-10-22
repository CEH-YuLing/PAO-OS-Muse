"""Bounded offline child transport; no engine registration or provider launch.

There is deliberately no arbitrary executable/argv/environment argument. This
stage can launch ONLY our source-controlled Python fixture. Reusing this code
for real CLIs requires provider adapters, native grants/accounting, durable
dispatch fencing, tool restrictions and OS sandbox acceptance in later stages.
"""
import asyncio
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Awaitable, Callable

from .containment import Containment
from .contracts import CliFailure, CliRequest, CliScope, Outcome

Authorize = Callable[[CliScope], Awaitable[bool]]
Sink = Callable[[str], Awaitable[None]]
FIXTURES = frozenset({'echo', 'usage', 'sleep', 'malformed', 'stderr', 'stderr_flood', 'flood',
                      'incomplete', 'trailing', 'false_success', 'bad_usage', 'duplicate', 'duplicate_keys', 'env', 'tree', 'delay'})


def _directory(path):
    path = Path(path)
    if not path.is_absolute() or len(path.parts) < 2:
        raise CliFailure('cli_runtime_path_invalid')
    try:
        for part in (path, *path.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise CliFailure('cli_runtime_path_invalid')
        if not path.is_dir():
            raise CliFailure('cli_runtime_path_invalid')
    except OSError:
        raise CliFailure('cli_runtime_path_invalid') from None
    return path


def child_environment(folder):
    # Do not mutate the parent's environment or copy PATH, API keys, .env,
    # SSH agent, proxy, provider profiles, user hooks or Python paths.
    env = {'HOME': str(folder), 'USERPROFILE': str(folder), 'TMP': str(folder), 'TEMP': str(folder),
           'CODEX_HOME': str(folder), 'CLAUDE_CONFIG_DIR': str(folder), 'LC_ALL': 'C.UTF-8'}
    if os.name == 'nt':
        root = os.environ.get('SystemRoot') or os.environ.get('SYSTEMROOT')
        if root:
            env['SystemRoot'] = root
    return env


async def _authorize(check, scope):
    try:
        if await check(scope) is not True:
            raise CliFailure('cli_access_denied')
    except asyncio.CancelledError:
        raise
    except Exception:
        raise CliFailure('cli_access_denied') from None


def _failure(group):
    if isinstance(group, CliFailure):
        return group
    for child in getattr(group, 'exceptions', ()):
        result = _failure(child)
        if result is not None:
            return result
    return None


class FixtureTransport:
    """One event-loop instance. In-memory duplicate fence is FIXTURE ONLY.

No queue, background daemon or retry loop. Existing ARQ/Temporal services own
those responsibilities. Never treat this in-memory fence as crash-safe storage.
"""
    def __init__(self, runtime_root, *, max_active=4, max_attempts=4096):
        self.runtime_root = _directory(runtime_root)
        if type(max_active) is not int or not 1 <= max_active <= 16 or type(max_attempts) is not int or not 1 <= max_attempts <= 4096:
            raise CliFailure('cli_contract_invalid')
        self.max_active, self.max_attempts = max_active, max_attempts
        self._active = set()
        self._attempts = set()

    async def run(self, request: CliRequest, *, authorize: Authorize, fixture='echo', on_delta: Sink | None = None):
        if not isinstance(request, CliRequest) or not callable(authorize):
            raise CliFailure('cli_contract_invalid')
        if fixture not in FIXTURES:
            raise CliFailure('cli_fixture_invalid')
        payload = json.dumps({'fixture': fixture, 'prompt': request.prompt}, ensure_ascii=False).encode('utf-8') + b'\n'
        if len(payload) > request.limits.max_input_bytes:
            raise CliFailure('cli_input_limit')
        # The same profile cannot run concurrently across two SMEs either.
        profile = (request.provider, request.scope.device_id, request.scope.profile_id)
        attempt = request.attempt_id
        if attempt in self._attempts:
            raise CliFailure('cli_attempt_already_dispatched')
        try:
            async with asyncio.timeout(request.limits.timeout_seconds):
                await _authorize(authorize, request.scope)
        except TimeoutError:
            raise CliFailure('cli_timeout') from None
        # Recheck after await; simultaneous submissions must not both dispatch.
        if attempt in self._attempts:
            raise CliFailure('cli_attempt_already_dispatched')
        if profile in self._active:
            raise CliFailure('cli_profile_busy')
        if len(self._active) >= self.max_active or len(self._attempts) >= self.max_attempts:
            raise CliFailure('cli_capacity')
        self._attempts.add(attempt)
        self._active.add(profile)
        try:
            # Includes scope callbacks and all pipe/process I/O after dispatch.
            async with asyncio.timeout(request.limits.timeout_seconds):
                with tempfile.TemporaryDirectory(prefix='pao-cli-fixture-', dir=_directory(self.runtime_root)) as folder:
                    return await self._run(request, authorize, fixture, on_delta, payload, Path(folder))
        except TimeoutError:
            raise CliFailure('cli_timeout') from None
        finally:
            self._active.discard(profile)

    async def _run(self, request, authorize, fixture, sink, payload, folder):
        proc = None
        containment = None
        text = []
        usage = None
        completed = False
        byte_count = 0

        def counted(data):
            nonlocal byte_count
            byte_count += len(data)
            if byte_count > request.limits.max_output_bytes:
                raise CliFailure('cli_output_limit')

        async def event(raw):
            nonlocal completed, usage
            try:
                def unique(pairs):
                    result = {}
                    for key, item in pairs:
                        if key in result:
                            raise ValueError()
                        result[key] = item
                    return result

                value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique)
                if not isinstance(value, dict) or completed:
                    raise ValueError()
                kind = value.get('type')
                if kind == 'delta' and set(value) == {'type', 'text'} and isinstance(value['text'], str):
                    # Recheck immediately before delivery; never replay a final
                    # denied result as a successful cached response.
                    await _authorize(authorize, request.scope)
                    text.append(value['text'])
                    if sink:
                        await sink(value['text'])
                elif kind == 'completed' and set(value) <= {'type', 'usage'}:
                    usage = value.get('usage')
                    if usage is not None:
                        if (not isinstance(usage, dict) or set(usage) != {'input_tokens', 'output_tokens'}
                                or any(type(n) is not int or not 0 <= n <= 10**9 for n in usage.values())):
                            raise ValueError()
                    completed = True
                else:
                    raise ValueError()
            except (ValueError, UnicodeError, TypeError, RecursionError):
                raise CliFailure('cli_protocol_invalid') from None

        async def stdout():
            buffered = b''
            while data := await proc.stdout.read(4096):
                counted(data)
                buffered += data
                while b'\n' in buffered:
                    line, buffered = buffered.split(b'\n', 1)
                    if not line or len(line) > request.limits.max_line_bytes:
                        raise CliFailure('cli_output_limit' if line else 'cli_protocol_invalid')
                    await event(line)
                if len(buffered) > request.limits.max_line_bytes:
                    raise CliFailure('cli_output_limit')
            if buffered:
                raise CliFailure('cli_protocol_invalid')

        async def stderr():
            # Drain concurrently, but retain/return no raw stderr or auth URL.
            while data := await proc.stderr.read(4096):
                counted(data)

        async def feed():
            await _authorize(authorize, request.scope)
            proc.stdin.write(payload)
            await proc.stdin.drain()
            proc.stdin.close()

        async def exited():
            # asyncio Process.wait can wait for inherited pipe handles held by
            # orphan children. Observe leader exit, close the whole group/job,
            # then wait for pumps/transport to finish.
            while proc.returncode is None:
                await asyncio.sleep(.01)
            containment.stop()

        try:
            script = Path(__file__).with_name('_fixture.py')
            if script.is_symlink() or not script.is_file():
                raise CliFailure('cli_fixture_invalid')
            options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                sys.executable, '-I', '-B', '-X', 'utf8', str(script),
                cwd=folder, env=child_environment(folder), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **options))
            try:
                proc = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                proc = await spawn
                raise
            containment = Containment(proc)
            try:
                async with asyncio.TaskGroup() as group:
                    for operation in (stdout(), stderr(), feed(), exited()):
                        group.create_task(operation)
            except ExceptionGroup as error:
                raise (_failure(error) or CliFailure('cli_process_failed')) from None
            if proc.returncode != 0:
                raise CliFailure('cli_process_failed')
            if not completed:
                raise CliFailure('cli_incomplete')
            await _authorize(authorize, request.scope)
            return Outcome(''.join(text), **(usage or {}))
        except OSError:
            raise CliFailure('cli_process_start_failed') from None
        finally:
            try:
                if containment:
                    containment.stop()
                elif proc and proc.returncode is None:
                    # Known fixture has not received stdin / cannot spawn yet.
                    proc.kill()
                if proc:
                    # On an output limit TaskGroup cancelled the readers. A
                    # paused StreamReader can keep Windows pipe transports
                    # open even after the job is dead. Drain/discard remaining
                    # bytes concurrently before waiting; never accumulate them.
                    async def discard(pipe):
                        while await pipe.read(4096):
                            pass

                    await asyncio.wait_for(asyncio.gather(
                        discard(proc.stdout), discard(proc.stderr), proc.wait()), timeout=3)
            except (OSError, TimeoutError):
                raise CliFailure('cli_cleanup_failed') from None
