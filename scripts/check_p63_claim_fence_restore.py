"""Restore a lost-projection fixture; never probe the primary database.

Seed test_missing_attempt_never_erases_immutable_claim[recover-True].
No claims/jobs/providers are started; only isolated recover/fail_pending refuse.
"""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, text, func
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.exc import DBAPIError

from pao.config import ROOT, settings
from pao.models import StudioExecution, StudioEvent, TaskAttempt
from pao.modules.studio import step_jobs as jobs
from check_p11_migration import docker, snapshot, CONTAINER


async def inspect(url, probe=False):
    assert url.database == 'pao_test' or url.database.startswith('pao_p63_claim_fence_restore_')
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) == '0041'
            rows = list(await db.scalars(select(StudioExecution)))
            assert len(rows) == 1
            row = rows[0]
            assert row.status == 'running' and row.cancel_requested is True
            first = row.command['steps'][0]
            ident = first['execution_id']
            assert await db.scalar(select(func.count(TaskAttempt.id))) == 0
            assert await db.get(StudioEvent, jobs.event_id(ident, 'claimed')) is not None
            assert await db.get(StudioEvent, jobs.event_id(ident, 'outcome')) is None
        if probe:
            # This process has no concurrent tasks. Route only these explicit
            # native helper calls to the owned clone, then restore the binding.
            original = jobs.Session
            jobs.Session = factory
            try:
                for helper in (jobs.recover, jobs.fail_pending):
                    for _ in range(2):
                        try:
                            await helper(row.id, first['step_id'], ident)
                        except HTTPException as error:
                            assert error.status_code == 409
                            assert error.detail == 'durable_step_projection_invalid'
                        else:
                            raise AssertionError('Restored immutable claim fence missing')
            finally:
                jobs.Session = original
            try:
                async with engine.begin() as db:
                    await db.execute(text("UPDATE studio_events SET data='{}'::json WHERE id=:id"),
                                     {'id': jobs.event_id(ident, 'claimed')})
            except DBAPIError:
                pass
            else:
                raise AssertionError('Restored immutable claim trigger missing')
    finally:
        await engine.dispose()


async def main():
    url = make_url(settings().database_url)
    assert ROOT.resolve() == Path('F:/PAO-ACOS')
    assert url.database == 'pao_acos_local' and url.host == '127.0.0.1' and url.port == 15432
    source = url.set(database='pao_test')
    columns, before = await snapshot(source)
    await inspect(source)
    assert (await snapshot(source, columns))[1] == before
    name = 'pao_p63_claim_fence_restore_' + uuid4().hex
    dump = ROOT / '.runtime' / ('p63-claim-fence-' + uuid4().hex + '.dump')
    with dump.open('xb') as output:
        docker(CONTAINER, 'pg_dump', '-U', 'pao', '-d', 'pao_test', '-Fc', stdout=output)
    created = False
    try:
        docker(CONTAINER, 'createdb', '-U', 'pao', name)
        created = True
        with dump.open('rb') as data:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', name,
                   '--no-owner', '--exit-on-error', stdin=data)
        target = url.set(database=name)
        assert (await snapshot(target, columns))[1] == before
        await inspect(target, True)
        assert (await snapshot(target, columns))[1] == before
        assert (await snapshot(source, columns))[1] == before
        print(json.dumps({'pass': True, 'tables': len(columns), 'hash_exact': True,
                          'immutable_claim_verified': True, 'missing_attempt_preserved': True,
                          'recover_and_fail_pending_rejected': True, 'replacement_attempts': 0,
                          'false_no_effect_outcomes': 0, 'model_calls': 0, 'queue_jobs': 0}))
    finally:
        if created:
            docker(CONTAINER, 'dropdb', '-U', 'pao', name)


if __name__ == '__main__':
    asyncio.run(main())
