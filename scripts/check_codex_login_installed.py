"""Before/after local install evidence. Diagnostic bearers are GET-only here."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'packages/cli-runtime'),str(ROOT/'scripts')]
from pao.config import settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot
from check_m2_restore import inspect

async def main(args):
    folder=args.folder.resolve();assert folder.parent==ROOT/'.runtime' and folder.name.startswith('codex-login-install-') and not folder.is_symlink()
    url=make_url(settings().database_url);assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    plan=json.loads((folder/'source-plan.json').read_text())
    if args.action=='before':
        value={'snapshot':await snapshot(url),'archives':await inspect(url),'binding':execution_binding(),
               'python_pin':digest(ROOT/'.runtime/acos-python-runtime.json'),'cli_registry':digest(ROOT/'.runtime/cli-device.json')}
        async with engine.connect() as db:
            assert await db.scalar(text("SELECT count(*) FROM cli_model_connections WHERE setup_operation_id IS NOT NULL"))==0
            assert await db.scalar(text("SELECT count(*) FROM cli_model_dispatches WHERE status IN ('dispatched','unknown')"))==0
        assert value['archives']['revision']=='0072' and len(value['archives']['counts'])==155
        with (folder/'before.json').open('x',encoding='utf-8') as output:json.dump(value,output,indent=2)
        print('Fresh primary read-only snapshot saved; no login/provider call')
        return
    before=json.loads((folder/'before.json').read_text())
    for name,change in plan['changes'].items():assert digest(ROOT/name)==change['after']
    assert digest(ROOT/'.runtime/acos-python-runtime.json')==before['python_pin']
    assert digest(ROOT/'.runtime/cli-device.json')==before['cli_registry']
    original=(folder/'env-before.private').read_bytes().replace(b'\r\n',b'\n')
    current=(ROOT/'.env').read_bytes().replace(b'\r\n',b'\n')
    assert current.replace(b'CLI_BROWSER_LOGIN_ENABLED=true\n',b'')==original
    assert settings().cli_browser_login_enabled and settings().cli_connections_enabled
    columns,hashes=before['snapshot'];assert (await snapshot(url,columns))[1]==hashes
    archive=await inspect(url)
    assert archive['revision']=='0072' and archive['artifact_hashes']==before['archives']['artifact_hashes'] and len(archive['counts'])==155
    contract=json.loads((ROOT/'packages/contracts/openapi.json').read_text())
    operations=sum(k in ('get','post','put','patch','delete','head','options') for methods in contract['paths'].values() for k in methods)
    assert operations==416
    replays=0;seen=set()
    async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=30) as client:
        assert (await client.get('/openapi.json')).json()==contract
        for p in ('/health','/ready'):assert (await client.get(p)).status_code==200
        for member in await db.scalars(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True))):
            user=await db.get(User,member.user_id);headers={'Authorization':'Bearer '+issue_token(user.id,user.auth_version)}
            prefix='/v1/workspaces/'+member.workspace_id+'/cli-connections'
            assert (await client.get(prefix+'/login-capabilities')).status_code==401
            caps=await client.get(prefix+'/login-capabilities',headers=headers)
            assert caps.status_code==200 and caps.json()['browser_login_enabled'] is True and caps.json()['tools_enabled'] is False
            listed=await client.get(prefix,headers=headers);assert listed.status_code==200
            for row in listed.json()['items']:
                assert row['owner_id']==user.id and row['workspace_id']==member.workspace_id
                assert row['profile_operation_pending'] is False
                state=await client.get(prefix+'/'+row['id']+'/login',headers=headers)
                assert state.status_code==200 and state.json()['user_code'] is None and state.json()['grant_activated'] is False
            runs=await db.execute(text("SELECT r.id,r.execution_plan FROM runs r JOIN sessions s ON s.id=r.session_id AND s.workspace_id=r.workspace_id WHERE r.workspace_id=:wid AND s.user_id=:uid AND r.status='completed'"),{'wid':member.workspace_id,'uid':user.id})
            for rid,value in runs:
                artifact=(value or {}).get('skill_artifact')
                if artifact:
                    response=await client.get('/v1/runs/'+str(rid)+'/skill-replay',headers=headers)
                    assert response.status_code==200 and response.json()['hash']==artifact['hash'] and response.json()['tools_reexecuted'] is False;replays+=1
            attempts=await db.execute(text('SELECT id,task_id,skill_artifact FROM task_attempts WHERE workspace_id=:wid AND skill_artifact IS NOT NULL'),{'wid':member.workspace_id})
            for aid,tid,artifact in attempts:
                if str(aid) in seen:continue
                response=await client.get('/v1/tasks/'+str(tid)+'/attempts/'+str(aid)+'/skill-replay',headers=headers)
                assert response.status_code==200 and response.json()['hash']==artifact['hash'] and response.json()['tools_reexecuted'] is False;replays+=1;seen.add(str(aid))
        assert (await client.get('http://127.0.0.1:3200/settings?tab=ai&section=providers')).status_code==200
    assert replays==3 and (await snapshot(url,columns))[1]==hashes
    result={'pass':True,'source_plan_installed_exactly':True,'schema':'0072','operations':416,'physical_tables':155,
        'binding':execution_binding(),'old_rows_exact':True,'read_only_archive_replays':replays,
        'CLI_registry_and_python_pin_unchanged':True,'browser_login_enabled':True,
        'only_intended_env_change':'CLI_BROWSER_LOGIN_ENABLED=true','diagnostic_bearer_GET_only':True,
        'provider_calls':0,'real_profile_login':False,'grant_activated':False,'native_job_tested':False,'production_accepted':False}
    (folder/'installed-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['before','after']);parser.add_argument('--folder',type=Path,required=True)
    async def run():
        try:await main(parser.parse_args())
        finally:await engine.dispose()
    asyncio.run(run())
