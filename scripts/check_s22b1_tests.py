"""Model resource checkpoint; pao_test and Redis15 only."""
import sys
from check_s21b2a_tests import call

if __name__=='__main__':
    call(sys.executable,'-m','alembic','upgrade','head')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
        'apps/api/tests/test_tenant_model_resources.py',
        'apps/api/tests/test_chat_management.py','apps/api/tests/test_engine_contract.py',
        'apps/api/tests/test_connection_generations.py','apps/api/tests/test_model_connection_fence.py',
        'apps/api/tests/test_model_grant_activation.py','apps/api/tests/test_model_router.py',
        'apps/api/tests/test_app_factory.py')
