"""Strict, offline text-only protocol subset for EA3 evaluation.

These parsers do not launch CLIs, authenticate, read profiles or confer tool
permission. Detecting a tool event cannot prevent/undo an action on a real host.
OS isolation, official auth eligibility and native accounting remain live gates.
Output is released only at finish, after the entire one-turn stream validates.
"""
from dataclasses import dataclass, field
import json
import re
from uuid import UUID

ERRORS = frozenset({'adapter_contract_invalid', 'adapter_protocol_invalid',
    'adapter_output_limit', 'adapter_incomplete', 'adapter_process_failed',
    'adapter_provider_failed', 'adapter_tool_denied', 'adapter_session_mismatch',
    'adapter_model_mismatch', 'adapter_live_disabled'})


class AdapterFailure(RuntimeError):
    def __init__(self, code):
        self.code = code if code in ERRORS else 'adapter_protocol_invalid'
        super().__init__(self.code)


@dataclass(frozen=True)
class Limits:
    max_bytes: int = 262144
    max_line_bytes: int = 65536
    max_events: int = 2048

    def __post_init__(self):
        if (any(type(v) is not int for v in (self.max_bytes, self.max_line_bytes, self.max_events))
                or not 64 <= self.max_line_bytes <= self.max_bytes <= 1048576
                or not 1 <= self.max_events <= 10000):
            raise AdapterFailure('adapter_contract_invalid')


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_creation_tokens: int | None = None
    thinking_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def state(self):
        return 'reported' if self.input_tokens is not None and self.output_tokens is not None else 'unknown'


@dataclass(frozen=True)
class Result:
    provider: str
    model: str
    text: str = field(repr=False)
    usage: Usage
    mode: str = field(default='ea3_offline_parsed_unverified', init=False)
    provider_inference_verified: bool = field(default=False, init=False)


def _require(condition, code='adapter_protocol_invalid'):
    if not condition:
        raise AdapterFailure(code)


def _uuid(value):
    try:
        _require(isinstance(value, str) and str(UUID(value)) == value)
    except (ValueError, TypeError, AttributeError):
        raise AdapterFailure('adapter_protocol_invalid') from None
    return value


def _object(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError()
            value[key] = item
        return value
    def constant(_):
        raise ValueError()
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=constant)
        _require(isinstance(value, dict))
        # Escaped lone surrogates are valid JSON syntax but not valid UTF-8 text.
        # Reject them even when hidden in ignored metadata, before publication.
        json.dumps(value, ensure_ascii=False).encode('utf-8')
        return value
    except (ValueError, UnicodeError, TypeError, RecursionError):
        raise AdapterFailure('adapter_protocol_invalid') from None


def _usage(value, provider):
    if value is None:
        return Usage()
    _require(isinstance(value, dict))
    mapping = {'input_tokens':'input_tokens', 'output_tokens':'output_tokens',
        'cache_read_tokens':'cache_read_input_tokens' if provider == 'claude_code_cli' else 'cache_read_tokens',
        'cache_creation_tokens':'cache_creation_input_tokens', 'thinking_tokens':'thinking_tokens', 'total_tokens':'total_tokens'}
    numbers = {}
    for target, source in mapping.items():
        n = value.get(source)
        _require(n is None or type(n) is int and 0 <= n <= 10**9)
        numbers[target] = n
    # Keep cache/thinking separately; do not invent comparable totals or money.
    return Usage(**numbers)


class _Stream:
    provider = ''

    def __init__(self, expected_model, limits=None):
        self.limits = Limits() if limits is None else limits
        _require(isinstance(self.limits, Limits), 'adapter_contract_invalid')
        _require(isinstance(expected_model, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+-]{0,119}', expected_model), 'adapter_contract_invalid')
        self.model = expected_model
        self._buffer = b''
        self._bytes = self._events = 0
        self._session = None
        self._done = self._failed = self._finished = False
        self._text = ''
        self._usage = Usage()

    def feed(self, data):
        _require(not self._failed and not self._finished)
        try:
            _require(isinstance(data, bytes))
            self._bytes += len(data)
            _require(self._bytes <= self.limits.max_bytes, 'adapter_output_limit')
            self._buffer += data
            while b'\n' in self._buffer:
                raw, self._buffer = self._buffer.split(b'\n', 1)
                _require(0 < len(raw) <= self.limits.max_line_bytes, 'adapter_output_limit')
                _require(not self._done)
                self._events += 1
                _require(self._events <= self.limits.max_events, 'adapter_output_limit')
                self._event(_object(raw))
            _require(len(self._buffer) <= self.limits.max_line_bytes, 'adapter_output_limit')
        except AdapterFailure:
            self._failed = True
            raise
        # No partially validated text, raw init metadata, reasoning or error body.
        return None

    def _bind(self, value):
        sid = _uuid(value)
        if self._session is None:
            self._session = sid
        else:
            _require(sid == self._session, 'adapter_session_mismatch')

    def finish(self, exit_code):
        _require(not self._failed and not self._finished)
        try:
            _require(type(exit_code) is int and exit_code == 0, 'adapter_process_failed')
            _require(self._done and not self._buffer and self._text.strip(), 'adapter_incomplete')
        except AdapterFailure:
            self._failed = True
            raise
        self._finished = True
        return Result(self.provider, self.model, self._text, self._usage)


class ClaudeStream(_Stream):
    """One init, zero-or-more plain-text assistant messages, one result.

    Deliberately rejects partial-message/reasoning/background/hook/retry shapes
    not validated by this candidate. Actual CLI compatibility remains unverified.
    """
    provider = 'claude_code_cli'

    def _event(self, value):
        kind = value.get('type')
        if self._session is None:
            _require(kind == 'system' and value.get('subtype') == 'init')
            self._bind(value.get('session_id'))
            _require(value.get('model') == self.model, 'adapter_model_mismatch')
            _require(value.get('tools') == [] and value.get('mcp_servers') == []
                     and value.get('plugins', []) == [], 'adapter_tool_denied')
            return
        self._bind(value.get('session_id'))
        if kind == 'assistant':
            _require(value.get('parent_tool_use_id') is None, 'adapter_tool_denied')
            message = value.get('message')
            _require(isinstance(message, dict))
            _require(message.get('model') == self.model, 'adapter_model_mismatch')
            _require(message.get('role') == 'assistant')
            blocks = message.get('content')
            _require(isinstance(blocks, list) and bool(blocks))
            for block in blocks:
                _require(isinstance(block, dict) and block.get('type') == 'text', 'adapter_tool_denied')
                _require(isinstance(block.get('text'), str))
                self._text += block['text']
        elif kind == 'result':
            _require(value.get('subtype') == 'success' and value.get('is_error') is False,
                     'adapter_provider_failed')
            _require(type(value.get('num_turns')) is int and value['num_turns'] == 1)
            _require(not value.get('permission_denials'), 'adapter_tool_denied')
            text = value.get('result')
            _require(isinstance(text, str) and bool(text.strip()))
            _require(not self._text or self._text == text)
            self._text = text
            self._usage = _usage(value.get('usage'), self.provider)
            self._done = True
        elif kind == 'system' and value.get('subtype') == 'api_retry':
            raise AdapterFailure('adapter_provider_failed')
        else:
            raise AdapterFailure('adapter_protocol_invalid')


class AntigravityStream(_Stream):
    """One new conversation only. Per-step usage is never double-counted."""
    provider = 'antigravity_cli'

    def __init__(self, expected_model, limits=None):
        super().__init__(expected_model, limits)
        self._steps = {}
        self._last_step = -1

    def _event(self, value):
        kind = value.get('event')
        if self._session is None:
            _require(kind == 'init')
            self._bind(value.get('conversation_id'))
            init = value.get('init')
            _require(isinstance(init, dict))
            _require(init.get('model') == self.model, 'adapter_model_mismatch')
            _require(init.get('tools') == [] and init.get('permission_mode') == 'request-review',
                     'adapter_tool_denied')
            return
        if kind == 'step_update':
            step = value.get('step_update')
            _require(isinstance(step, dict))
            self._bind(step.get('conversation_id'))
            _require(step.get('step_type') in ('user_input', 'agent_response', 'checkpoint')
                     and not step.get('tool_info') and not step.get('tool_name')
                     and not step.get('subagent_info'), 'adapter_tool_denied')
            index = step.get('step_index')
            state = step.get('state')
            _require(type(index) is int and index >= self._last_step and state in ('ACTIVE', 'DONE'))
            old = self._steps.get(index)
            _require(old is None or old == (step['step_type'], 'ACTIVE'))
            _require(index == self._last_step or all(v[1] == 'DONE' for v in self._steps.values()))
            self._steps[index] = (step['step_type'], state)
            self._last_step = index
            delta = step.get('text_delta', '')
            _require(isinstance(delta, str))
            _require(step['step_type'] == 'agent_response' or delta == '')
            self._text += delta
        elif kind == 'result':
            result = value.get('result')
            _require(isinstance(result, dict))
            self._bind(result.get('conversation_id'))
            _require(result.get('status') == 'SUCCESS' and not result.get('error'), 'adapter_provider_failed')
            _require(type(result.get('num_turns')) is int and result['num_turns'] == 1)
            _require(all(v[1] == 'DONE' for v in self._steps.values()))
            text = result.get('response')
            _require(isinstance(text, str) and bool(text.strip()))
            _require(not self._text or self._text == text)
            self._text = text
            self._usage = _usage(result.get('usage'), self.provider)
            self._done = True
        else:
            raise AdapterFailure('adapter_protocol_invalid')


def external_dispatch(*_args, **_kwargs):
    """No auth/launch escape hatch; this is not an execution adapter."""
    raise AdapterFailure('adapter_live_disabled')
