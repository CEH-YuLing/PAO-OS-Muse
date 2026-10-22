"""S5 candidate migration only on a fresh owned clone, never the primary."""
import asyncio,json,os,re,subprocess,sys
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import BusinessProfile,BusinessProfileVersion,BusinessRoutingVersion,BusinessPlanEvent
from pao.modules.business_planning.contracts import ProfileContent,digest
from pao.modules.business_planning.routing_contracts import RoutingContent
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0065'
    before,shape=await snapshot(url),await schema(url)
    name='pao_s5_migration_'+uuid4().hex;assert re.fullmatch('pao_s5_migration_[0-9a-f]{32}',name)
    backup=ROOT/'.runtime'/('s5-migration-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(action,rev):subprocess.run([sys.executable,'-m','alembic',action,rev],cwd=ROOT,env=env,check=True,timeout=120)
        for action,rev in (('upgrade','0070'),('downgrade','0065'),('upgrade','0070')):
            migrate(action,rev)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if action=='downgrade':assert await snapshot(target)==before and await schema(target)==shape
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        engine=create_async_engine(target);session=async_sessionmaker(engine,expire_on_commit=False)
        try:
            async with session.begin() as db:
                wid=await db.scalar(text('SELECT id::text FROM workspaces ORDER BY id LIMIT 1'))
                actor=await db.scalar(text('SELECT id::text FROM users ORDER BY id LIMIT 1'));assert wid and actor
                profile=BusinessProfile(workspace_id=wid,scope_key='enterprise',revision=1);db.add(profile);await db.flush()
                content=ProfileContent(currency='VND',timezone='Asia/Ho_Chi_Minh').model_dump(mode='json')
                db.add(BusinessProfileVersion(workspace_id=wid,profile_id=profile.id,revision=1,request_key=str(uuid4()),actor_id=actor,content=content,content_hash=digest(content)))
                routing=RoutingContent.model_validate({'targets':[{'key':'local','provider':'ollama','model':'fixture-only'}],
                    'default_target':'local'}).model_dump(mode='json',exclude_none=True)
                db.add(BusinessRoutingVersion(workspace_id=wid,revision=1,actor_id=actor,request_key=str(uuid4()),content=routing,content_hash=digest(routing)))
                data={'stopped':True};value={'subject_kind':'control','subject_id':wid,'action':'control','data':data}
                db.add(BusinessPlanEvent(workspace_id=wid,actor_id=actor,request_key=str(uuid4()),subject_kind='control',subject_id=wid,action='control',data=data,fingerprint=digest(value),content_hash=digest(value)))
            populated,definitions=await snapshot(target),await schema(target)
            refusal=subprocess.run([sys.executable,'-m','alembic','downgrade','0065'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refusal.returncode and 'Populated business operations' in refusal.stderr
            assert await revision(target)=='0070' and await snapshot(target)==populated and await schema(target)==definitions
        finally:await engine.dispose()
        assert await revision(url)=='0065' and await snapshot(url)==before and await schema(url)==shape
        result={'pass':True,'roundtrip':'0065->0070->0065->0070','old_tables_exact':True,'rollback_schema_exact':True,
            'populated_downgrade_refused':True,'primary_unchanged':True,'provider_calls':False,'backup':str(backup)}
        (ROOT/'.runtime/s5-migration.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only owned S5 migration clone; backup retained.')


if __name__=='__main__':asyncio.run(main())
