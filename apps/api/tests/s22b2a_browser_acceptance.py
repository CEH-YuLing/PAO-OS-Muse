"""Real HTTP read-policy metadata from Settings context, not a quota-form gate."""
from p6_browser_harness import browser
from test_model_connection_fence import fenced
from test_connection_inventory import corpus
from test_engine_contract import engines


async def test_read_policy_http_cas_and_tenant_switch(client,fenced):
    c,calls,_=fenced
    report=await browser('scripts/verify_s22b2a_browser.cjs','PAO_S22B2A_BROWSER_FIXTURE',{
        'workspace':c['workspace'],'second':c['second']},'s22b2a')
    assert report['quota_metadata'] and report['quota_ui'] is False and report['tenant_switch']
    assert all(calls[k]==0 for k in ('factory','stream','plan','extract'))
