"""Only test DB / Redis15; no source runtime changes."""
import sys
from check_s21b2a_tests import call

if __name__=='__main__':
    call(sys.executable,'-m','alembic','upgrade','head')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
         'apps/api/tests/test_ads_tenant_authority.py','apps/api/tests/test_meta.py',
         'apps/api/tests/test_google_ads.py','apps/api/tests/test_connection_grants.py',
         'apps/api/tests/test_connection_inventory.py','apps/api/tests/test_mcp_tenant_authority.py',
         'apps/api/tests/test_ads_actions.py','apps/api/tests/test_warehouse.py',
         'apps/api/tests/test_intelligence.py','apps/api/tests/test_creative_intelligence.py',
         'apps/api/tests/test_warehouse_scheduler_boundary.py','apps/api/tests/test_report_scheduler_boundary.py',
         'apps/api/tests/test_app_factory.py')
