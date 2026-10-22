"""Restore synthetic engine browser fixtures and verify snapshots/all row hashes."""
import asyncio,json
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from pao.modules.engines.service import checked_snapshot
from check_p11_migration import docker,snapshot,CONTAINER
async def inspect(url):
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) in ('0031','0032')
            rows=list(await db.execute(text('SELECT status,engine_snapshot FROM runs')))
            assert len(rows)==2 and {status for status,_ in rows}=={'completed','cancelled'}
            for _,value in rows:checked_snapshot(value)
            assert await db.scalar(text("SELECT count(*) FROM sessions WHERE engine_config IS NOT NULL"))==1
            return {'runs':2,'session_pins':1}
    finally:await engine.dispose()
async def main():
    url=make_url(settings().database_url);assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');columns,before=await snapshot(source);counts=await inspect(source)
    name='pao_p31_bytes_'+uuid4().hex;backup=ROOT/'.runtime'/('p31-browser-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);assert (await snapshot(target,columns))[1]==before and await inspect(target)==counts
        print(json.dumps({'pass':True,'tables':len(columns),'counts':counts,'all_hashes_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
