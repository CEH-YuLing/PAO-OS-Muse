"""Reconcile an explicitly scoped script-only repair, never hide a failed run.

The original XML remains untouched. No skipped/errored case, arbitrary failure,
production-source change or missing retry may be accepted by this S3 gate.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from pao.config import ROOT
from pao.skills import execution_binding

FROZEN='c44d27b22f4af7457327dc062060fb8faa4c3cdcc7d8d48888524cb87483bff1'
REPAIR='apps.api.tests.test_p7_restore.test_populated_p7_restore_fresh_process_identity_and_no_resend'


def cases(path):
    root=ET.parse(path).getroot();result={}
    for case in root.iter('testcase'):
        key=case.get('classname')+'.'+case.get('name')
        if key in result:raise RuntimeError('Duplicate test identity')
        if case.find('skipped') is not None or case.find('error') is not None:raise RuntimeError('Skipped/error test is not accepted')
        result[key]=case.find('failure') is None
    return result


def validate():
    assert execution_binding()['sha256']==FROZEN,'Production backend changed after full regression'
    full=cases(ROOT/'.runtime/s3-full-final.xml');assert len(full)==2078
    failed={key for key,value in full.items() if not value};assert failed=={REPAIR},'Unexpected full regression failure'
    recovery=cases(ROOT/'.runtime/s3-recovery-final.xml');assert len(recovery)==27 and all(recovery.values()) and REPAIR in recovery
    assert (ROOT/'.runtime/s3-recovery-final.xml').stat().st_mtime>=(ROOT/'.runtime/s3-full-final.xml').stat().st_mtime
    # Only the restore helper's revision allowlist changed. Report both runs;
    # never rewrite the full XML or describe it as a new all-green full run.
    latest={**full,**recovery};assert len(latest)==2078 and all(latest.values())
    value={'pass':True,'unique_cases_verified':len(latest),'full_run_passed':2077,'full_run_failed':1,
        'full_run_errors':0,'full_run_skipped':0,'recovery_passed':27,'backend_unchanged':True,
        'repair_scope':'P7 populated-restore helper now reuses the explicit supported-revision allowlist; all data/dedup/no-resend checks unchanged',
        'full_rerun':False,'binding':execution_binding()}
    return value


if __name__=='__main__':
    result=validate();(ROOT/'.runtime/s3-regression.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
