"""GD01 isolated source acceptance; serial pao_test/Redis15, no provider network."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from stage_openai_effort_candidate import stage
from local_cycle_test_lock import isolated_test_slot
from check_pao_mcp_local import digests
from check_p84_foundation import primary_schema,health
from check_installation_ai_migration import signatures
from pao.config import settings
from sqlalchemy.engine import make_url
from cryptography.fernet import Fernet


async def live_key():
    from pao.db import Session
    from pao.models import ModelProviderConnection
    from pao.model_router import decrypt_key
    from pao.modules.installation_ai.models import InstallationAIResource
    from pao.modules.installation_ai.service import ready
    from sqlalchemy import select
    async with Session() as db:
        row=await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='openai',InstallationAIResource.enabled.is_(True)))
        await ready(db,row)
        assert {'gpt-6.1-sol','gpt-6-luna'} <= {v['model'] for v in row.catalog},'Selected live models not in captured catalog'
        source=await db.get(ModelProviderConnection,row.source_id)
        return decrypt_key(source.api_key_ciphertext)


def main(focused,live=False,personal_cli=False,live_muse=False,muse_only=False,muse_business_local=False,provider_only=False):
    cfg=settings();pg=urlsplit(cfg.database_url)
    assert ROOT==Path('F:/PAO-ACOS') and (pg.hostname,pg.port,pg.path)==('127.0.0.1',15432,'/pao_acos_local')
    before=digests();schema=asyncio.run(primary_schema());rows=asyncio.run(signatures(make_url(cfg.database_url)))
    folder=ROOT/'.runtime'/('gd01-tests-'+uuid4().hex);folder.mkdir()
    staged=stage(folder/'source')
    state={'pass':False,'functional_pass':False,'installed':False,'focused':focused,'provider_calls':0,
        'primary_migrated':False,'schema_before':schema,'primary_rows_before':rows,'live_openai':live}
    env={**os.environ,'PAO_ROOT':str(staged),'DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
        'PAO_TEST_DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
        'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
        'JWT_SECRET':'synthetic-gd01-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
        'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1',
        'PYTHONPATH':os.pathsep.join(str(p) for p in (ROOT/'.runtime/p84-native-test-deps',staged/'apps/api',staged/'packages/cli-runtime',ROOT/'scripts'))}
    try:
        with (folder/'migration.log').open('wb') as log:
            result=subprocess.run([sys.executable,'-B','-m','alembic','upgrade','0077'],cwd=staged,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=90)
        assert result.returncode==0,'Test migration failed; retained log'
        files=['test_gd01_ai_resources.py','test_installation_ai_modalities.py']
        if not focused:files += ['test_openai_effort.py','test_gateway.py','test_installation_ai.py',
            'test_installation_ai_catalog.py','test_model_router.py','test_engine_contract.py','test_business_routing.py',
            'test_enterprise_ai.py','test_studio.py','test_business_operations.py','test_model_connection_fence.py',
            'test_personal_cli.py','test_cli_models.py','test_chat_management.py','test_memory.py',
            'test_legacy_accounting_fence.py','test_tenant_model_resources.py','test_embedding_resources.py','test_muse_resources.py','test_muse_business.py','test_provider_managed_tokens.py']
        if personal_cli:files=['test_personal_cli.py','test_cli_models.py','test_cli_login.py']
        if muse_only:files=['test_muse_resources.py']
        if muse_business_local:files=['test_muse_business.py','test_business_planning.py','test_business_plan_review.py','test_business_routing.py','test_business_operations.py','test_muse_resources.py']
        if provider_only:files=['test_provider_managed_tokens.py','test_muse_business.py']
        if live_muse:
            files=[{'orchestrator':'gd01_muse_orchestrator_live_acceptance.py','business':'gd01_muse_business_live_acceptance.py','context':'gd01_muse_context_live_acceptance.py'}.get(live_muse,'gd01_muse_live_acceptance.py')]
            env['PAO_GD01_MUSE_LIVE_APPROVED']='two_synthetic_calls_no_fallback'
            env['PAO_GD01_MUSE_LIVE_RECEIPT']=str(folder/'live-summary.json')
        if live:
            files=['gd01_live_acceptance.py']
            env['PAO_GD01_LIVE_KEY']=asyncio.run(live_key())
            env['PAO_GD01_LIVE_APPROVED']='two_synthetic_calls_no_fallback'
            env['PAO_GD01_LIVE_RECEIPT']=str(folder/'live-summary.json')
        assert all((staged/'apps/api/tests'/name).is_file() for name in files),'Missing selected test module'
        with (folder/'pytest.log').open('wb') as log:
            result=subprocess.run([sys.executable,'-B','-m','pytest','-q','--maxfail=1',*([] if live or live_muse else ['-p','local_cycle_network_guard']),
                *['apps/api/tests/'+name for name in files],'--junitxml='+str(folder/'junit.xml')],cwd=staged,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
            for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        state['counts']=counts
        state['functional_pass']=result.returncode==0 and counts['tests']>0 and not any(counts[k] for k in ('failures','errors','skipped'))
        if live:
            env.pop('PAO_GD01_LIVE_KEY',None)
            state['provider_calls']='at_most_two_openai_inference_requests_see_live_summary'
            state['live_summary']=json.loads((folder/'live-summary.json').read_text()) if (folder/'live-summary.json').exists() else None
            if state['live_summary'] is not None:
                state['provider_calls']=len(state['live_summary']['calls'])
        if live_muse:
            state['live_muse']=True
            state['live_summary']=json.loads((folder/'live-summary.json').read_text()) if (folder/'live-summary.json').exists() else None
            summary=state['live_summary']
            # A failed assertion can happen after dispatch but before usage collection.
            # Missing evidence is unknown, never proof of zero quota consumption.
            if summary is None:
                state['provider_calls']=None
            elif 'requested_calls' in summary:
                state['provider_calls']=len(summary['requested_calls'])
            elif summary.get('pass'):
                state['provider_calls']=len(summary.get('calls',[]))
            else:
                state['provider_calls']=None
    finally:
        after=asyncio.run(signatures(make_url(cfg.database_url)))
        state.update(source_env_pins_unchanged=before==digests(),schema_after=asyncio.run(primary_schema()),
            primary_rows_after=after,primary_rows_unchanged=rows==after,
            changed_primary_tables=[k for k in sorted(set(rows)|set(after)) if rows.get(k)!=after.get(k)],health=health())
        state['pass']=state['functional_pass'] and state['source_env_pins_unchanged'] and state['schema_before']==state['schema_after'] and state['primary_rows_unchanged']
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(state,out,indent=2)
        print(json.dumps({'folder':str(folder),**{k:v for k,v in state.items() if not k.startswith('primary_rows_')}}))
    return 0 if state['pass'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--focused',action='store_true')
    parser.add_argument('--personal-cli',action='store_true',help='Bounded reconnect/catalogue regression, no provider requests')
    parser.add_argument('--live-openai',action='store_true',help='Explicit two-call live acceptance using the configured source; no private inputs/fallback')
    parser.add_argument('--live-muse',action='store_true',help='Two synthetic Muse subscription calls via approved isolated profile; pao_test only')
    parser.add_argument('--muse-only',action='store_true',help='Bounded Muse registry/ledger checks without provider calls')
    parser.add_argument('--live-muse-orchestrator',action='store_true',help='Two synthetic Muse planner/final calls only')
    parser.add_argument('--muse-business-local',action='store_true',help='Existing business/Muse offline regression with real ARQ and synthetic model boundary')
    parser.add_argument('--live-muse-business',action='store_true',help='Two real Muse calls through dependent synthetic business jobs and ARQ')
    parser.add_argument('--live-muse-context',action='store_true',help='Two synthetic High reasoning Muse calls without PAO token caps')
    parser.add_argument('--provider-tokens-only',action='store_true',help='Provider-managed token/privacy/wire and business regression without provider calls')
    args=parser.parse_args()
    assert sum((args.focused,args.live_openai,args.personal_cli,args.live_muse,args.muse_only,args.live_muse_orchestrator,args.muse_business_local,args.live_muse_business,args.live_muse_context,args.provider_tokens_only))<=1
    mode='context' if args.live_muse_context else 'business' if args.live_muse_business else 'orchestrator' if args.live_muse_orchestrator else args.live_muse
    with isolated_test_slot():raise SystemExit(main(args.focused,args.live_openai,args.personal_cli,mode,args.muse_only,args.muse_business_local,args.provider_tokens_only))
