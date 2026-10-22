"""Serial tests and GET-only installed acceptance for eight local switches.

Never changes .env, credentials, application source or primary schema.
The prepare subcommand may stop ONLY verified idle API/worker for config reload.
"""
import argparse
import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/api'), str(ROOT / 'scripts'), str(ROOT / 'packages/cli-runtime')]
from local_feature_activation import ENABLE, KEEP_OFF, flags, non_feature_hash, verify_local, source_manifest
from check_p84_foundation import binding, protected, primary_schema, health
from check_installation_ai_migration import signatures
from check_m2_restore import inspect
from local_cycle_test_lock import isolated_test_slot
from pao.config import settings
from pao.modules.operations.checkpoint import digest
from sqlalchemy.engine import make_url


def write(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)


def location(raw):
    path = Path(raw).resolve()
    assert path.is_relative_to(ROOT / '.runtime')
    assert not any(p.is_symlink() or p.is_junction() for p in (path, *path.parents))
    return path


def test():
    cfg = settings()
    verify_local(cfg)
    url = make_url(cfg.database_url)
    folder = ROOT / '.runtime' / ('local-feature-tests-' + uuid4().hex)
    folder.mkdir()
    before = asyncio.run(signatures(url))
    source = protected()
    state = {'pass': False, 'provider_calls': 0, 'rows_before': before, 'source_before': source}
    pg = urlsplit(cfg.database_url)
    env = {**os.environ, 'DATABASE_URL': urlunsplit(pg._replace(path='/pao_test')),
        'PAO_TEST_DATABASE_URL': urlunsplit(pg._replace(path='/pao_test')),
        'REDIS_URL': urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
        'JWT_SECRET': 'synthetic-local-' + secrets.token_hex(24),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
        'PYTHONPATH': os.pathsep.join(str(ROOT / p) for p in ('.runtime/p84-native-test-deps', 'apps/api', 'packages/cli-runtime', 'scripts'))}
    # Tests set their own enabled/disabled fixtures; do not inherit live switches.
    for key in (*ENABLE, *KEEP_OFF):
        env[key.upper()] = 'false'
    files = ('test_local_feature_activation.py', 'test_result_inbox.py', 'test_result_outbox.py',
        'test_learning_review.py', 'test_artifact_learning.py', 'test_outcome_observations.py',
        'test_business_events.py', 'test_business_event_acceptance.py', 'test_unified_approvals.py',
        'test_goal_admission.py', 'test_schedule_policy.py')
    try:
        with (folder / 'migration.log').open('wb') as log:
            subprocess.run([sys.executable, '-B', '-m', 'alembic', 'upgrade', '0075'],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
        with (folder / 'pytest.log').open('wb') as log:
            run = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '--maxfail=1',
                '-p', 'local_cycle_network_guard', *['apps/api/tests/' + f for f in files],
                '--junitxml=' + str(folder / 'junit.xml')], cwd=ROOT, env=env,
                stdout=log, stderr=subprocess.STDOUT, timeout=600)
        counts = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
        for suite in ElementTree.parse(folder / 'junit.xml').getroot().iter('testsuite'):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
        state.update(counts=counts, functional_pass=run.returncode == 0 and counts['tests'] >= 40
            and not any(counts[k] for k in ('failures', 'errors', 'skipped')))
    finally:
        after = asyncio.run(signatures(url))
        state.update(rows_after=after, primary_unchanged=before == after,
            source_unchanged=source == protected(), health=health())
        state['pass'] = state.get('functional_pass', False) and state['primary_unchanged'] and state['source_unchanged']
        write(folder / 'receipt.json', state)
        print(json.dumps({'folder': str(folder), **{k: v for k, v in state.items() if k not in ('rows_before', 'rows_after', 'source_before')}}))
    assert state['pass'], 'Keep failed evidence; do not activate from this run'


def prepare(test_path, checkpoint_path):
    import read_owned_pao_processes as owned
    cfg = settings()
    verify_local(cfg)
    tests = json.loads(location(test_path).read_text(encoding='utf-8'))
    assert tests['pass'] and tests['source_before'] == protected()
    checkpoint_path = location(checkpoint_path)
    checkpoint = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    assert checkpoint['binding']['sha256'] == binding()
    assert digest(location(checkpoint['database']['backup'])) == checkpoint['database']['sha256']
    assert checkpoint['database']['revision_before'] == '0075'
    assert all(code == 200 for code in health().values()), 'Serving endpoints must be healthy before config reload'
    subprocess.run([sys.executable, '-B', 'scripts/check_acos_idle.py', '--safe-repair'],
        cwd=ROOT, check=True, timeout=30)
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        owned.main()
    identities = json.loads(captured.getvalue())
    for kind in ('api', 'worker'):
        assert Path(identities[kind]['exe']).resolve() == Path(sys.executable).resolve()
    # A metadata/login operation is not in the business-job idle report.
    async def native_idle():
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(cfg.database_url, connect_args={'server_settings': {
            'default_transaction_read_only': 'on', 'statement_timeout': '10000'}})
        try:
            async with engine.connect() as db:
                assert await db.scalar(text("SELECT count(*) FROM cli_model_dispatches WHERE status IN ('dispatched','unknown')")) == 0
                assert await db.scalar(text('SELECT count(*) FROM cli_model_connections WHERE setup_operation_id IS NOT NULL')) == 0
                assert await db.scalar(text("SELECT count(*) FROM tenant_metadata_leases WHERE status='active' AND expires_at>now()")) == 0
                assert await db.scalar(text("SELECT count(*) FROM business_outbox WHERE status IN ('pending','processing')")) == 0
        finally:
            await engine.dispose()
    asyncio.run(native_idle())
    url = make_url(cfg.database_url)
    folder = ROOT / '.runtime' / ('local-feature-activation-' + uuid4().hex)
    folder.mkdir()
    state = {'binding': binding(), 'schema': asyncio.run(primary_schema()),
        'rows_before': asyncio.run(signatures(url)), 'source_before': protected(),
        'env_unrelated_hash': non_feature_hash((ROOT / '.env').read_bytes()),
        'flags_before': flags(cfg), 'checkpoint': str(checkpoint_path),
        'tests': str(location(test_path)), 'identities': identities,
        'archives_before': asyncio.run(inspect(url))['artifact_hashes']}
    write(folder / 'before.json', state)
    # Verify ALL exact executable/start-time/command identities before any stop.
    for kind in ('api', 'worker'):
        assert owned.metadata(identities[kind]['id']) == identities[kind]
    for kind in ('api', 'worker'):
        assert owned.metadata(identities[kind]['id']) == identities[kind]
        subprocess.run(['taskkill', '/PID', str(identities[kind]['id']), '/T', '/F'],
            check=True, capture_output=True, timeout=15)
    after = asyncio.run(signatures(url))
    write(folder / 'stopped.json', {'rows_after_stop': after, 'primary_unchanged': after == state['rows_before']})
    assert after == state['rows_before'], 'Concurrent writes preserved; review before applying config'
    print(json.dumps({'folder': str(folder), 'stopped_owned_idle_api_worker': True}))


async def verify(folder):
    import httpx
    from sqlalchemy import select
    from pao.auth import issue_token
    from pao.models import Member, User, Brain
    from pao.db import Session, engine
    folder = location(folder)
    cfg = settings()
    verify_local(cfg)
    assert all(getattr(cfg, key) is True for key in ENABLE)
    before = json.loads((folder / 'before.json').read_text(encoding='utf-8'))
    url = make_url(cfg.database_url)
    attempt = folder / ('verification-' + uuid4().hex)
    attempt.mkdir()
    window_before = await signatures(url)
    state = {'pass': False, 'scope': 'installed_features_fresh_readonly_window',
        'provider_calls': 0, 'GET_only': True, 'flags': flags(cfg),
        'activation_folder': str(folder), 'rows_before_window': window_before,
        'changed_since_preparation': [key for key in sorted(set(window_before) | set(before['rows_before']))
            if window_before.get(key) != before['rows_before'].get(key)],
        'primary_unchanged_since_preparation': window_before == before['rows_before']}
    try:
        source = protected()
        # Keep the original failed receipt. Do not silently rewrite its baseline.
        changed = [key for key in sorted(set(source) | set(before['source_before']))
            if source.get(key) != before['source_before'].get(key)]
        state['changed_files'] = changed
        assert source_manifest(before['source_before']) == source_manifest(source)
        assert non_feature_hash((ROOT / '.env').read_bytes()) == before['env_unrelated_hash']
        assert binding() == before['binding']
        async with Session() as db, httpx.AsyncClient(base_url='http://127.0.0.1:8100', trust_env=False, timeout=20) as client:
            # Windows' ambient cp1252 corrupts Vietnamese defaults; never rely
            # on the caller having set PYTHONUTF8 before comparing OpenAPI.
            contract = json.loads((ROOT / 'packages/contracts/openapi.json').read_text(encoding='utf-8'))
            assert (await client.get('/openapi.json')).json() == contract
            state['contract_utf8_verified'] = True
            members = list(await db.scalars(select(Member).join(User, Member.user_id == User.id).where(Member.role == 'owner', User.active.is_(True))))
            seen = set()
            learning_checked = 0
            for member in members:
                user = await db.get(User, member.user_id)
                headers = {'Authorization': 'Bearer ' + issue_token(user.id, user.auth_version)}
                params = {'workspace_id': member.workspace_id}
                for path, field in (('/v1/results/status', 'enabled'),
                    ('/v1/business-events/status', 'enabled'), ('/v1/schedules/workflows/status', 'manager_enabled'),
                    ('/v1/ads/outcome-observations/status', 'enabled'),
                    ('/v1/goal-executions/status', 'admission_enabled')):
                    response = await client.get(path, params=params, headers=headers)
                    assert response.status_code == 200, (path, response.status_code)
                    value = response.json()
                    assert value[field] is True
                    if path == '/v1/results/status':
                        assert value['external_delivery_enabled'] is False and value['destinations'] == ['in_app']
                    if path == '/v1/business-events/status':
                        assert value['producer_enabled'] and value['delivery_enabled'] and value['consumer'] == 'internal.audit.v1'
                    if path.endswith('workflows/status'):
                        assert value['dispatch_enabled'] is False and value['model_calls'] is False
                    if path.endswith('goal-executions/status'):
                        assert value['execution_enabled'] is False
                    assert (await client.get(path, params=params)).status_code == 401
                for path in ('/v1/results', '/v1/business-events/approvals'):
                    response = await client.get(path, params=params, headers=headers)
                    assert response.status_code == 200, (path, response.status_code)
                brain = await db.scalar(select(Brain).where(Brain.workspace_id == member.workspace_id,
                    Brain.owner_id == user.id, Brain.archived_at.is_(None)).limit(1))
                if brain:
                    response = await client.get(f'/v1/learning/brains/{brain.id}/proposals', headers=headers)
                    assert response.status_code == 200
                    learning_checked += 1
                seen.add(member.workspace_id)
            assert len(seen) >= 2
            state['owner_workspaces_checked'] = len(seen)
            state['learning_brains_checked'] = learning_checked
        after = await signatures(url)
        state.update(binding=binding(), schema_unchanged=await primary_schema() == before['schema'],
            primary_rows_unchanged=after == window_before, rows_after=after,
            archives_unchanged=(await inspect(url))['artifact_hashes'] == before['archives_before'],
            unrelated_config_unchanged=True, serving_source_unchanged=True, health=health())
        state['pass'] = all(state[k] for k in ('schema_unchanged', 'primary_rows_unchanged', 'archives_unchanged')) and all(v == 200 for v in state['health'].values())
    finally:
        await engine.dispose()
        write(attempt / 'receipt.json', state)
        print(json.dumps({'folder': str(attempt), **{k: v for k, v in state.items()
            if k not in ('rows_after', 'rows_before_window', 'changed_files')}}))
    assert state['pass']


if __name__ == '__main__':
    assert ROOT == Path('F:/PAO-ACOS')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('test', 'prepare', 'verify'))
    parser.add_argument('paths', nargs='*')
    args = parser.parse_args()
    if args.action == 'test':
        assert not args.paths
        with isolated_test_slot():
            test()
    elif args.action == 'prepare':
        assert len(args.paths) == 2
        prepare(*args.paths)
    else:
        assert len(args.paths) == 1
        asyncio.run(verify(args.paths[0]))
