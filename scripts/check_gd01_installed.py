"""Installed authenticated GET-only contracts, history replay and browser check."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import httpx
from sqlalchemy import select,text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts'),str(ROOT/'packages/cli-runtime')]
from pao.config import settings
from pao.db import Session,engine
from pao.models import Member,User,ChatSession
from pao.auth import issue_token
from check_pao_mcp_local import digests
from check_p84_foundation import binding,health,primary_schema
from check_installation_ai_migration import signatures
from check_m2_restore import inspect


async def main():
    cfg=settings();url=make_url(cfg.database_url)
    assert ROOT==Path('F:/PAO-ACOS') and (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    folder=ROOT/'.runtime'/('gd01-installed-'+uuid4().hex);folder.mkdir()
    before=await signatures(url);source=digests();archive=await inspect(url)
    state={'pass':False,'provider_calls':0,'primary_mutations':0,'GET_only':True,'replays':0}
    try:
        assert archive['revision']=='0077' and len(archive['counts'])==161
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',trust_env=False,timeout=20) as client:
            from pao.app import create_app
            live=(await client.get('/openapi.json')).json()
            assert live==create_app().openapi()==json.loads((ROOT/'packages/contracts/openapi.json').read_text())
            seen=set();browser_fixture=None;workspaces=set()
            for member in await db.scalars(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True))):
                user=await db.get(User,member.user_id);token=issue_token(user.id,user.auth_version)
                headers={'Authorization':'Bearer '+token};workspaces.add(member.workspace_id)
                chat=await db.scalar(select(ChatSession).where(ChatSession.workspace_id==member.workspace_id,
                    ChatSession.user_id==user.id,ChatSession.archived_at.is_(None)).order_by(ChatSession.created_at.desc()).limit(1))
                if chat:
                    profile=await client.get('/v1/sessions/'+chat.id+'/chat',headers=headers)
                    assert profile.status_code==200, f'Owned chat GET status={profile.status_code}: {profile.text[:160]}'
                    from pao.modules.chat.policy import policy_for
                    expected=policy_for(chat)['token_mode']
                    assert profile.json()['policy']['token_mode']==expected
                    state.setdefault('served_chat_token_modes',{})[member.workspace_id]=expected
                personal_model=None;muse_models=[]
                for endpoint in ('/v1/installation-ai','/v1/engines'):
                    response=await client.get(endpoint,params={'workspace_id':member.workspace_id},headers=headers)
                    assert response.status_code==200 and response.headers['cache-control']=='no-store'
                    value=response.json();assert value['provider_calls'] is False
                    for item in value.get('resources',value.get('engines',[])):
                        if endpoint=='/v1/engines' and item.get('provider')=='muse':
                            assert item.get('installation_resource_id') and item.get('error') is None
                            from pao.modules.cli_connections.muse_resource import stamp
                            from pao.modules.cli_connections.muse_client import read_state
                            stamp()  # Metadata-only validation; never starts a native process.
                            muse_models=item['models']
                            assert muse_models==[v['model'] for v in read_state()['models']]
                            assert len(muse_models)>0
                            state.setdefault('muse_workspaces',{})[member.workspace_id]=muse_models
                        if item.get('personal_cli_source_id'):
                            from pao.modules.cli_connections.personal import config as personal_config
                            own=await personal_config(db,member.workspace_id,user.id)
                            assert item['personal_cli_source_id']==own['connection_id']
                            from pao.modules.cli_connections.model_catalog import public_catalog
                            metadata=await public_catalog(db,member.workspace_id,user.id,own['cli_pin'])
                            assert item['provider']=='codex_cli' and item['models']==(metadata['models'] if metadata else [own['model']])
                            assert item['personal_cli_source_version']==own['cli_pin']['source_version']
                            assert not item.get('installation_resource_id') and item['error'] is None
                            state['personal_codex_catalog_verified']=True
                            personal_model=own['model'] if own['model'] in item['models'] else item['models'][0]
                            state['personal_codex_models']=item['models']
                            continue
                        assert item['catalog_evidence']['revision']>=1
                        assert item['quota_evidence']['remaining'] is None
                        assert item['inference_evidence']['scope']=='caller_workspace'
                if chat is not None and user.id in cfg.installation_ai_manager_ids and (browser_fixture is None or personal_model):
                    browser_fixture={'token':token,'actor':user.id,'workspace':member.workspace_id,'folder':str(folder),
                                     'personal_model':personal_model,'personal_models':state.get('personal_codex_models',[]),
                                     'muse_models':muse_models}
                for rid,plan in await db.execute(text("SELECT r.id,r.execution_plan FROM runs r JOIN sessions s ON s.id=r.session_id WHERE r.workspace_id=:wid AND s.user_id=:uid AND r.status='completed'"),{'wid':member.workspace_id,'uid':user.id}):
                    saved=(plan or {}).get('skill_artifact')
                    if not saved or str(rid) in seen:continue
                    result=await client.get(f'/v1/runs/{rid}/skill-replay',headers=headers)
                    assert result.status_code==200 and result.json()['hash']==saved['hash'] and result.json()['tools_reexecuted'] is False
                    seen.add(str(rid));state['replays']+=1
                for aid,tid,saved in await db.execute(text('SELECT id,task_id,skill_artifact FROM task_attempts WHERE workspace_id=:wid AND skill_artifact IS NOT NULL'),{'wid':member.workspace_id}):
                    if str(aid) in seen:continue
                    result=await client.get(f'/v1/tasks/{tid}/attempts/{aid}/skill-replay',headers=headers)
                    assert result.status_code==200 and result.json()['hash']==saved['hash'] and result.json()['tools_reexecuted'] is False
                    seen.add(str(aid));state['replays']+=1
            assert state['replays']==len(archive['artifact_hashes'])==3
            assert len(workspaces)>=2 and browser_fixture
            assert (await client.get('/v1/installation-ai',params={'workspace_id':browser_fixture['workspace']})).status_code==401
        with (folder/'browser.log').open('wb') as log:
            subprocess.run(['node',str(ROOT/'scripts/gd01_installed_browser.cjs')],cwd=ROOT,
                env={**os.environ,'PAO_GD01_BROWSER':json.dumps(browser_fixture)},stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
        state.update(browser=json.loads((folder/'browser.json').read_text()),workspaces_checked=len(workspaces),
            source_env_pins_unchanged=source==digests(),primary_rows_unchanged=before==await signatures(url),
            schema=await primary_schema(),health=health(),binding=binding(),contract_source_live_stored_equal=True)
        state['pass']=state['source_env_pins_unchanged'] and state['primary_rows_unchanged'] and all(v==200 for v in state['health'].values())
    finally:
        state.update(source_env_pins_unchanged=source==digests(),primary_rows_unchanged=before==await signatures(url))
        await engine.dispose()
        with (folder/'receipt.json').open('x',encoding='utf-8') as output:json.dump(state,output,indent=2)
        print(json.dumps({'folder':str(folder),**state}))
    assert state['pass']


if __name__=='__main__':asyncio.run(main())
