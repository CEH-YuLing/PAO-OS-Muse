"""Content identity of the host transport, independent of the Codex binary pin."""
import hashlib
from pathlib import Path

from .contracts import CliFailure

PACKAGE = Path(__file__).absolute().parent


def library_digest():
    if PACKAGE.is_symlink() or getattr(PACKAGE, 'is_junction', lambda: False)():
        raise CliFailure('cli_binary_changed')
    files = sorted(PACKAGE.glob('*.py'))
    if not files or not (PACKAGE / '__init__.py').is_file():
        raise CliFailure('cli_binary_changed')
    digest = hashlib.sha256()
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise CliFailure('cli_binary_changed')
        # Raw bytes: the Docker context and installed host package must agree,
        # rather than quietly normalizing a modified installation.
        digest.update(path.name.encode('utf-8') + b'\0')
        digest.update(path.read_bytes() + b'\0')
    return digest.hexdigest()
