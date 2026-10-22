"""Reconcile fixture-only repair; retain failed full XML/JSON verbatim.

No production change, skip, error, unknown failure or missing retry is waived.
The original full run is NOT described as an all-green rerun.
"""
import json
import xml.etree.ElementTree as ET
from pao.config import ROOT
from pao.skills import execution_binding

FROZEN='aef563f8c0664b061f47961cae673afc5372923563bc5a663b04153c3ce19977'
PREFIX='apps.api.tests.test_reconciliation.'
FAILED={PREFIX+name for name in (
    'test_matches_not_business_verified_and_no_writes',
    'test_scope_mismatch_not_compared[account_id-act_2]',
    'test_scope_mismatch_not_compared[currency-USD]',
    'test_scope_mismatch_not_compared[timezone-UTC]',
    'test_scope_mismatch_not_compared[attribution-different]',
    'test_scope_mismatch_not_compared[period_end-2026-10-06]',
    'test_unknown_zero_and_exact_decimal_difference[changes0-insufficient_data]',
    'test_unknown_zero_and_exact_decimal_difference[changes1-mismatch]',
    'test_unknown_zero_and_exact_decimal_difference[changes2-mismatch]',
    'test_auth_owner_and_connection_version')}


def cases(path):
    found={}
    for case in ET.parse(path).getroot().iter('testcase'):
        key=case.get('classname')+'.'+case.get('name')
        assert key not in found,'Duplicate case identity'
        assert case.find('skipped') is None and case.find('error') is None,'No skip/error is accepted'
        found[key]=case.find('failure') is None
    return found


def validate():
    binding=execution_binding();assert binding['sha256']==FROZEN
    original=json.loads((ROOT/'.runtime/s4-backend.json').read_text(encoding='utf-8'))
    assert original['binding']==binding and original['binding_unchanged']
    assert (original['tests'],original['failures'],original['errors'],original['skipped'])==(2099,10,0,0)
    full=cases(ROOT/'.runtime/s4-full.xml');assert len(full)==2099 and {k for k,v in full.items() if not v}==FAILED
    recovery=cases(ROOT/'.runtime/s4-recovery.xml');assert len(recovery)==52 and all(recovery.values()) and FAILED<=recovery.keys()
    assert sum(key.startswith('apps.api.tests.test_telegram_reports.') for key in recovery)==6
    callers=cases(ROOT/'.runtime/s4-fixture-callers.xml');assert len(callers)==82 and all(callers.values())
    for name in ('test_analysis_tools','test_attribution_read_tool','test_skill_artifacts','test_skill_router','test_analysis_routing','test_m2_acceptance','test_skill_budget','test_skill_version_guard'):
        assert any(key.startswith('apps.api.tests.'+name+'.') for key in callers),'Missing shared-fixture caller coverage'
    for path in ('s4-recovery.xml','s4-fixture-callers.xml'):
        assert (ROOT/'.runtime'/path).stat().st_mtime>=(ROOT/'.runtime/s4-full.xml').stat().st_mtime
    assert recovery.keys()<=full.keys() and callers.keys()<=full.keys()
    latest={**full,**recovery,**callers};assert len(latest)==2099 and all(latest.values())
    return {'pass':True,'unique_cases_verified':2099,'full_run_passed':2089,'full_run_failed':10,'full_run_errors':0,'full_run_skipped':0,
        'recovery_passed':len(recovery),'shared_fixture_callers_passed':len(callers),'backend_unchanged':True,'binding':binding,
        'repair_scope':'Only test_business_tools.seed now supplies the required app_binding; Telegram report fixture uses synthetic App credentials. No assertion or production gate weakened.',
        'full_rerun':False}


if __name__=='__main__':
    value=validate();(ROOT/'.runtime/s4-regression.json').write_text(json.dumps(value),encoding='utf-8');print(json.dumps(value))
