"""Select the exact unexecuted suffix after a preserved fixture-only failure."""
import json
import os
from pathlib import Path

def pytest_collection_modifyitems(config,items):
    root=Path('F:/PAO-ACOS').resolve()
    path=Path(os.environ['PAO_CODEX_LOGIN_RESUME']).resolve()
    assert path.parent.parent==root/'.runtime' and path.parent.name.startswith('codex-login-tests-') and path.name=='resume-manifest.json'
    value=json.loads(path.read_text())
    assert [x.nodeid for x in items]==value['all_nodes'],'Collection changed; resume denied'
    count=value['passed_prefix_count']
    assert 0<count<len(items) and value['selected_nodes']==value['all_nodes'][count:]
    prefix=items[:count];items[:]=items[count:]
    config.hook.pytest_deselected(items=prefix)
