"""Stop verified idle services for the reviewed four-file patch, no migration.

The actual source promotion uses apply_patch separately. Source/credential/runtime
files are never copied or edited by this script. Failed tests/checkpoint/idle
checks stop before any process termination. Windows CIM is not required.
"""
import asyncio
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from pao.config import settings
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from check_p84_foundation import binding,primary_schema
from check_installation_ai_migration import signatures
from check_m2_restore import inspect
from pao.modules.operations.checkpoint import digest
from check_pao_mcp_local import digests
import read_owned_pao_processes as owned

CHECKPOINT=ROOT/'.runtime/checkpoints/p0-20261020T143814-3397bcd2/manifest.json'
TESTS=ROOT/'.runtime/openai-effort-tests-b2e37efeb54345618dfd325eaec661ea/receipt.json'
FOCUSED=ROOT/'.runtime/openai-effort-tests-f44eaf15128e4e7aa3268682e8b0a8b5/receipt.json'
DRIFT=ROOT/'.runtime/openai-effort-drift-856646a49be241a9b4fbcf78dd8a0459/receipt.json'


async def quiet():
    url=make_url(settings().database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    engine=create_async_engine(url,connect_args={'server_settings':{'default_transaction_read_only':'on'}})
    try:
        async with engine.connect() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0075'
            assert await db.scalar(text("SELECT count(*) FROM cli_model_dispatches WHERE status IN ('dispatched','unknown')"))==0
            assert await db.scalar(text('SELECT count(*) FROM cli_model_connections WHERE setup_operation_id IS NOT NULL'))==0
            assert await db.scalar(text("SELECT count(*) FROM tenant_metadata_leases WHERE status='active' AND expires_at>now()"))==0
    finally:await engine.dispose()


def main():
    assert ROOT==Path('F:/PAO-ACOS') and sys.argv[1:]==['--stop-for-patch']
    tested=json.loads(TESTS.read_text());focused=json.loads(FOCUSED.read_text());drift=json.loads(DRIFT.read_text())
    # Preserve both aggregate failures. No failed receipt is promoted or rewritten.
    # Separate functional proof from live concurrent-user isolation, explicitly.
    assert tested['counts']=={'tests':325,'failures':0,'errors':0,'skipped':0}
    assert focused['counts']=={'tests':37,'failures':0,'errors':0,'skipped':0}
    assert not tested['pass'] and not focused['pass'] and focused['functional_tests_passed']
    assert tested['serving_source_env_pins_unchanged'] and focused['serving_source_env_pins_unchanged']
    assert tested['candidate_files']==focused['candidate_files']
    assert focused['changed_primary_tables']==['tenant_metadata_leases']
    assert drift['changed_since_checkpoint']==['login_sessions','tenant_metadata_leases']
    assert drift['fresh_window_unchanged'] and drift['archives_unchanged'] and drift['owned_clone_removed']
    checkpoint=json.loads(CHECKPOINT.read_text())
    assert checkpoint['binding']['sha256']==binding()=='7ccc74553002ccc79d2aeb5c0d68e90f9c34d49188f37264b33e36de2bf96584'
    assert digest(Path(checkpoint['database']['backup']))==checkpoint['database']['sha256']
    assert checkpoint['database']['revision_before']=='0075'
    asyncio.run(quiet())
    subprocess.run([sys.executable,'-B','scripts/check_acos_idle.py','--safe-repair'],cwd=ROOT,check=True,timeout=30)
    output=io.StringIO()
    with contextlib.redirect_stdout(output):owned.main()
    identities=json.loads(output.getvalue())
    folder=ROOT/'.runtime'/('openai-effort-install-'+uuid4().hex);folder.mkdir()
    value={'stopped':False,'installed':False,'provider_calls':0,'schema_migrated':False,
        'checkpoint':str(CHECKPOINT),'tests':str(TESTS),'focused':str(FOCUSED),'drift_review':str(DRIFT),
        'test_aggregate_pass':False,'test_functional_proof_only':True,
        'source_before':digests(),'binding_before':binding(),
        'rows_before':asyncio.run(signatures(make_url(settings().database_url))),
        'schema_before':asyncio.run(primary_schema()),'archives_before':asyncio.run(inspect(make_url(settings().database_url)))['artifact_hashes']}
    (folder/'preflight.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    from pao.modules.cli_connections.antigravity_native import CONFIG
    value['antigravity_provision_sha256']=digest(CONFIG)
    for name in ('api','worker'):
        assert owned.metadata(identities[name]['id'])==identities[name]
        subprocess.run(['taskkill','/PID',str(identities[name]['id']),'/T','/F'],check=True,capture_output=True,timeout=15)
    value['stopped']=True
    value['rows_after_stop']=asyncio.run(signatures(make_url(settings().database_url)))
    changed=[key for key in value['rows_after_stop'] if value['rows_after_stop'][key]!=value['rows_before'].get(key)]
    assert not changed,'Concurrent write at stop boundary; preserve it and review before patching'
    (folder/'preflight.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps({'folder':str(folder),'stopped_owned_idle_api_worker':True,'source_not_patched_by_script':True}))


if __name__=='__main__':main()
