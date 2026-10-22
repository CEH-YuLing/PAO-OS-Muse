"""Restore ACOS to a NEW isolated database; verify additive migration and rollback.

Never migrate/drop the source DB; drop only the generated DB created here.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT, settings

CONTAINER = 'pao-acos-local-postgres-1'


def docker(*args, **kwargs):
    subprocess.run(['docker','exec',*args], check=True, **kwargs)


async def snapshot(url, columns=None):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            if columns is None:
                columns = {}
                for table, column in await db.execute(text("""SELECT table_name,column_name
                    FROM information_schema.columns WHERE table_schema='public'
                    AND table_name != 'alembic_version' ORDER BY table_name,ordinal_position""")):
                    columns.setdefault(table,[]).append(column)
            hashes = {}
            for table, fields in columns.items():
                quoted = lambda name: '"' + name.replace('"','""') + '"'
                sql = 'SELECT row_to_json(t)::text FROM (SELECT '+','.join(map(quoted,fields))+' FROM '+quoted(table)+') t'
                rows = sorted(await db.scalars(text(sql)))
                hashes[table] = {'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
            return columns, hashes
    finally:
        await engine.dispose()


async def validate_mapping(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            revision = await db.scalar(text('SELECT version_num FROM alembic_version'))
            assert revision == '0025'
            assert await db.scalar(text("""SELECT count(*) FROM sessions s LEFT JOIN brains b ON b.id=s.brain_id
                WHERE b.id IS NULL OR NOT b.legacy_default OR b.workspace_id<>s.workspace_id
                OR b.owner_id<>s.user_id OR b.brand_id IS DISTINCT FROM s.brand_id""")) == 0
            assert await db.scalar(text('SELECT count(*) FROM brain_members')) == 0
            assert await db.scalar(text('SELECT count(*) FROM runs WHERE brain_id IS NOT NULL OR brain_revision IS NOT NULL OR brain_context IS NOT NULL')) == 0
            count = await db.scalar(text('SELECT count(*) FROM brains'))
            return count
    finally:
        await engine.dispose()


async def main():
    url = make_url(settings().database_url)
    if ROOT.resolve() != Path('F:/PAO-ACOS') or url.database != 'pao_acos_local' or url.port != 15432 or url.host != '127.0.0.1':
        raise SystemExit('Only the isolated ACOS source is allowed')
    engine = create_async_engine(url)
    async with engine.connect() as db:
        assert await db.scalar(text('SELECT version_num FROM alembic_version')) == '0024'
    await engine.dispose()
    name = 'pao_p11_restore_' + uuid4().hex
    backup = ROOT/'.runtime'/('p11-pre-'+uuid4().hex+'.dump')
    with backup.open('xb') as output:
        docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=output)
    created = False
    try:
        docker(CONTAINER,'createdb','-U','pao',name); created = True
        with backup.open('rb') as source:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target = url.set(database=name)
        columns, before = await snapshot(target)
        env = {**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(*args):
            subprocess.run([sys.executable,'-m','alembic',*args],env=env,cwd=ROOT,check=True)
        migrate('upgrade','0025')
        assert (await snapshot(target,columns))[1] == before, 'Legacy rows changed on upgrade'
        brain_count = await validate_mapping(target)
        migrate('check')
        migrate('downgrade','0024')
        assert await snapshot(target) == (columns,before), 'Rollback changed original schema/rows'
        migrate('upgrade','0025')
        assert (await snapshot(target,columns))[1] == before
        assert await validate_mapping(target) == brain_count
        print(json.dumps({'pass':True,'upgrade':'0024->0025','rollback':'0025->0024',
            'legacy_tables':len(columns),'mapped_brains':brain_count,'source_database_changed':False,
            'backup':str(backup)}))
    finally:
        if created:
            docker(CONTAINER,'dropdb','-U','pao',name)


if __name__ == '__main__':
    asyncio.run(main())
