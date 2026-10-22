"""MCP authority and affected regressions; only pao_test / Redis15."""
import sys
from check_s21b2a_tests import call

if __name__=='__main__':
    call(sys.executable,'-m','alembic','upgrade','head')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
         'apps/api/tests/test_mcp_tenant_authority.py','apps/api/tests/test_connectors.py',
         'apps/api/tests/test_connection_grants.py','apps/api/tests/test_connection_inventory.py',
         'apps/api/tests/test_model_grant_activation.py','apps/api/tests/test_model_connection_fence.py',
         'apps/api/tests/test_studio.py','apps/api/tests/test_studio_connection_recovery.py',
         'apps/api/tests/test_tools.py','apps/api/tests/test_app_factory.py')
