"""Real UI/HTTP + fixture rotation; no provider calls or production data."""
import asyncio
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from pao.config import ROOT
from pao.db import Session
from pao.models import ModelProviderConnection,ModelGrantActivation,TenantConnectionReference,TenantConnectionGrant
from pao.model_router import encrypt_key
from p6_browser_harness import browser
from test_model_connection_fence import fenced
from test_connection_inventory import corpus
from test_engine_contract import engines


async def test_model_rotation_reapply_new_consent_and_sme_switch(client,fenced):
    c,calls,_=fenced
    directory=ROOT/'.runtime'/('s22a-handshake-'+uuid4().hex);directory.mkdir()
    marker=directory/'rotate';done=directory/'rotated'
    async def rotate():
        async with asyncio.timeout(120):
            while not marker.exists():await asyncio.sleep(.05)
        async with Session.begin() as db:
            row=await db.get(ModelProviderConnection,c['connections']['a']['model'])
            row.api_key_ciphertext=encrypt_key('new-local-fixture-never-provider')
        done.touch()
    rotation=asyncio.create_task(rotate())
    try:
        report=await browser('scripts/verify_s22a_browser.cjs','PAO_S22A_BROWSER_FIXTURE',{
            'workspace':c['workspace'],'second':c['second'],'actor':c['user_id'],
            'source':c['connections']['a']['model'],'marker':str(marker),'done':str(done)},'s22a')
        await asyncio.wait_for(rotation,5)
        assert report['new_consent_required'] and report['tenant_switch'] and report['native_probe_denied']
        async with Session() as db:
            refs=list(await db.scalars(select(TenantConnectionReference).order_by(TenantConnectionReference.generation)))
            assert len(refs)==2 and refs[0].status=='revoked' and refs[1].supersedes_id==refs[0].id
            grants=list(await db.scalars(select(TenantConnectionGrant).order_by(TenantConnectionGrant.created_at)))
            assert len(grants)==2 and grants[0].status=='revoked' and grants[1].status=='staged'
            assert len(list(await db.scalars(select(ModelGrantActivation))))==2
        assert all(calls[k]==0 for k in ('factory','stream','plan','extract'))
    finally:
        if not rotation.done():rotation.cancel()
        await asyncio.gather(rotation,return_exceptions=True)
