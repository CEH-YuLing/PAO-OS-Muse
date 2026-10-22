"""Partial B2b metadata hardening; dedicated test DB/Redis15 only."""
import sys
from check_s21b2a_tests import call

if __name__=='__main__':
    # Contract validation tests compare generated schema, so export first.
    call(sys.executable,'scripts/export_openapi.py')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
        'apps/api/tests/test_model_metadata.py','apps/api/tests/test_model_router.py',
        'apps/api/tests/test_tenant_model_resources.py','apps/api/tests/test_connection_generations.py',
        'apps/api/tests/test_model_connection_fence.py','apps/api/tests/test_model_grant_activation.py',
        'apps/api/tests/test_connection_inventory.py','apps/api/tests/test_connection_grants.py',
        'apps/api/tests/test_brain_manager.py','apps/api/tests/test_brain_files.py',
        'apps/api/tests/test_brain_notes.py','apps/api/tests/test_app_factory.py')
