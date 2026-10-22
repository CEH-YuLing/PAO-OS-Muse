"""Read-only installed binary capability probe; no auth or inference commands.

This is NOT a grant or a sandbox acceptance. Probes run only --version/--help
under an empty temporary home; they never inspect an existing CODEX_HOME.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import os

from .contracts import CliFailure
from .transport import _directory, child_environment


@dataclass(frozen=True)
class CodexBinary:
    path: str
    sha256: str
    version: str
    flags: frozenset[str]

    def check(self):
        path = Path(self.path)
        _directory(path.parent)
        if path.is_symlink() or not path.is_file() or path.name not in ('codex', 'codex.exe'):
            raise CliFailure('cli_contract_invalid')
        if not re.fullmatch(r'[0-9a-f]{64}', self.sha256) or not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?', self.version):
            raise CliFailure('cli_contract_invalid')
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.sha256:
            raise CliFailure('cli_binary_changed')
        if not isinstance(self.flags, frozenset) or any(not isinstance(flag, str) for flag in self.flags):
            raise CliFailure('cli_contract_invalid')


def probe(binary, runtime_root, diagnostics=None, help_outputs=None):
    path = Path(binary)
    _directory(path.parent)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.name not in ('codex', 'codex.exe'):
        raise CliFailure('cli_contract_invalid')
    if os.name == 'nt' and path.suffix != '.exe':
        raise CliFailure('cli_contract_invalid')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    outputs = {}
    with tempfile.TemporaryDirectory(prefix='codex-help-', dir=_directory(runtime_root)) as folder:
        for name, args in (('version', ['--version']), ('root_help', ['--help']),
                           ('exec_help', ['exec', '--help']), ('sandbox_help', ['sandbox', '--help'])):
            try:
                result = subprocess.run([str(path), *args], stdin=subprocess.DEVNULL,
                    capture_output=True, timeout=15, cwd=folder, env=child_environment(folder),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except (OSError, subprocess.TimeoutExpired):
                if diagnostics is not None:
                    diagnostics[name] = {'completed': False}
                raise CliFailure('cli_process_failed') from None
            if diagnostics is not None:
                diagnostics[name] = {'completed': True, 'returncode': result.returncode,
                    'stdout_bytes': len(result.stdout), 'stderr_bytes': len(result.stderr)}
            if help_outputs is not None and len(result.stdout) <= 262144:
                help_outputs[name] = result.stdout.decode('utf-8', errors='replace')
            if result.returncode or len(result.stdout) + len(result.stderr) > 262144:
                raise CliFailure('cli_process_failed')
            outputs[name] = result.stdout.decode('utf-8', errors='strict')
    found = re.fullmatch(r'codex-cli (\d+\.\d+\.\d+(?:[-+][a-zA-Z0-9.-]+)?)\s*', outputs['version'])
    if not found:
        raise CliFailure('cli_protocol_invalid')
    flags = frozenset(re.findall(r'(?<![\w-])--[a-z][a-z-]+', outputs['root_help'] + outputs['exec_help']))
    pin = CodexBinary(str(path), digest, found[1], flags)
    pin.check()
    return pin, outputs
