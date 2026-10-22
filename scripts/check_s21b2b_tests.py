"""Only pao_test / Redis15; model activation and affected integration corpus."""
import sys
from check_s21b2a_tests import call

if __name__ == '__main__':
    if '--browser-only' in sys.argv:
        call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
             'apps/api/tests/s21b2b_browser_acceptance.py')
        raise SystemExit(0)
    call(sys.executable,'-m','alembic','upgrade','head')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
         'apps/api/tests/test_model_grant_activation.py',
         'apps/api/tests/test_model_connection_fence.py',
         'apps/api/tests/test_connection_grants.py','apps/api/tests/test_connection_inventory.py',
         'apps/api/tests/test_engine_contract.py','apps/api/tests/test_model_router.py',
         'apps/api/tests/test_memory.py','apps/api/tests/test_chat_management.py',
         'apps/api/tests/test_studio.py','apps/api/tests/test_studio_connection_recovery.py',
         'apps/api/tests/test_app_factory.py')
