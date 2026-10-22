from check_phase3_release_security import assess


def test_missing_or_stale_audit_is_not_clean():
    for audit in ({}, {'audit_completed': True, 'runtime_clean': True,
                         'runtime_requirements_sha256': 'old', 'affected_packages': []}):
        result = assess({'local_prepared': True}, audit, {}, 'new', 'new-js')
        assert result['functional_local_prepared']
        assert not result['python_runtime_clear'] and not result['release_promotable']


def test_findings_cannot_be_hidden_by_clean_flag():
    audit = {'audit_completed': True, 'source_image_requirements_verified': True,
             'runtime_clean': True, 'runtime_requirements_sha256': 'lock',
             'affected_packages': [{'name': 'pyjwt'}]}
    result = assess({'local_prepared': True}, audit, {'package_lock_sha256': 'js'}, 'lock', 'js')
    assert result['python_audit_current'] and result['js_audit_current']
    assert not result['python_runtime_clear'] and result['python_affected_packages'] == ['pyjwt']
    assert not result['production_accepted'] and not result['release_promotable']


def test_clean_scan_does_not_grant_production_or_cold_restore():
    audit = {'audit_completed': True, 'source_image_requirements_verified': True,
             'runtime_clean': True, 'runtime_requirements_sha256': 'lock', 'affected_packages': []}
    result = assess({'local_prepared': True}, audit, {'package_lock_sha256': 'js'}, 'lock', 'js')
    assert result['python_runtime_clear']
    assert not result['existing_archive_cold_restore_accepted']
    assert not result['release_promotable']
