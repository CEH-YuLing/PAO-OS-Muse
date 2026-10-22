"""Serialize the operator probes sharing pao_test/Redis15; never lock primary usage."""
from contextlib import contextmanager
from pao.config import ROOT
import msvcrt

@contextmanager
def isolated_test_slot():
    path=ROOT/'.runtime/local-cycle-tests.lock'
    with path.open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise RuntimeError('Another local-cycle test probe owns pao_test/Redis15; do not start a second probe') from None
        try:yield
        finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
