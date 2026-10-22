"""UI-only checkpoint. Never create credentials, grants or model jobs."""
import argparse,asyncio,json,shutil,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.modules.operations.checkpoint import entries,digest
from pao.config import settings
from check_p84_foundation import health,binding
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
FILES=('apps/web/components/workspace/ConnectionGrantPanel.tsx','apps/web/components/workspace/ClientModelSettings.tsx')

def protected():
    return {**{k:v for k,v in entries(ROOT).items() if k.startswith(('apps/api/','packages/cli-runtime/','packages/contracts/')) or k in ('requirements.lock','pyproject.toml','package.json','package-lock.json')},'.env':digest(ROOT/'.env'),'.runtime/cli-device.json':digest(ROOT/'.runtime/cli-device.json'),'.runtime/acos-python-runtime.json':digest(ROOT/'.runtime/acos-python-runtime.json')}

async def observation():
    cfg=settings();url=make_url(cfg.database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    dbengine=create_async_engine(url,connect_args={'server_settings':{'default_transaction_read_only':'on','statement_timeout':'5000'}})
    try:
        async with dbengine.connect() as db:
            assert await db.scalar(text('SHOW transaction_read_only'))=='on'
            revision=await db.scalar(text('SELECT version_num FROM alembic_version'))
            profile=dict((await db.execute(text("SELECT status,version,model,auth_checked_at IS NOT NULL AS auth_recorded,setup_operation_id IS NOT NULL AS operation_pending FROM cli_model_connections WHERE id='398aa03c-0465-426c-ad95-12d1d1cc475d' AND workspace_id='ef221310-5afc-4c21-9f9e-4aa9bf4b3e79' AND owner_id='165b1fa6-f443-4f66-bddb-51eb5b6e6fa5'"))).mappings().one())
            counts=dict((await db.execute(text("SELECT (SELECT count(*) FROM tenant_connection_references WHERE kind='cli_model') AS cli_references,(SELECT count(*) FROM cli_model_dispatches) AS cli_dispatches"))).mappings().one())
            return {'revision':revision,'profile_metadata':profile,'native_counts':counts,'flags':{k:getattr(cfg,k) for k in ('cli_connections_enabled','cli_browser_login_enabled','engine_contract_enabled')},'read_only':True}
    finally:await dbengine.dispose()

def main(args):
    assert ROOT==Path('F:/PAO-ACOS')
    if args.action=='prepare':
        folder=ROOT/'.runtime'/('codex-access-ui-'+uuid4().hex);folder.mkdir()
        for name in FILES:
            target=folder/'before'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        value={'protected':protected(),'files':{name:digest(ROOT/name) for name in FILES},'binding':binding(),'observation':asyncio.run(observation())}
        (folder/'before.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),'observation':value['observation'],'source_only_checkpoint':True}));return
    folder=args.folder.resolve();assert folder.parent==ROOT/'.runtime' and folder.name.startswith('codex-access-ui-') and not folder.is_symlink()
    before=json.loads((folder/'before.json').read_text())
    assert protected()==before['protected'] and binding()==before['binding']
    proof={}
    for item in args.proof:
        assert item.resolve().is_relative_to(ROOT/'.runtime')
        value=json.loads(item.read_text());assert value['pass'] is True
        if 'stages' in value:
            assert value['stages']==['node','typegen','typecheck','build'] and value['frontend_unchanged_during_build']
            for name in FILES:assert digest(Path(value['source'])/name)==digest(ROOT/name)
        else:
            assert value['fixture_only']
            assert value.get('real_provider_calls',value.get('external_provider_calls'))==0
            assert value.get('backend_forwarded',value.get('backend_requests_forwarded'))==0
        proof[str(item)]=value
    assert len(proof)>=4
    current=asyncio.run(observation());statuses=health();assert current['revision']=='0072' and all(v==200 for v in statuses.values())
    result={'pass':True,'UI_only':True,'backend_env_runtime_unchanged':True,'binding':before['binding'],'schema':'0072','health':statuses,'before_observation':before['observation'],'after_observation':current,'files':{name:digest(ROOT/name) for name in FILES},'proof_paths':list(proof),'real_model_job_tested':False,'real_grant_created_by_agent':False,'primary_data_frozen_claim':False,'production_accepted':False}
    (folder/'receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'folder':str(folder),**result}))
    (ROOT/'.runtime/codex-access-current-status.json').write_text(json.dumps({'state':'model_access_UI_local_accepted_owner_activation_required','receipt':str(folder/'receipt.json'),'backend_unchanged':True,'native_job_tested':False,'phase_C_complete':False},indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','verify']);parser.add_argument('--folder',type=Path);parser.add_argument('--proof',type=Path,action='append',default=[]);main(parser.parse_args())
