"""Byte/hash verification of real Sources browser fixtures after backup restore."""
import asyncio,hashlib,json
from pathlib import Path
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
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) in ('0029','0030','0031')
            jobs=list(await db.execute(text("SELECT parsed_text,parsed_sha256,status FROM knowledge_ingestion_jobs")))
            assert len(jobs)==3 and all(status=='completed' for _,_,status in jobs)
            for content,sha,_ in jobs:assert hashlib.sha256(content.encode()).hexdigest()==sha
            assert await db.scalar(text('SELECT count(*) FROM knowledge_sources'))==2
            assert await db.scalar(text('SELECT count(*) FROM knowledge_versions'))==3
            return {'sources':2,'source_versions':3,'completed_parse_jobs':3}
    finally:await engine.dispose()

async def main():
    url=make_url(settings().database_url)
    if ROOT.resolve()!=Path('F:/PAO-ACOS') or url.database!='pao_acos_local' or url.host!='127.0.0.1' or url.port!=15432:
        raise SystemExit('ACOS runner only')
    source=url.set(database='pao_test');columns,before=await snapshot(source);values=await inspect(source)
    name='pao_p21_bytes_'+uuid4().hex;backup=ROOT/'.runtime'/('p21-browser-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);assert (await snapshot(target,columns))[1]==before
        assert await inspect(target)==values
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'tables':len(columns),**values,'all_row_hashes_unchanged':True,
            'parsed_bytes_verified':True,'local_data_changed':False,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
