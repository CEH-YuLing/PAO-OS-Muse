"""Secret-free CLI contracts, independent of PAO settings, database and SDKs.

A scope is an identity tuple, NOT an authorization grant. The future serving
adapter must resolve it from native services and recheck it at dispatch/delivery.
Provider auth, inference, tool permissions and commercial eligibility are separate.
"""
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class CliProvider(StrEnum):
    CODEX = 'codex_cli'
    CLAUDE = 'claude_code_cli'
    ANTIGRAVITY = 'antigravity_cli'


class CliFailure(RuntimeError):
    def __init__(self, code: str):
        # Never accept an exception/provider body as a public failure code.
        if code not in ERROR_CODES:
            code = 'cli_internal_error'
        self.code = code
        super().__init__(code)


ERROR_CODES = frozenset({
    'cli_contract_invalid', 'cli_access_denied', 'cli_scope_mismatch',
    'cli_external_disabled', 'cli_fixture_invalid', 'cli_runtime_path_invalid',
    'cli_process_start_failed', 'cli_process_failed', 'cli_timeout',
    'cli_input_limit', 'cli_output_limit', 'cli_protocol_invalid', 'cli_incomplete',
    'cli_profile_busy', 'cli_attempt_already_dispatched', 'cli_capacity',
    'cli_cleanup_failed', 'cli_process_isolation_failed', 'cli_internal_error',
    'cli_tool_event_denied', 'cli_provider_failed', 'cli_binary_changed',
    'cli_binary_unsupported', 'cli_native_bridge_pending',
    'cli_runtime_not_provisioned', 'cli_docker_failed', 'cli_profile_binding_invalid',
})


def _uuid(value):
    if not isinstance(value, str):
        raise CliFailure('cli_contract_invalid')
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise CliFailure('cli_contract_invalid') from None


@dataclass(frozen=True)
class CliScope:
    workspace_id: str
    actor_id: str
    connection_id: str
    profile_id: str
    device_id: str
    brand_id: str | None = None

    def __post_init__(self):
        for value in (self.workspace_id, self.actor_id, self.connection_id, self.profile_id, self.device_id):
            _uuid(value)
        if self.brand_id is not None:
            _uuid(self.brand_id)


@dataclass(frozen=True)
class Limits:
    timeout_seconds: float = 10.0
    max_input_bytes: int = 65536
    max_output_bytes: int = 262144
    max_line_bytes: int = 32768

    def __post_init__(self):
        import math
        if (type(self.timeout_seconds) not in (float, int)
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120):
            raise CliFailure('cli_contract_invalid')
        for value in (self.max_input_bytes, self.max_output_bytes, self.max_line_bytes):
            if type(value) is not int or not 64 <= value <= 1048576:
                raise CliFailure('cli_contract_invalid')
        if self.max_line_bytes > self.max_output_bytes:
            raise CliFailure('cli_contract_invalid')


@dataclass(frozen=True)
class CliRequest:
    provider: CliProvider
    scope: CliScope
    attempt_id: str
    prompt: str = field(repr=False)
    model: str = 'fixture-only'
    limits: Limits = field(default_factory=Limits)

    def __post_init__(self):
        if not isinstance(self.provider, CliProvider) or not isinstance(self.scope, CliScope) or not isinstance(self.limits, Limits):
            raise CliFailure('cli_contract_invalid')
        _uuid(self.attempt_id)
        if not isinstance(self.model, str) or not self.model or len(self.model) > 120 or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in self.model):
            raise CliFailure('cli_contract_invalid')
        if not isinstance(self.prompt, str) or not self.prompt or '\x00' in self.prompt:
            raise CliFailure('cli_contract_invalid')
        try:
            size = len(self.prompt.encode('utf-8'))
        except UnicodeError:
            raise CliFailure('cli_contract_invalid') from None
        if size > self.limits.max_input_bytes:
            raise CliFailure('cli_input_limit')


@dataclass(frozen=True)
class Outcome:
    text: str = field(repr=False)
    input_tokens: int | None = None
    output_tokens: int | None = None
    mode: str = 'offline_fixture'
    provider_inference_verified: bool = False


# These are preparation metadata, not installed version/entitlement claims.
PROVIDERS = {
    CliProvider.CODEX: {'binary': 'codex', 'transport': 'exec_json_candidate', 'live_enabled': False},
    CliProvider.CLAUDE: {'binary': 'claude', 'transport': 'cli_or_sdk_evaluation_pending', 'live_enabled': False},
    CliProvider.ANTIGRAVITY: {'binary': 'agy', 'transport': 'stream_json_candidate', 'live_enabled': False},
}


def external_dispatch(*_args, **_kwargs):
    """No boolean feature flag, caller-supplied command or auth token bypass."""
    raise CliFailure('cli_external_disabled')
