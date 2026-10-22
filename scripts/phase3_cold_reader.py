"""Operator-only read of a disposable restored clone. Never resume archived work."""
import asyncio,json,os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from pao.skills import execution_binding,require_snapshot_execution,SkillVersionMismatch
from pao.skill_artifacts import read_artifact

async def main():
    engine=create_async_engine(os.environ['DATABASE_URL'])
    hashes=[];denied=0
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SHOW transaction_read_only'))=='on'
            role=(await db.execute(text('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user'))).one()
            assert not any(role)
            assert not await db.scalar(text("SELECT pg_has_role(current_user,'pao_cold_admin','MEMBER')"))
            assert not await db.scalar(text("SELECT has_table_privilege(current_user,'users','INSERT')"))
            assert not await db.scalar(text("SELECT has_schema_privilege(current_user,'public','CREATE')"))
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0071'
            tables=await db.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'"))
            assert tables==153
            items=[]
            for rid,wid,plan,response in await db.execute(text("SELECT id,workspace_id,execution_plan,response FROM runs WHERE status='completed'")):
                artifact=(plan or {}).get('skill_artifact')
                if artifact:items.append(('run',str(rid),str(wid),artifact,response))
            for aid,wid,artifact in await db.execute(text('SELECT id,workspace_id,skill_artifact FROM task_attempts WHERE skill_artifact IS NOT NULL')):
                items.append(('attempt',str(aid),str(wid),artifact,None))
            assert len(items)==3
            for kind,ident,wid,artifact,response in items:
                value=read_artifact(artifact,kind,ident,wid)
                assert value.read_only and not value.tools_reexecuted
                if response is not None:assert value.response==response
                hashes.append(value.hash)
                try:read_artifact(artifact,kind,ident,'wrong-workspace')
                except ValueError:pass
                else:raise AssertionError('archive_scope_gate_missing')
                corrupt={**artifact,'hash':'0'*64}
                try:read_artifact(corrupt,kind,ident,wid)
                except ValueError:pass
                else:raise AssertionError('archive_hash_gate_missing')
                if value.skill_snapshot['execution_binding']!=execution_binding():
                    try:require_snapshot_execution(value.skill_snapshot)
                    except SkillVersionMismatch:denied+=1
                    else:raise AssertionError('old_execution_binding_was_bypassed')
            assert denied==3,'Fixture expects all three historical execution bindings to differ'
            # Read-only role and transaction must still be active after all parsing.
            assert await db.scalar(text('SHOW transaction_read_only'))=='on'
        print(json.dumps({'pass':True,'tables':tables,'archive_hashes':sorted(hashes),'archives_read':3,
            'incompatible_execution_denied':denied,'tools_reexecuted':False,
            'candidate_binding':execution_binding(),'full_production_restore_accepted':False}))
    finally:await engine.dispose()

if __name__=='__main__':asyncio.run(main())
