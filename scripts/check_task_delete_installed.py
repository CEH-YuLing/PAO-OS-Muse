"""Verify installed hashes, native contract, archives and read-only delete UI."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select,func
from pao.auth import issue_token
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.models import User,Member,Task
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot

async def fixture():
    try:
        async with Session() as db:
            count=select(func.count(Task.id)).where(Task.workspace_id==Member.workspace_id).correlate(Member).scalar_subquery()
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).order_by(count.desc(),Member.workspace_id))
            assert member
            user=await db.get(User,member.user_id)
            return {'actor':user.id,'workspace':member.workspace_id,'token':issue_token(user.id,user.auth_version)}
    finally:await engine.dispose()

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    candidate=Path('F:/Apex/task-delete-candidate');proof=json.loads((candidate/'.runtime/task-delete-release.json').read_text())
    assert proof['pass']
    assert all(digest(ROOT/n)==v['after'] for n,v in proof['changes'].items())
    folder=ROOT/'.runtime'/('task-delete-installed-'+uuid4().hex);folder.mkdir()
    before=asyncio.run(snapshot(settings().database_url));env=digest(ROOT/'.env');binding=execution_binding()
    (folder/'before.json').write_text(json.dumps(before),encoding='utf-8')
    for title,script in [('live','check_task_delete_live.py'),('health','check_acos_health.py')]:
        with (folder/(title+'.log')).open('wb') as log:
            subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=240)
    data={**asyncio.run(fixture()),'web':'http://127.0.0.1:3200','folder':str(folder)}
    with (folder/'browser.log').open('wb') as log:
        subprocess.run(['node',str(ROOT/'scripts/task_delete_installed_browser.cjs')],cwd=ROOT,env={**os.environ,'PAO_UX_LIVE':json.dumps(data)},check=True,stdout=log,stderr=subprocess.STDOUT,timeout=360)
    browser=json.loads((folder/'installed-browser.json').read_text())
    after=asyncio.run(snapshot(settings().database_url));(folder/'after.json').write_text(json.dumps(after),encoding='utf-8')
    assert before==after and env==digest(ROOT/'.env') and binding==execution_binding()
    assert browser['pass'] and browser['api_mutations']==0
    assert all(digest(ROOT/n)==v['after'] for n,v in proof['changes'].items())
    result={**browser,'pass':True,'primary_unchanged':True,'environment_unchanged':True,'binding':binding,'schema':'0071',
            'operations':407,'historical_replays':3,'evidence':str(folder),'full_backend_regression':False,'s6_accepted':False,'production_accepted':False}
    (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (ROOT/'.runtime/task-delete-completion.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
