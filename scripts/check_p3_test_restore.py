"""Restore every synthetic table byte hash including compaction/ledger/retry."""
import asyncio,json
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from check_p11_migration import docker,snapshot,CONTAINER
async def inspect(url):
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) in ('0032','0033','0034')
            assert await db.scalar(text("SELECT count(*) FROM runs WHERE status='completed'"))==5
            assert await db.scalar(text('SELECT count(*) FROM runs WHERE parent_run_id IS NOT NULL'))==1
            assert await db.scalar(text('SELECT count(*) FROM chat_compactions'))==1
            assert await db.scalar(text('SELECT count(*) FROM llm_attempts'))==10
            assert await db.scalar(text("SELECT count(*) FROM llm_attempts WHERE usage_state='reported'"))==5
    finally:await engine.dispose()
async def main():
    url=make_url(settings().database_url);assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');await inspect(source);columns,before=await snapshot(source)
    name='pao_p3_bytes_'+uuid4().hex;backup=ROOT/'.runtime'/('p3-browser-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);assert (await snapshot(target,columns))[1]==before;await inspect(target)
        print(json.dumps({'pass':True,'tables':len(columns),'all_hashes_unchanged':True,'ledger':10,'compactions':1,'retries':1,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
