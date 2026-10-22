"""FastAPI composition boundary; importing this module does not create an app."""
from contextlib import asynccontextmanager
from importlib import import_module

from fastapi import FastAPI


# Keep registration order stable for OpenAPI operation IDs and route precedence.
ROUTER_SPECS = (
    (".core_api", "router"),
    (".memory_api", "router"),
    (".agent_api", "router"),
    (".tool_api", "router"),
    (".telegram", "router"),
    (".integrations.meta.api", "router"),
    (".integrations.google_ads.api", "router"),
    (".warehouse_api", "router"),
    (".report_api", "router"),
    (".intelligence_api", "router"),
    (".ads_action_api", "router"),
    (".ads_action_api", "approval_router"),
    (".ads_policy_api", "router"),
    (".creative_api", "router"),
    (".attribution_api", "router"),
    (".automation_api", "router"),
    (".voice_api", "router"),
    (".task_api", "router"),
    (".platform_api", "router"),
    (".model_api", "router"),
    (".skill_api", "router"),
    (".modules.brains.api", "router"),
    (".modules.brains.files", "router"),
    (".modules.brains.notes", "router"),
    (".modules.brains.portable", "router"),
    (".modules.knowledge.api", "router"),
    (".modules.knowledge.workspace_api", "router"),
    (".modules.knowledge.conversations", "router"),
    (".modules.engines.api", "router"),
    (".modules.chat.api", "router"),
    (".modules.studio.api", "router"),
    (".modules.connectors.api", "router"),
    (".modules.events.api", "router"),
    (".modules.goals.api", "router"),
    (".modules.schedules.api", "router"),
    (".modules.business.outcomes", "router"),
    (".modules.results.api", "router"),
    (".modules.learning.api", "router"),
    (".modules.goals.runner_api", "router"),
    (".modules.channels.api", "router"),
    (".modules.channels.telegram_transport", "router"),
    (".modules.channels.telegram_setup_api", "router"),
    (".modules.channels.voice_turns", "router"),
    (".modules.connections.api", "router"),
    (".modules.connections.resources_api", "router"),
    (".modules.business_planning.api", "router"),
    (".modules.platform.lifecycle", "router"),
    (".modules.platform.organization", "router"),
    (".modules.studio.organization", "router"),
    (".modules.cli_connections.api", "router"),
    (".modules.cli_connections.personal_api", "router"),
    (".modules.cli_connections.model_api", "router"),
    (".modules.connections.enterprise_api", "router"),
    (".modules.installation_ai.api", "router"),
    (".modules.cli_connections.antigravity_native", "router"),
    (".modules.cli_connections.muse_client", "router"),
)


@asynccontextmanager
async def lifespan(app):
    # Runtime resources belong to this app's lifespan, not the import/factory.
    from arq import create_pool
    from arq.connections import RedisSettings
    from .config import settings

    redis = await create_pool(RedisSettings.from_dsn(settings().redis_url))
    app.state.redis = redis
    from .modules.cli_connections.login_manager import LoginManager
    app.state.cli_logins = LoginManager()
    try:
        yield
    finally:
        await app.state.cli_logins.close()
        from .modules.cli_connections.muse_profile import cancel_login
        await cancel_login()
        await redis.aclose()


def create_app() -> FastAPI:
    """Compose a fresh application without opening database/provider connections.

    Router imports retain existing config/ORM/registry initialization; removing
    those import-time initializations is a separate checkpoint.
    """
    app = FastAPI(title="PAO Local API", version="0.1.0", lifespan=lifespan)
    from .modules.operations.request_trace import RequestTrace, configure
    from .modules.brains.validation import BrainBodyLimit
    configure()
    app.add_middleware(BrainBodyLimit)
    app.add_middleware(RequestTrace)
    from fastapi.exceptions import RequestValidationError
    from .modules.brains.validation import safe_validation
    app.add_exception_handler(RequestValidationError,safe_validation)
    for module_name, attribute in ROUTER_SPECS:
        module = import_module(module_name, package=__package__)
        app.include_router(getattr(module, attribute))

    from .schemas import EventOut
    original_openapi = app.openapi

    def openapi():
        schema = original_openapi()
        schema.setdefault("components", {}).setdefault("schemas", {})[
            "RunEvent"
        ] = EventOut.model_json_schema()
        return schema

    app.openapi = openapi
    return app
