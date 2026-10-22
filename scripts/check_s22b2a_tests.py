"""Native read queue checkpoint; pao_test/Redis15, never live providers."""
import sys
from check_s21b2a_tests import call

if __name__=='__main__':
    call(sys.executable,'-m','alembic','upgrade','head')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
        'apps/api/tests/test_tenant_read_resources.py','apps/api/tests/test_tenant_model_resources.py',
        'apps/api/tests/test_read_queue_worker_edges.py',
        'apps/api/tests/test_connectors.py','apps/api/tests/test_meta.py','apps/api/tests/test_google_ads.py',
        'apps/api/tests/test_mcp_tenant_authority.py','apps/api/tests/test_ads_tenant_authority.py',
        'apps/api/tests/test_warehouse.py','apps/api/tests/test_warehouse_scheduler_boundary.py',
        'apps/api/tests/test_tools.py','apps/api/tests/test_connection_generations.py',
        'apps/api/tests/test_app_factory.py')
