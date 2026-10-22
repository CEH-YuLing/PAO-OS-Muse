"""Installed GET-only diagnostic; no owner consent, provider or setup mutations."""
import asyncio,hashlib,json,sys,os,subprocess
from pathlib import Path
from uuid import uuid4
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts'),str(ROOT/'packages/cli-runtime')]
from pao.config import settings
from pao.db import Session,engine
from pao.models import Member,User
from pao.auth import issue_token
from check_installation_ai_migration import signatures
from check_m2_restore import inspect
from check_p84_foundation import binding,health
from pao.modules.cli_connections.runtime import device_config


async def main():
    cfg=settings();url=make_url(cfg.database_url)
    assert ROOT==Path('F:/PAO-ACOS') and (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    assert cfg.installation_ai_enabled and cfg.installation_ai_manager_ids==['165b1fa6-f443-4f66-bddb-51eb5b6e6fa5']
    folder=ROOT/'.runtime'/('installation-ai-live-'+uuid4().hex);folder.mkdir()
    before=await signatures(url);schema=await inspect(url);device=device_config()
    state={'pass':False,'provider_calls':0,'diagnostic_GET_only':True,'runtime_swapped':False}
    try:
        assert schema['revision']=='0075' and len(schema['counts'])==161
        replays=0;seen=set()
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',trust_env=False,timeout=15) as client:
            saved=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json()==saved
            assert (await client.get('/v1/installation-ai',params={'workspace_id':'ef221310-5afc-4c21-9f9e-4aa9bf4b3e79'})).status_code==401
            for member in await db.scalars(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True))):
                user=await db.get(User,member.user_id)
                headers={'Authorization':'Bearer '+issue_token(user.id,user.auth_version)}
                response=await client.get('/v1/installation-ai',params={'workspace_id':member.workspace_id},headers=headers)
                assert response.status_code==200 and response.headers['cache-control']=='no-store'
                value=response.json();assert value['enabled'] and not value['provider_calls']
                assert value['can_manage']==(user.id in cfg.installation_ai_manager_ids)
                for rid,plan in await db.execute(text("SELECT r.id,r.execution_plan FROM runs r JOIN sessions s ON s.id=r.session_id WHERE r.workspace_id=:wid AND s.user_id=:uid AND r.status='completed'"),{'wid':member.workspace_id,'uid':user.id}):
                    artifact=(plan or {}).get('skill_artifact')
                    if not artifact or str(rid) in seen:continue
                    replay=await client.get(f'/v1/runs/{rid}/skill-replay',headers=headers)
                    assert replay.status_code==200 and replay.json()['hash']==artifact['hash'] and replay.json()['tools_reexecuted'] is False
                    seen.add(str(rid));replays+=1
                for aid,tid,artifact in await db.execute(text('SELECT id,task_id,skill_artifact FROM task_attempts WHERE workspace_id=:wid AND skill_artifact IS NOT NULL'),{'wid':member.workspace_id}):
                    if str(aid) in seen:continue
                    replay=await client.get(f'/v1/tasks/{tid}/attempts/{aid}/skill-replay',headers=headers)
                    assert replay.status_code==200 and replay.json()['hash']==artifact['hash'] and replay.json()['tools_reexecuted'] is False
                    seen.add(str(aid));replays+=1
        assert replays==3 and len(schema['artifact_hashes'])==3
        if '--browser' in sys.argv:
            async with Session() as db:
                user=await db.get(User,'165b1fa6-f443-4f66-bddb-51eb5b6e6fa5')
                fixture={'token':issue_token(user.id,user.auth_version),'actor':user.id,'workspace':'ef221310-5afc-4c21-9f9e-4aa9bf4b3e79','folder':str(folder)}
            with (folder/'browser.log').open('wb') as log:
                subprocess.run(['node',str(ROOT/'scripts/installation_ai_installed_browser.cjs')],cwd=ROOT,
                    env={**os.environ,'PAO_AI_INSTALLED':json.dumps(fixture)},stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
            state['browser']=json.loads((folder/'browser-receipt.json').read_text())
        state.update(health=health(),schema='0075',physical_tables=161,operations=429,
            binding=binding(),historical_HTTP_replays=replays,primary_unchanged=before==await signatures(url),
            cli_runtime_pin_valid=device==device_config())
        # Compare original config text without exposing its contents or copying
        # credentials into a report. Only two new non-secret lines may differ.
        original='\n'.join(line for line in (ROOT/'.env').read_text(encoding='utf-8').split('\n') if not line.startswith(('INSTALLATION_AI_ENABLED=','INSTALLATION_AI_MANAGER_IDS=')))
        state['only_two_installation_config_lines_added']=hashlib.sha256(original.encode()).hexdigest()=='448baa03d718b01fd7c86208373b462cce80e586fe1effcb293acba4c9ff46fb'
        state['pass']=all(state[k] for k in ('primary_unchanged','cli_runtime_pin_valid','only_two_installation_config_lines_added')) and all(v==200 for v in state['health'].values())
    finally:
        await engine.dispose()
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**state}))
    assert state['pass']


if __name__=='__main__':asyncio.run(main())
