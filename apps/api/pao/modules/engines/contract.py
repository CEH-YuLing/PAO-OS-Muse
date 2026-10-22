"""Adapter capabilities, sanitized failures and managed client streams.

These describe PAO's adapters, not every feature advertised by a model vendor.
Tool planning is structured JSON followed by the existing guarded Tool Gateway;
it is not native function calling, arbitrary shell or an authorization grant.
"""
import asyncio
from dataclasses import asdict, dataclass
from typing import AsyncIterator, Protocol

import httpx
from ...gateway import Chunk, CloudProviderError


class Engine(Protocol):
    model_name: str
    provider_name: str
    def stream(self, messages: list[dict], max_tokens: int | None = None) -> AsyncIterator[Chunk]: ...
    async def plan(self, messages: list[dict]): ...


@dataclass(frozen=True)
class Capabilities:
    text: bool = True
    tools: bool = True
    tool_mode: str = 'guarded_structured_plan'
    native_tools: bool = False
    vision: bool = False
    stream: bool = True
    cancel: str = 'client_stream'
    usage: str = 'reported_optional'


class EngineFailure(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def capabilities(provider: str) -> dict:
    if provider in ('codex_cli','muse'):
        return asdict(Capabilities(cancel='process_tree', usage='reported_optional'))
    if provider == 'knowledge':
        return asdict(Capabilities(tools=False, tool_mode='none', usage='not_applicable'))
    if provider not in ('ollama', 'openai', 'anthropic', 'gemini', 'openrouter'):
        raise EngineFailure('engine_not_supported')
    return asdict(Capabilities())


def require_capability(caps: dict, name: str):
    if caps.get(name) is not True:
        raise EngineFailure('engine_capability_denied')


def normalize(exc: Exception) -> EngineFailure:
    if isinstance(exc, EngineFailure):
        return exc
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return EngineFailure('engine_timeout')
    if isinstance(exc,CloudProviderError):
        known={'context':'engine_provider_context_exceeded','rate_limited':'engine_provider_rate_limited','authentication':'engine_provider_authentication',
               'temporary':'engine_provider_temporary'}
        if exc.kind in known:return EngineFailure(known[exc.kind])
    # Never reflect URL, response bodies, credentials or prompt data.
    return EngineFailure('engine_unavailable')


class ManagedEngine:
    def __init__(self, gateway: Engine, caps: dict):
        self.gateway, self.capabilities = gateway, caps
        self.provider_name, self.model_name = gateway.provider_name, gateway.model_name

    @property
    def last_usage(self):
        return getattr(self.gateway,'last_usage',{})

    @staticmethod
    def extraction_messages(prompt):
        from ...gateway import OllamaGateway
        return OllamaGateway.extraction_messages(prompt)

    async def extract(self, prompt):
        require_capability(self.capabilities, 'text')
        if not callable(getattr(self.gateway, 'extract', None)):
            raise EngineFailure('engine_capability_denied')
        try:
            return await self.gateway.extract(prompt)
        except Exception as exc:
            raise normalize(exc) from None

    async def plan(self, messages):
        require_capability(self.capabilities, 'tools')
        try:
            return await self.gateway.plan(messages)
        except Exception as exc:
            raise normalize(exc) from None

    async def stream(self, messages, max_tokens=None):
        require_capability(self.capabilities, 'text')
        require_capability(self.capabilities, 'stream')
        source = self.gateway.stream(messages, max_tokens=max_tokens)
        try:
            async for chunk in source:
                # An absent usage report is unknown, never zero. P3.7 adds ledger.
                yield chunk
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise normalize(exc) from None
        finally:
            close = getattr(source, 'aclose', None)
            if close:
                await close()
