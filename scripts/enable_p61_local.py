"""Enable only local planning, retaining credentials and all execution gates."""
import os,re,tempfile
from pathlib import Path
from pao.config import ROOT,settings
from pao.integrations.meta.app_config import preserve_permissions

c=settings()
assert ROOT.resolve()==Path('F:/PAO-ACOS') and c.database_url.endswith('/pao_acos_local')
assert not any((c.meta_enabled,c.meta_write_enabled,c.meta_autopilot_enabled,c.ads_autopilot_global_enabled))
path=ROOT/'.env'; original=path.read_bytes(); lines=[]
for line in original.decode('utf-8-sig').splitlines():
    match=re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=',line)
    if not match or match.group(1).upper()!='WORKFLOW_PLANNING_ENABLED':lines.append(line)
temporary=None
try:
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=ROOT,prefix='.p61-enable-',suffix='.tmp',delete=False) as file:
        temporary=Path(file.name);file.write('\n'.join(lines+['WORKFLOW_PLANNING_ENABLED=true'])+'\n');file.flush();os.fsync(file.fileno())
    preserve_permissions(path,temporary)
    assert path.read_bytes()==original,'Configuration changed concurrently; refuse overwrite'
    os.replace(temporary,path);temporary=None
finally:
    if temporary is not None:temporary.unlink(missing_ok=True)
print('Local workflow planning enabled; provider credentials and execution gates unchanged. Reload API/worker.')
