"""Verify all P2 fixture rows and content hashes after full DB restore."""
import asyncio,hashlib,json
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
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) in ('0030','0031','0032','0033','0034')
            for table,body,sha in [('knowledge_ingestion_jobs','parsed_text','parsed_sha256'),('knowledge_chunks','content','sha256'),('knowledge_wiki_versions','content','sha256')]:
                rows=list(await db.execute(text(f'SELECT {body},{sha} FROM {table} WHERE {body} IS NOT NULL')));assert rows,table
                for value,digest in rows:assert hashlib.sha256(value.encode()).hexdigest()==digest
            counts={table:await db.scalar(text('SELECT count(*) FROM '+table)) for table in ['knowledge_chunks','knowledge_wiki_versions','knowledge_wiki_events','session_attachments','run_knowledge']}
            assert all(counts.values());return counts
    finally:await engine.dispose()
async def main():
    url=make_url(settings().database_url);assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');columns,before=await snapshot(source);counts=await inspect(source)
    name='pao_p2_bytes_'+uuid4().hex;backup=ROOT/'.runtime'/('p2-browser-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);assert (await snapshot(target,columns))[1]==before and await inspect(target)==counts
        print(json.dumps({'pass':True,'tables':len(columns),'counts':counts,'hashes_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
