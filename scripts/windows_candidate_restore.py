"""Exact Windows P8.4 candidate / pao_test profile; no primary URL or rollout."""
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
import sys
import tempfile

EXPECTED = PureWindowsPath('F:/PAO-ACOS/.runtime/p84-native-candidate-20261018')
ALLOWED_CANDIDATES = frozenset((EXPECTED, PureWindowsPath('F:/PAO-ACOS/.runtime/codex-login-candidate-20261019')))


class PgTools:
    def __init__(self, root, url, env, populated, manifest, platform=None):
        platform = sys.platform if platform is None else platform
        selected = PureWindowsPath(str(root))
        container = env.get('PAO_WINDOWS_CANDIDATE_PG_CONTAINER', '')
        if (platform != 'win32' or env.get('PAO_WINDOWS_CANDIDATE_RESTORE') != '1'
                or env.get('PAO_CI_RESTORE') or env.get('PAO_LINUX_LOCAL_RESTORE')
                or not populated or manifest or selected not in ALLOWED_CANDIDATES
                or PureWindowsPath(env.get('PAO_ROOT', '')) != selected
                or not re.fullmatch('[a-f0-9]{64}', container)
                or url.drivername != 'postgresql+asyncpg' or url.host != '127.0.0.1'
                or url.port != 15432 or url.database != 'pao_test' or url.username != 'pao'):
            raise ValueError('exact_windows_candidate_test_restore_required')
        if sys.platform == 'win32':
            path = Path(root).absolute()
            if path.resolve() != path or any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)()
                                           for p in (path, *path.parents)):
                raise ValueError('candidate_restore_links_denied')
        self.container = container
        self.created = set()

    def __call__(self, *args, **kwargs):
        values = list(args)
        interactive = values and values[0] == '-i'
        if interactive:
            values.pop(0)
        if len(values) < 2:
            raise ValueError('restore_command_required')
        values.pop(0)  # Never execute the legacy caller's container argument.
        command, *options = values
        if command == 'pg_dump':
            if interactive or options != ['-U', 'pao', '-d', 'pao_test', '-Fc']:
                raise ValueError('test_dump_only')
        elif command in ('createdb', 'dropdb'):
            if (interactive or len(options) != 3 or options[:2] != ['-U', 'pao']
                    or not re.fullmatch('pao_p7_restore_[a-f0-9]{32}', options[2])):
                raise ValueError('owned_clone_required')
            if (command == 'dropdb' and options[2] not in self.created
                    or command == 'createdb' and options[2] in self.created):
                raise ValueError('unowned_or_duplicate_clone')
        elif command == 'pg_restore':
            if (not interactive or len(options) != 6 or options[:3] != ['-U', 'pao', '-d']
                    or options[3] not in self.created or options[4:] != ['--no-owner', '--exit-on-error']):
                raise ValueError('owned_restore_only')
        else:
            raise ValueError('unsupported_restore_command')
        from pao_cli_runtime.docker_transport import DockerTransport
        from pao_cli_runtime.transport import child_environment
        with tempfile.TemporaryDirectory(prefix='pao-p84-restore-') as folder:
            env = child_environment(folder)
            env['DOCKER_CONFIG'] = folder
            result = subprocess.run([*DockerTransport.docker(), 'exec', *(['-i'] if interactive else []),
                self.container, command, *options], check=True, timeout=90, env=env,
                **({'creationflags': 0x08000000} if os.name == 'nt' else {}), **kwargs)
        if command == 'createdb':
            self.created.add(options[2])
        elif command == 'dropdb':
            self.created.remove(options[2])
        return result
