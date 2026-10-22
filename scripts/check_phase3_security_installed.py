"""Bind M6 frontend evidence to installed files and read-only live checks."""
import asyncio,hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from sqlalchemy import select
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import entries,digest
from backup_acos_checkpoint import frontend_supplements
from check_p11_migration import snapshot

def frontend(root):return {k:v for k,v in {**entries(root),**frontend_supplements(root)}.items() if k.startswith('apps/web/') and not k.endswith('next-env.d.ts')}
async def principal_fixture():
 try:
  async with Session() as db:
   member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)))
   assert member
   user=await db.get(User,member.user_id)
   return {'token':issue_token(user.id,user.auth_version),'actor':user.id,'workspace':member.workspace_id}
 finally:await engine.dispose()
def main():
 cfg=settings();url=make_url(cfg.database_url)
 assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
 receipt_path=Path(sys.argv[1]).resolve();assert receipt_path.is_relative_to(ROOT/'.runtime/phase3-browser-runs') and receipt_path.name=='receipt.json'
 browser=json.loads(receipt_path.read_text());assert browser['pass'] and browser['plan_deep_link'] and browser['production_build'] and browser['next_version']=='15.5.28'
 for name,hashed_dependency in browser['root_dependency_hashes'].items():assert digest(ROOT/name)==hashed_dependency
 assert json.loads((receipt_path.parent/'cleanup.json').read_text())['pass']
 files=frontend(ROOT);candidate=frontend(Path('F:/Apex/phase3-candidate'));assert files==candidate
 hashed=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest();assert hashed==browser['frontend_sha256']
 binding=execution_binding();backend=json.loads((ROOT/'.runtime/s62-backend.json').read_text())
 assert backend['pass'] and backend['tests']==2258 and backend['binding']==binding==browser['binding']
 assert backend['failures']==backend['errors']==backend['skipped']==0
 before=asyncio.run(snapshot(url));env_hash=digest(ROOT/'.env')
 folder=ROOT/'.runtime/phase3-security-installed-runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S');folder.mkdir(parents=True)
 def run(title,command,env=None):
  checked=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
  (folder/(title+'.log')).write_text(checked.stdout+checked.stderr,encoding='utf-8');checked.check_returncode();return checked.stdout
 test_files=sorted(str(p) for p in (ROOT/'apps/web/lib').glob('*.test.mjs'))
 tests=run('node',['node','--test',*test_files]);assert 'tests 120' in tests and 'fail 0' in tests
 run('route-types',['node','node_modules/next/dist/bin/next','typegen','apps/web'])
 run('native-compat',['node','--test','scripts/test_security_compat.cjs'])
 run('audit-unit',['node','--test','scripts/test_js_dependencies.cjs'])
 audit=json.loads(run('runtime-audit',['node','scripts/check_js_dependencies.cjs']).strip().splitlines()[-1]);assert audit['runtime_gate_pass']
 run('typecheck',['node','node_modules/typescript/bin/tsc','--noEmit','-p','apps/web/tsconfig.json'])
 live=json.loads(run('live',[sys.executable,'scripts/check_s62_live.py']).strip().splitlines()[-1]);assert live['pass']
 health=json.loads(run('health',[sys.executable,'scripts/check_acos_health.py']).strip().splitlines()[-1]);assert health['operations']['worker']['healthy']
 fixture={**asyncio.run(principal_fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
 run('installed-browser',['node','scripts/m6_installed_browser.cjs'],{**os.environ,'PAO_M6_LIVE':json.dumps(fixture)})
 assert before==asyncio.run(snapshot(url)) and env_hash==digest(ROOT/'.env') and binding==execution_binding() and files==frontend(ROOT)
 result={'pass':True,'phase':'Phase3_security_release','local_accepted':True,'frontend_sha256':hashed,'binding':binding,
  'node_tests':120,'typecheck':True,'production_build_candidate':True,'isolated_browser_receipt':str(receipt_path),
  'installed_read_only_browser':True,'live':live,'health':health,'backend_baseline_reused':2258,'next_version':'15.5.28','dependency_security':audit,
  'business_hashes_unchanged':True,'env_unchanged':True,'provider_calls':False,'s6_accepted':False,'production_accepted':False,'evidence':str(folder)}
 (ROOT/'.runtime/phase3-security-completion.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'pass':True,'phase':'Phase3_security_release','node_tests':120,'backend_unchanged':True,'installed_browser':True,'evidence':str(folder)}))
if __name__=='__main__':main()
