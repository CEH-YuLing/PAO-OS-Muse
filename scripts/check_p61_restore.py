"""Restore only own P6.1 test fixture clone and verify every business row hash."""
import asyncio,json
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER
async def inspect(url):
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:
            assert await db.scalar(text("SELECT count(*) FROM tasks WHERE status='draft'"))==2
            assert await db.scalar(text('SELECT count(*) FROM task_dependencies'))==1
            for table in ('task_attempts','runs','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
            plan=await db.scalar(text("SELECT data FROM studio_events WHERE action='p61_plan_created'"))
            value=plan['snapshot'];assert value['sha256']==digest({k:v for k,v in value.items() if k!='sha256'})
    finally:await engine.dispose()
async def main():
    url=make_url(settings().database_url);assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');await inspect(source);columns,before=await snapshot(source)
    name='pao_p61_restore_'+uuid4().hex;backup=ROOT/'.runtime'/('p61-fixture-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);assert (await snapshot(target,columns))[1]==before;await inspect(target)
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'tables':len(columns),'all_hashes_unchanged':True,'planned_tasks':2,'model_calls':0}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
