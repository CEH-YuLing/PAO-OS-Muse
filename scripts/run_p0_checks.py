"""Local/CI P0 gate; backend tests are confined to pao_test and Redis DB15."""
import json
from pathlib import Path
import subprocess
import sys
from pao.config import ROOT
from pao.main import app
from pao.models import Base

def call(*args):
    subprocess.run(list(args),cwd=ROOT,check=True)

def main(preflight_only=False):
    saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    assert app.openapi()==saved, 'Full OpenAPI differs from saved UTF-8 contract'
    assert len(Base.metadata.tables)==160, 'ORM metadata table set changed; review migration'
    print('PASS full OpenAPI/160 ORM tables (GD00 reviewed source through0075)',flush=True)
    if preflight_only:
        print('PRECHECK ONLY: backend regression/Node/TypeScript/build not executed',flush=True)
        return
    call(sys.executable,str(ROOT/'scripts/test_backend.py'))
    call('node','--test',*[str(path.relative_to(ROOT)) for path in sorted((ROOT/'apps/web/lib').glob('*.test.mjs'))])
    call('node','node_modules/typescript/bin/tsc','--noEmit','-p','apps/web/tsconfig.json')
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--preflight-only',action='store_true')
    main(parser.parse_args().preflight_only)
