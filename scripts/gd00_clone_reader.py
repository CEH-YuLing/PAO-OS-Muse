"""Read a restored source/DB in a child process; no workers, login writes or providers."""
import asyncio
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from sqlalchemy.engine import make_url


def clone_url(raw):
    url = make_url(raw)
    if (url.drivername, url.host, url.port, url.username) != ('postgresql+asyncpg', '127.0.0.1', 15432, 'pao') or not re.fullmatch(r'pao_s03_restore_[0-9a-f]{32}', url.database or ''):
        raise ValueError('gd00_owned_clone_required')
    return url


def network_guard(event, args):
    if event == 'socket.connect':
        address = args[1]
        if not isinstance(address, tuple) or address[:2] not in {('127.0.0.1', 15432), ('127.0.0.1', 16379)}:
            raise RuntimeError('gd00_external_network_denied')
    if event in {'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'}:
        raise RuntimeError('gd00_child_process_denied')


def run_restored_reader(url, saved, archive, folder):
    """Called only while check_s03_restore owns the temporary restored database."""
    from dotenv import dotenv_values
    from gd00_baseline import extract_source, read_private, write_new
    target = folder/'restored-source'
    clone_url(url)
    extract_source(archive, saved['source']['files'], target)
    recovered = read_private(folder/'private-recovery')
    values = dotenv_values(stream=io.StringIO(recovered['.env'].decode('utf-8-sig')), interpolate=False)
    if not values.get('INTEGRATION_ENCRYPTION_KEY'):
        raise ValueError('gd00_recovered_encryption_key_missing')
    env = os.environ.copy()
    env.update({key: value for key, value in values.items() if value is not None})
    from urllib.parse import urlsplit, urlunsplit
    redis = urlsplit(values.get('REDIS_URL',''))
    if redis.scheme != 'redis' or redis.hostname != '127.0.0.1' or redis.port != 16379:
        raise ValueError('gd00_local_redis_required')
    env.update(PAO_ROOT=str(target), DATABASE_URL=url.render_as_string(hide_password=False),
        REDIS_URL=urlunsplit(redis._replace(path='/14',query='',fragment='')), JWT_SECRET='gd00-synthetic-clone-jwt-not-a-production-secret',
        PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
        PYTHONPATH=os.pathsep.join(str(target/name) for name in ('apps/api','scripts','packages/cli-runtime','packages/pao-mcp')))
    # Explicitly disable all existing activation/dispatch flags in this child only.
    from pao.config import Settings
    env.update({key.upper(): 'false' for key in Settings.model_fields if key.endswith('_enabled')})
    child = subprocess.run([sys.executable, '-B', str(target/'scripts/gd00_clone_reader.py')],
        cwd=target, env=env, capture_output=True, timeout=120)
    if child.returncode:
        # Raw stderr/HTTP bodies/credentials are not operator-report fields.
        try: diagnostic = json.loads(child.stdout.decode('utf-8'))
        except Exception: diagnostic = {}
        write_new(folder/'clone-reader-failure.json', {'pass':False, 'exit_code':child.returncode,
            'code':diagnostic.get('code','restored_reader_failed'), 'error_type':diagnostic.get('error_type'),
            'stderr_sha256':__import__('hashlib').sha256(child.stderr).hexdigest()})
        raise ValueError('gd00_restored_reader_failed')
    result = json.loads(child.stdout.decode('utf-8'))
    if result.get('pass') is not True:
        raise ValueError('gd00_restored_reader_not_accepted')
    write_new(folder/'clone-reader.json', result)
    return result


async def read():
    from cryptography.fernet import Fernet, InvalidToken
    from sqlalchemy import text, select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from pao.config import ROOT, settings
    url = clone_url(settings().database_url)
    if ROOT.name != 'restored-source' or (ROOT/'.env').exists():
        raise ValueError('gd00_restored_source_without_plaintext_env_required')
    engine = create_async_engine(url, connect_args={'server_settings': {
        'default_transaction_read_only':'on', 'statement_timeout':'10000'}})
    # Replace unused import-time DB factory before composing routes; all imported
    # Session references and FastAPI dependencies then use this read-only engine.
    import pao.db as database_module
    await database_module.engine.dispose()
    database_module.engine = engine
    database_module.Session = async_sessionmaker(engine, expire_on_commit=False)
    sys.addaudithook(network_guard)
    from pao.app import create_app
    from pao.auth import issue_token
    from pao.models import User, ChatSession, Run
    from check_m2_restore import inspect
    import httpx
    try:
        decrypted = 0
        cipher = Fernet(settings().integration_encryption_key.encode())
        sample = None
        async with engine.connect() as db:
            if await db.scalar(text('SHOW transaction_read_only')) != 'on':
                raise ValueError('gd00_clone_readonly_required')
            columns = await db.execute(text("""SELECT table_name,column_name FROM information_schema.columns
                WHERE table_schema='public' AND (column_name='ciphertext' OR right(column_name,11)='_ciphertext')
                ORDER BY table_name,column_name"""))
            for table, column in columns:
                quote = lambda s: '"'+s.replace('"','""')+'"'
                for value in await db.scalars(text('SELECT '+quote(column)+' FROM '+quote(table)+' WHERE '+quote(column)+' IS NOT NULL')):
                    raw = value.encode() if isinstance(value, str) else bytes(value)
                    cipher.decrypt(raw)
                    decrypted += 1
                    sample = raw
        # A real stored credential where present, otherwise a clearly synthetic
        # challenge: never claim fixture-only validation decrypted real rows.
        challenge = sample or cipher.encrypt(b'gd00-synthetic-encryption-challenge')
        try: Fernet(Fernet.generate_key()).decrypt(challenge)
        except InvalidToken: wrong_key_rejected = True
        else: raise ValueError('gd00_wrong_key_not_rejected')
        from pao.model_router import _cipher, ModelRouterError
        original_key = settings().integration_encryption_key
        settings().integration_encryption_key = ''
        try:
            try: _cipher()
            except ModelRouterError: missing_key_rejected = True
            else: raise ValueError('gd00_missing_key_not_rejected')
        finally: settings().integration_encryption_key = original_key
        artifacts = await inspect(url)
        app = create_app()
        checked = {}
        async with app.router.lifespan_context(app), httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url='http://clone', trust_env=False) as client:
            for path in ('/health','/ready','/openapi.json'):
                response = await client.get(path)
                if response.status_code != 200: raise ValueError('gd00_clone_health_failed')
                checked[path] = response.status_code
                if path == '/openapi.json':
                    operations = sum(method in {'get','post','put','patch','delete','head','options'}
                        for value in response.json()['paths'].values() for method in value)
            async with database_module.Session() as db:
                user = await db.scalar(select(User).where(User.active.is_(True)).order_by(User.id))
                if not user: raise ValueError('gd00_restored_user_missing')
                token = issue_token(user.id, user.auth_version)
                headers = {'Authorization':'Bearer '+token}
                response = await client.get('/v1/me', headers=headers)
                if response.status_code != 200: raise ValueError('gd00_clone_identity_read_failed')
                checked['/v1/me'] = 200
                run = await db.scalar(select(Run).join(ChatSession, Run.session_id == ChatSession.id)
                    .where(ChatSession.user_id == user.id, Run.status == 'completed').order_by(Run.id))
                if run:
                    response = await client.get('/v1/runs/'+str(run.id), headers=headers)
                    if response.status_code != 200: raise ValueError('gd00_clone_history_read_failed')
                    checked['/v1/runs/{id}'] = 200
        return {'pass':True, 'revision':artifacts['revision'], 'physical_tables':len(artifacts['counts']),
            'archive_replays':len(artifacts['artifact_hashes']), 'http_checks':checked, 'operations':operations,
            'decrypted_stored_credentials':decrypted, 'wrong_key_rejected':wrong_key_rejected,
            'missing_key_rejected':missing_key_rejected, 'db_readonly':True,
            'source_from_checkpoint':True,'plaintext_env_restored':False,
            'external_calls':False,'worker_started':False,'jwt_saved':False}
    finally:
        await engine.dispose()


if __name__ == '__main__':
    try:
        print(json.dumps(asyncio.run(read())))
    except Exception as error:
        code = str(error) if type(error) is ValueError and re.fullmatch(r'gd00_[a-z_]+', str(error)) else 'gd00_clone_read_failed'
        print(json.dumps({'pass':False,'code':code,'error_type':type(error).__name__}))
        raise SystemExit(2)
