"""Owned0057->0058 clone; preserve old bytes and refuse populated rollback."""
import asyncio,json,os,subprocess,sys,hashlib
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,Brain,BrainFile,KnowledgeSource,KnowledgeVersion,KnowledgeIndexJob
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema

async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0057'
    before,definitions=await snapshot(url),await schema(url)
    name='pao_knowledge_embedding_'+uuid4().hex
    backup=ROOT/'.runtime'/('knowledge-embedding-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for command,rev in (('upgrade','0058'),('downgrade','0057'),('upgrade','0058')):
            subprocess.run([sys.executable,'-m','alembic',command,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if command=='downgrade':assert await schema(target)==definitions and await snapshot(target)==before
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        local=create_async_engine(target);sessions=async_sessionmaker(local)
        try:
            async with sessions.begin() as db:
                actor=User(email=uuid4().hex+'@example.test',password_hash='fixture-no-login')
                space=Workspace(name='Knowledge owned clone');db.add_all([actor,space]);await db.flush()
                brain=Brain(workspace_id=space.id,owner_id=actor.id,name='Clone private');db.add(brain);await db.flush()
                raw=b'Fixture source';sha=hashlib.sha256(raw).hexdigest()
                file=BrainFile(workspace_id=space.id,brain_id=brain.id,created_by=actor.id,name='fixture.txt',
                    mime='text/plain',size=len(raw),sha256=sha,content=raw);db.add(file);await db.flush()
                source=KnowledgeSource(workspace_id=space.id,brain_id=brain.id,file_id=file.id,created_by=actor.id,title='Fixture');db.add(source);await db.flush()
                value=KnowledgeVersion(workspace_id=space.id,brain_id=brain.id,source_id=source.id,number=1,
                    origin_version=1,source_sha256=sha,source_size=len(raw),title='Fixture',created_by=actor.id);db.add(value);await db.flush()
                db.add(KnowledgeIndexJob(workspace_id=space.id,brain_id=brain.id,version_id=value.id,
                    actor_id=actor.id,chunker_version='chars1800-v1',embedding_model='fixture',
                    embedding_engine={'version':1,'model':'fixture','url':'http://127.0.0.1:11434'}))
            populated,shape=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0057'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode!=0 and 'Knowledge embedding pins must be preserved' in refused.stderr
            assert await snapshot(target)==populated and await schema(target)==shape and await revision(target)=='0058'
        finally:await local.dispose()
        assert await snapshot(url)==before and await schema(url)==definitions and await revision(url)=='0057'
        print(json.dumps({'pass':True,'up_down_up':'0057->0058->0057->0058','old_rows_exact':True,
            'rollback_schema_equivalent':True,'populated_downgrade_refused':True,'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned clone; retained dump.')

if __name__=='__main__':asyncio.run(main())
