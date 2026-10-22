"""Fail closed release summary, separate from functional/local infrastructure proof."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from pao.config import ROOT


def assess(readiness, python_audit, js_audit, python_lock, js_lock):
    python_current = (python_audit.get('audit_completed') is True
        and python_audit.get('source_image_requirements_verified') is True
        and python_audit.get('runtime_requirements_sha256') == python_lock)
    js_current = js_audit.get('package_lock_sha256') == js_lock
    python_clear=python_current and python_audit.get('runtime_clean') is True and python_audit.get('affected_packages')==[]
    reviews=[]
    if not python_clear:reviews.append('python_dependency_remediation_and_auth_fernet_regression')
    if js_audit.get('dev_review_pending'):reviews.append('dev_dependency_advisories_no_upstream_fix')
    if not readiness.get('archive_read_on_candidate_accepted'):reviews.append('archive_read_compatibility_evidence')
    reviews.append('hosted_ci_and_dedicated_production_keys_blobs_cold_restore_gates')
    return {
        'functional_local_prepared': readiness.get('local_prepared') is True,
        'production_accepted': False,
        'release_promotable': False,
        'python_audit_current': python_current,
        'python_runtime_clear': python_current and python_audit.get('runtime_clean') is True
            and python_audit.get('affected_packages') == [],
        'python_affected_packages': [p['name'] for p in python_audit.get('affected_packages', [])],
        'js_audit_current': js_current,
        'js_runtime_gate_pass': js_current and js_audit.get('runtime_gate_pass') is True,
        'js_dev_review_pending': js_audit.get('dev_review_pending') is True,
        'existing_archive_cold_restore_accepted': readiness.get('existing_archive_cold_restore_accepted') is True,
        'archive_read_on_candidate_accepted':readiness.get('archive_read_on_candidate_accepted') is True,
        'required_review':reviews,
    }


def main():
    assert ROOT.resolve() == Path('F:/PAO-ACOS')
    runtime = ROOT / '.runtime'
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    readiness = read(runtime/'phase3-readiness.json')
    ci_path = Path(readiness['ci_evidence']).resolve()
    assert ci_path.is_relative_to(runtime.resolve())
    js_audit = read(ci_path.parent/'js-security.json')
    with ZipFile(ci_path.parent/'source.zip') as archive:
        js_audit['package_lock_sha256'] = hashlib.sha256(archive.read('package-lock.json')).hexdigest()
    result = assess(readiness, read(runtime/'phase3-python-security.json'),
        js_audit, digest(ROOT/'requirements.lock'), digest(ROOT/'package-lock.json'))
    (runtime/'phase3-release-security.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    # A successful command cannot be mistaken for release permission.
    raise SystemExit(0 if result['release_promotable'] else 2)


if __name__ == '__main__':
    main()
