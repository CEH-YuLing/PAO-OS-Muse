"""Operator lock smoke: deny overlap, then allow reacquisition after release."""
import os,subprocess,sys
from pathlib import Path
from local_cycle_test_lock import isolated_test_slot
code="from local_cycle_test_lock import isolated_test_slot\nwith isolated_test_slot(): pass"
env={**os.environ,'PYTHONPATH':os.environ.get('PYTHONPATH','')+os.pathsep+str(Path(__file__).parent)}
with isolated_test_slot():
    child=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=20)
    assert child.returncode!=0 and 'Another local-cycle test probe' in child.stderr
with isolated_test_slot():pass
print('Operator test lock: overlap denied; release/reacquire passed (2 guards).')
