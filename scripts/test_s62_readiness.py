from check_s6_readiness import assess
from test_s6_readiness import evidence,BINDING


def setup():
    live,regression,health=evidence()
    live.update(revision='0071',operations=399,physical_tables=153)
    regression['tests']=2251
    receipt={'phase1_accepted':True,'binding':BINDING,
        'identity':True,'sessions':True,'data':True,'no_auto_purge':True,'browser':True,'migration_restore':True}
    return live,regression,health,receipt


def test_new_release_requires_current_receipt_not_just_http():
    live,regression,health,receipt=setup()
    assert not assess(live,regression,health,BINDING)['local_checks_passed']
    result=assess(live,regression,health,BINDING,receipt)
    assert result['local_checks_passed']
    assert not result['s6_accepted'] and not result['production_accepted']
    assert sum(g['state']=='local_accepted' for g in result['gates'])==2


def test_stale_receipt_or_partial_evidence_does_not_close_phase():
    for key,value in [('binding',{}),('phase1_accepted','true'),('browser',False),('migration_restore',False),('no_auto_purge',False)]:
        live,regression,health,receipt=setup();receipt[key]=value
        assert not assess(live,regression,health,BINDING,receipt)['local_checks_passed']


def test_new_release_cannot_reuse_old_test_count_or_schema_counts():
    live,regression,health,receipt=setup();regression['tests']=2224
    assert not assess(live,regression,health,BINDING,receipt)['local_checks_passed']
    live,regression,health,receipt=setup();live['physical_tables']=149
    assert not assess(live,regression,health,BINDING,receipt)['local_checks_passed']
