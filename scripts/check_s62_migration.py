"""Owned-clone lifecycle migration/roundtrip and populated restore. No primary writes."""
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT, settings
from pao.models import now
from pao.modules.operations.checkpoint import digest
from check_p11_migration import snapshot

CONTAINER='pao-acos-local-postgres-1'
NEW={'workspace_invitations','login_sessions','lifecycle_audits','data_lifecycle_requests'}


def docker(*args, **kwargs):
    return subprocess.run(['docker','exec',*args],check=True,timeout=120,**kwargs)


async def query(url, statement, values=None):
    engine=create_async_engine(url)
    try:
        async with engine.begin() as db:
            return await db.execute(text(statement), values or {})
    finally:
        await engine.dispose()


def migration(url, direction, revision):
    env={**os.environ,'DATABASE_URL':url.render_as_string(hide_password=False)}
    subprocess.run([sys.executable,'-m','alembic',direction,revision],cwd=ROOT,env=env,check=True)


async def main():
    config=settings();url=make_url(config.database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert not config.channel_retention_enabled
    env_hash=digest(ROOT/'.env')
    primary=await snapshot(url)
    assert (await query(url,'SELECT version_num FROM alembic_version')).scalar_one()=='0070'
    folder=ROOT/'.runtime'/('s62-migration-'+uuid4().hex);folder.mkdir()
    dump=folder/'before.dump'
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=output)
    names=['pao_s62_migration_'+uuid4().hex,'pao_s62_restore_'+uuid4().hex]
    created=[]
    try:
        for name in names:
            assert re.fullmatch('pao_s62_(migration|restore)_[a-f0-9]{32}',name)
            docker(CONTAINER,'createdb','-U','pao',name);created.append(name)
        clone=url.set(database=names[0]);restored=url.set(database=names[1])
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',names[0],'--no-owner','--exit-on-error',stdin=data)
        assert await snapshot(clone)==primary
        migration(clone,'upgrade','0071')
        after=await snapshot(clone)
        assert set(after[0])-set(primary[0])==NEW
        assert (await snapshot(clone,primary[0]))[1]==primary[1]
        migration(clone,'downgrade','0070')
        assert await snapshot(clone)==primary
        migration(clone,'upgrade','0071')
        user=(await query(clone,'SELECT id FROM users ORDER BY id LIMIT 1')).scalar_one()
        workspace=(await query(clone,'SELECT workspace_id FROM workspace_members WHERE user_id=:uid LIMIT 1',{'uid':user})).scalar_one()
        await query(clone,"INSERT INTO lifecycle_audits(id,created_at,workspace_id,actor_id,action,subject_id,details) VALUES(:id,:at,:wid,:uid,'restore.synthetic',:uid,'{}')",
                    {'id':uuid4(),'at':now(),'wid':workspace,'uid':user})
        await query(clone,"INSERT INTO login_sessions(id,created_at,user_id,token_hash,auth_version,expires_at,revoked) VALUES(:id,:at,:uid,:hash,0,:expires,true)",
                    {'id':uuid4(),'at':now(),'uid':user,'hash':'1'*64,'expires':now()+timedelta(minutes=5)})
        for sql in ('UPDATE lifecycle_audits SET action=\'changed\'','DELETE FROM lifecycle_audits'):
            try:await query(clone,sql)
            except DBAPIError:pass
            else:raise AssertionError('Audit mutation was allowed')
        failure=subprocess.run([sys.executable,'-m','alembic','downgrade','0070'],cwd=ROOT,
            env={**os.environ,'DATABASE_URL':clone.render_as_string(hide_password=False)},capture_output=True)
        assert failure.returncode!=0
        assert (await query(clone,'SELECT version_num FROM alembic_version')).scalar_one()=='0071'
        populated=await snapshot(clone)
        saved=folder/'populated.dump'
        with saved.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d',names[0],'-Fc',stdout=output)
        with saved.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',names[1],'--no-owner','--exit-on-error',stdin=data)
        assert await snapshot(restored)==populated
        try:await query(restored,'DELETE FROM lifecycle_audits')
        except DBAPIError:pass
        else:raise AssertionError('Restored audit trigger missing')
        assert await snapshot(url)==primary and digest(ROOT/'.env')==env_hash
        result={'pass':True,'roundtrip':'0070-0071-0070-0071','old_columns_exact':True,
                'populated_restore_exact':True,'audit_immutable_after_restore':True,
                'populated_downgrade_refused':True,'primary_unchanged':True,'env_unchanged':True}
        (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({**result,'evidence':str(folder)}))
    finally:
        for name in reversed(created):
            assert re.fullmatch('pao_s62_(migration|restore)_[a-f0-9]{32}',name)
            docker(CONTAINER,'dropdb','-U','pao',name)
        print('Removed only generated S6.2 clone databases; retained private backups.')


if __name__=='__main__':asyncio.run(main())
