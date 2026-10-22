"""Host App Settings native HTTP/CAS/temp-file only; never real .env or Meta."""
from sqlalchemy import select
from dotenv import dotenv_values
from pao.db import Session
from pao.models import Workspace,Member
from pao.config import ROOT
from pao.integrations.meta.client import MetaClient
from pao.modules.operations.checkpoint import digest
from p6_browser_harness import browser
from test_meta_app_settings import config_file


async def test_host_config_lost_response_cas_validation_secret_and_runtime_gate(client,identity,config_file,monkeypatch):
    baseline=digest(ROOT/'.env')
    async def forbidden(*args,**kwargs):raise AssertionError('No Meta transport in host Settings acceptance')
    monkeypatch.setattr(MetaClient,'_request',forbidden)
    report=await browser('scripts/verify_s23e_browser.cjs','PAO_HOST_SETTINGS_BROWSER',{'workspace':identity['workspace']},'s23e-host')
    assert all(report[key] for key in ('local_validation','lost_response','manual_recovery','preserve_same_app_key','changed_app_requires_key','stale_revision','hidden_clear','malformed_unknown','readonly_locked','mobile'))
    values=dotenv_values(config_file[0])
    assert values['META_APP_ID']=='123' and values['META_GRAPH_API_VERSION']=='v26.2'
    assert values['META_APP_SECRET']=='fixture-host-new-key-NOT-REAL'
    assert all(values[flag]=='false' for flag in ('META_WRITE_ENABLED','META_AUTOPILOT_ENABLED','ADS_AUTOPILOT_GLOBAL_ENABLED'))
    assert values['INTEGRATION_ENCRYPTION_KEY']==config_file[1] and values['OTHER_SETTING']=='preserved'
    assert values['META_APP_CONFIG_SOURCE']=='settings_ui' and digest(ROOT/'.env')==baseline


async def test_multi_sme_host_form_denied_and_late_response_scoped(client,identity,config_file):
    baseline=digest(ROOT/'.env');before=config_file[0].read_bytes()
    async with Session.begin() as db:
        second=Workspace(name='Host Settings operator SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=identity['user_id'],role='operator'));wid=second.id
    report=await browser('scripts/verify_s23e_scope_browser.cjs','PAO_HOST_SCOPE_BROWSER',{'workspace':identity['workspace'],'second':wid},'s23e-scope')
    assert report['multi_sme_denied'] and report['late_response'] and report['role_switch']
    assert config_file[0].read_bytes()==before and digest(ROOT/'.env')==baseline
