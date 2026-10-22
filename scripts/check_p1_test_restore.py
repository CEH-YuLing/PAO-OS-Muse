"""Restore real browser-created KB fixtures from pao_test, hash all rows/bytes.
Run after browser acceptance, never during regression. No local data mutation.
"""
import asyncio,hashlib,json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from check_p11_migration import docker,snapshot,CONTAINER

async def inspect_bytes(url):
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) in ('0028','0029','0030','0031')
            files=list(await db.execute(text('SELECT content,sha256,size FROM brain_files')))
            versions=list(await db.execute(text('SELECT content,sha256,size FROM brain_note_versions')))
            assert len(files)>=2 and len(versions)>=3,'Browser fixtures missing; do not call during regression'
            for content,sha,size in files:
                assert len(content)==size and hashlib.sha256(content).hexdigest()==sha
            for content,sha,size in versions:
                raw=content.encode();assert len(raw)==size and hashlib.sha256(raw).hexdigest()==sha
            return {'files':len(files),'note_versions':len(versions)}
    finally:await engine.dispose()

async def main():
    local=make_url(settings().database_url)
    if ROOT.resolve()!=Path('F:/PAO-ACOS') or local.database!='pao_acos_local' or local.host!='127.0.0.1' or local.port!=15432:
        raise SystemExit('ACOS runner only')
    source=local.set(database='pao_test');columns,before=await snapshot(source);bytes_before=await inspect_bytes(source)
    name='pao_p1_bytes_'+uuid4().hex;backup=ROOT/'.runtime'/('p1-test-bytes-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=local.set(database=name)
        assert (await snapshot(target,columns))[1]==before
        assert await inspect_bytes(target)==bytes_before
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'all_row_hashes_unchanged':True,'tables':len(columns),**bytes_before,
            'file_note_bytes_verified':True,'local_data_changed':False,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
