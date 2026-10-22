"""Metadata admission/source fences; pao_test and Redis15, no live providers."""
import sys
from check_s21b2a_tests import call

if __name__=='__main__':
    call(sys.executable,'scripts/export_openapi.py')
    call(sys.executable,'-m','alembic','upgrade','head')
    call(sys.executable,'-m','alembic','check')
    call(sys.executable,'-m','pytest','-q','--tb=short','--show-capture=no',
        'apps/api/tests/test_knowledge_embedding_resources.py','apps/api/tests/test_knowledge_workspace.py',
        'apps/api/tests/test_knowledge_sources.py','apps/api/tests/test_brain_scopes.py',
        'apps/api/tests/test_embedding_resources.py','apps/api/tests/test_gateway.py',
        'apps/api/tests/test_legacy_accounting_fence.py','apps/api/tests/test_memory.py','apps/api/tests/test_chat_management.py',
        'apps/api/tests/test_local_metadata_resources.py','apps/api/tests/test_engine_contract.py',
        'apps/api/tests/test_metadata_credentials.py',
        'apps/api/tests/test_tenant_metadata_resources.py','apps/api/tests/test_model_metadata.py',
        'apps/api/tests/test_connectors.py','apps/api/tests/test_model_router.py',
        'apps/api/tests/test_tenant_model_resources.py','apps/api/tests/test_tenant_read_resources.py',
        'apps/api/tests/test_connection_generations.py','apps/api/tests/test_mcp_tenant_authority.py',
        'apps/api/tests/test_model_connection_fence.py','apps/api/tests/test_model_grant_activation.py',
        'apps/api/tests/test_app_factory.py')
