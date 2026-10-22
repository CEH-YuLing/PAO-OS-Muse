"""Pause Meta on the approved ACOS host without deleting App/token/key settings."""
import os,re,tempfile
from pathlib import Path
from pao.config import ROOT,settings
from pao.integrations.meta.app_config import preserve_permissions

assert ROOT.resolve()==Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
path=ROOT/'.env';original=path.read_bytes();flags={'META_ENABLED':'false','META_WRITE_ENABLED':'false',
    'META_AUTOPILOT_ENABLED':'false','ADS_AUTOPILOT_GLOBAL_ENABLED':'false'}
lines=[]
for line in original.decode('utf-8-sig').splitlines():
    match=re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=',line)
    if not match or match.group(1).upper() not in flags:lines.append(line)
temporary=None
try:
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=ROOT,prefix='.meta-pause-',suffix='.tmp',delete=False) as file:
        temporary=Path(file.name);file.write('\n'.join(lines+[f'{k}={v}' for k,v in flags.items()])+'\n');file.flush();os.fsync(file.fileno())
    preserve_permissions(path,temporary)
    assert path.read_bytes()==original,'Configuration changed concurrently; refuse overwrite'
    os.replace(temporary,path);temporary=None
finally:
    if temporary is not None:temporary.unlink(missing_ok=True)
print('Meta paused locally; App/secret/encryption keys preserved. Reload API/worker.')
