"""Compatibility entrypoint retained for uvicorn, scripts and existing tests."""
from .app import create_app, lifespan

app = create_app()

# Preserve access to legacy handler symbols; routes now live in core_api.
from .core_api import (
    cancel,
    create_run,
    create_session,
    delete_session,
    events,
    get_run,
    get_session,
    health,
    list_sessions,
    login,
    me,
    ready,
)

# Preserve the callable OpenAPI alias for existing inspection tools.
openapi = app.openapi
