"""Request correlation with an allowlisted log schema; never log raw URLs/body."""
import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from ipaddress import ip_address
from uuid import UUID, uuid4
from starlette.routing import Route

LOGGER = logging.getLogger('pao.request')
_CONTEXT = ContextVar('pao_request_trace', default=None)


def bind_actor(actor_id):
    """Only call after authentication/session checks; never accept a header ID."""
    context = _CONTEXT.get()
    if context is not None:
        try:
            context['actor_id'] = str(UUID(str(actor_id)))
        except (ValueError, TypeError, AttributeError):
            pass


def bind_workspace(workspace_id):
    """Only call after membership checks, including the required write role."""
    context = _CONTEXT.get()
    if context is not None:
        try:
            value = str(UUID(str(workspace_id)))
        except (ValueError, TypeError, AttributeError):
            return
        # Do not misattribute a multi-workspace request to the last workspace.
        if context['workspace_id'] is None and not context['multiple_workspaces']:
            context['workspace_id'] = value
        elif context['workspace_id'] != value:
            context.update(workspace_id=None, multiple_workspaces=True)


def route_template(scope):
    route = scope.get('route')
    # Matched server route only: never fall back to path, URL or query string.
    value = route.path if isinstance(route, Route) else None
    return value if isinstance(value, str) and len(value) <= 240 and not any(ord(c) < 32 for c in value) else None


def client_ip(scope):
    try:
        return str(ip_address(scope['client'][0]))
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def configure():
    if not any(getattr(h, '_pao_safe', False) for h in LOGGER.handlers):
        handler = logging.StreamHandler()
        handler._pao_safe = True
        handler.setFormatter(logging.Formatter('%(message)s'))
        LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)


class RequestTrace:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid4().hex  # Do not trust a user-supplied correlation header.
        started_at = datetime.now(timezone.utc).isoformat()
        context = {'actor_id': None, 'workspace_id': None, 'multiple_workspaces': False}
        token = _CONTEXT.set(context)
        started = time.monotonic()
        status = 500
        async def traced_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = [(k,v) for k,v in message.get('headers',[])
                           if k.lower() != b'x-request-id']
                message = {**message, 'headers': headers + [(b'x-request-id', request_id.encode())]}
            await send(message)
        try:
            await self.app(scope, receive, traced_send)
        finally:
            try:
                # No raw path/query/header/body/exception or credential values.
                method = scope.get('method', '')
                if method not in ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'):
                    method = 'OTHER'
                LOGGER.info(json.dumps({'event':'http.request','request_id':request_id,
                    'started_at':started_at, 'timestamp':datetime.now(timezone.utc).isoformat(),
                    'route':route_template(scope), 'client_ip':client_ip(scope),
                    # Upstream ASGI servers may apply proxy trust policy. This is
                    # NOT a verified physical peer, person, browser or OS PID.
                    'client_source':'asgi_scope', **context,
                    'method':method,'status':status,
                    'duration_ms':round((time.monotonic()-started)*1000,2)},sort_keys=True))
            finally:
                _CONTEXT.reset(token)
