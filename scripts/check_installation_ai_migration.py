"""Roundtrip 0075 on a restored private clone; primary is SELECT-only."""
import argparse,asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'apps/api'),str(ROOT/'scripts')]
from pao.config import settings
from check_m2_restore import inspect,CONTAINER
from pao.modules.operations.checkpoint import digest


async def signatures(url):
    engine=create_async_engine(url,connect_args={'server_settings':{'default_transaction_read_only':'on','statement_timeout':'20000'}})
    try:
        async with engine.connect() as db:
            names=list(await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))
            return {name:await db.scalar(text('SELECT md5(COALESCE(string_agg(row_json,\'\' ORDER BY row_json),\'\')) FROM (SELECT row_to_json(t)::text AS row_json FROM "'+name.replace('"','""')+'" t) AS rows')) for name in names}
    finally:await engine.dispose()


def docker(*args,**kwargs):
    return subprocess.run(['docker','exec',*args],check=True,timeout=90,**kwargs)


async def main(args):
    assert ROOT==Path('F:/PAO-ACOS')
    url=make_url(settings().database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    manifest_path=(args.manifest or ROOT/'.runtime/checkpoints/p0-20261020T100457-f4a9247b/manifest.json').resolve(strict=True)
    assert manifest_path.is_relative_to(ROOT/'.runtime/checkpoints') and not manifest_path.is_symlink()
    manifest=json.loads(manifest_path.read_text())
    previous,target_revision=('0075','0077') if args.codex_models else ('0074','0075')
    assert not args.codex_models or args.manifest,'Fresh explicit checkpoint required'
    backup=Path(manifest['database']['backup']).resolve()
    assert backup.is_relative_to(ROOT/'.runtime') and digest(backup)==manifest['database']['sha256']
    folder=ROOT/'.runtime'/(('codex-models-migration-' if args.codex_models else 'installation-ai-migration-')+uuid4().hex);folder.mkdir()
    clone='pao_rai_restore_'+uuid4().hex
    before=await signatures(url);created=False
    state={'pass':False,'primary_migrated':False,'provider_calls':0,'clone':clone}
    try:
        docker(CONTAINER,'createdb','-U','pao',clone);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',clone,'--no-owner','--exit-on-error',stdin=source,capture_output=True)
        target=url.set(database=clone)
        old=await signatures(target);archives=await inspect(target)
        assert archives['revision']==previous
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False),'PYTHONDONTWRITEBYTECODE':'1'}
        for index,command in enumerate((('upgrade',target_revision),('downgrade',previous),('upgrade',target_revision))):
            with (folder/(str(index)+'-migration.log')).open('wb') as log:
                subprocess.run([sys.executable,'-B','-m','alembic',*command],cwd=ROOT,env=env,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=90)
            current=await signatures(target)
            assert all(current.get(name)==hashed for name,hashed in old.items() if name!='alembic_version')
            assert len(current)==len(old)+(2 if target_revision=='0075' and command[1]=='0075' else 0)
            restored=await inspect(target)
            assert restored['artifact_hashes']==archives['artifact_hashes']
            assert restored['revision']==command[1]
        state.update(pass_roundtrip=True,old_tables_unchanged=True,archive_count=len(archives['artifact_hashes']),previous=previous,target=target_revision,pass_=True)
        state['pass']=True
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',clone);state['owned_clone_removed']=True
        state['primary_unchanged']=before==await signatures(url)
        state['pass']=state['pass'] and state['primary_unchanged']
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**state}))
    assert state['pass']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--codex-models',action='store_true');parser.add_argument('--manifest',type=Path)
    asyncio.run(main(parser.parse_args()))
