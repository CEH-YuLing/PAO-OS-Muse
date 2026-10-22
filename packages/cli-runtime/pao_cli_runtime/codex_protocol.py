"""Codex exec JSONL parser and inert invocation preparation.

Streaming granularity is complete agent messages, not assumed token deltas.
These events are untrusted input. Tool events invalidate the result, but this
does NOT undo/prevent a tool that ran: isolation is a prerequisite to launch.
No provider session resume, credential reading or inference is implemented here.
"""
from dataclasses import dataclass, field
import json
import re
from uuid import UUID

from .codex_probe import CodexBinary
from .contracts import CliFailure, CliProvider, CliRequest, Limits, Outcome
from .transport import _directory

REQUIRED_FLAGS = frozenset({'--json', '--ephemeral', '--ignore-user-config', '--ignore-rules',
                            '--skip-git-repo-check', '--sandbox', '--ask-for-approval', '--strict-config', '--color'})


def json_object(raw):
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
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CliFailure('cli_protocol_invalid') from None


class CodexExecParser:
    def __init__(self, limits):
        if not isinstance(limits, Limits):
            raise CliFailure('cli_contract_invalid')
        self.limits = limits
        self._buffer = b''
        self._bytes = 0
        self._thread = False
        self._started = False
        self._completed = False
        self._failed = False
        self._messages = []
        self._items = set()
        self._item_types = {}
        self._finished = False
        self._usage = None

    def feed(self, data: bytes):
        """Accept arbitrary byte boundaries, return newly completed messages."""
        if self._failed or self._finished:
            raise CliFailure('cli_protocol_invalid')
        try:
            if not isinstance(data, bytes):
                raise CliFailure('cli_protocol_invalid')
            self._bytes += len(data)
            if self._bytes > self.limits.max_output_bytes:
                raise CliFailure('cli_output_limit')
            self._buffer += data
            delivered = []
            while b'\n' in self._buffer:
                line, self._buffer = self._buffer.split(b'\n', 1)
                if not line or len(line) > self.limits.max_line_bytes:
                    raise CliFailure('cli_output_limit' if line else 'cli_protocol_invalid')
                try:
                    event = json_object(line.decode('utf-8'))
                except UnicodeError:
                    raise CliFailure('cli_protocol_invalid') from None
                message = self._event(event)
                if message is not None:
                    delivered.append(message)
            if len(self._buffer) > self.limits.max_line_bytes:
                raise CliFailure('cli_output_limit')
            return delivered
        except CliFailure:
            self._failed = True
            raise

    def _event(self, event):
        kind = event.get('type')
        if self._completed:
            raise CliFailure('cli_protocol_invalid')
        if kind in ('error', 'turn.failed'):
            raise CliFailure('cli_provider_failed')
        if kind == 'thread.started':
            if self._thread or self._started:
                raise CliFailure('cli_protocol_invalid')
            try:
                if str(UUID(event['thread_id'])) != event['thread_id']:
                    raise ValueError()
            except (ValueError, TypeError, KeyError, AttributeError):
                raise CliFailure('cli_protocol_invalid') from None
            self._thread = True
        elif kind == 'turn.started':
            if not self._thread or self._started:
                raise CliFailure('cli_protocol_invalid')
            self._started = True
        elif kind in ('item.started', 'item.updated', 'item.completed'):
            if not self._started or not isinstance(event.get('item'), dict):
                raise CliFailure('cli_protocol_invalid')
            item = event['item']
            if item.get('type') not in ('agent_message', 'reasoning'):
                raise CliFailure('cli_tool_event_denied')
            key = item.get('id')
            if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', key) or key in self._items:
                raise CliFailure('cli_protocol_invalid')
            if key in self._item_types and self._item_types[key] != item['type']:
                raise CliFailure('cli_protocol_invalid')
            self._item_types[key] = item['type']
            if kind == 'item.completed':
                self._items.add(key)
                if item['type'] == 'agent_message':
                    if not isinstance(item.get('text'), str):
                        raise CliFailure('cli_protocol_invalid')
                    self._messages.append(item['text'])
                    return item['text']
            # Never disclose or store reasoning text/partial scratchpad.
        elif kind == 'turn.completed':
            if not self._started:
                raise CliFailure('cli_protocol_invalid')
            usage = event.get('usage')
            if usage is not None:
                if (not isinstance(usage, dict) or not {'input_tokens', 'output_tokens'} <= usage.keys()
                        or any(type(n) is not int or not 0 <= n <= 10**9 for n in usage.values())
                        or usage.get('cached_input_tokens', 0) > usage['input_tokens']):
                    raise CliFailure('cli_protocol_invalid')
                self._usage = {key: usage[key] for key in ('input_tokens', 'output_tokens')}
            self._completed = True
        else:
            raise CliFailure('cli_protocol_invalid')

    def finish(self, returncode):
        if self._failed or self._finished:
            raise CliFailure('cli_protocol_invalid')
        if type(returncode) is not int or returncode != 0:
            self._failed = True
            raise CliFailure('cli_process_failed')
        if self._buffer or not self._completed or not ''.join(self._messages).strip():
            self._failed = True
            raise CliFailure('cli_incomplete')
        # Provider attribution is NOT verified by a parser/fixture. The future
        # admitted transport records actual inference separately in native ledger.
        self._finished = True
        return Outcome(''.join(self._messages), **(self._usage or {}), mode='codex_exec_parsed_unverified')


@dataclass(frozen=True)
class CodexDraft:
    """Preview only. No method here can spawn an inference process."""
    argv: tuple[str, ...] = field(repr=False)
    stdin: bytes = field(repr=False)
    model: str
    attempt_id: str
    binary_sha256: str
    live_dispatch_allowed: bool = field(default=False, init=False)


def prepare(request: CliRequest, binary: CodexBinary, workdir):
    if (not isinstance(request, CliRequest) or not isinstance(binary, CodexBinary)
            or request.provider != CliProvider.CODEX
            or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/+-]{0,119}', request.model)):
        raise CliFailure('cli_contract_invalid')
    binary.check()
    if not REQUIRED_FLAGS <= binary.flags:
        raise CliFailure('cli_binary_unsupported')
    folder = _directory(workdir)
    # This is defence-in-depth configuration, not an OS isolation certificate.
    config = ('model_provider="openai"', 'features.shell_tool=false', 'features.apps=false', 'web_search="disabled"',
              'features.multi_agent=false', 'features.goals=false', 'features.hooks=false',
              'features.plugins=false', 'features.memories=false', 'features.view_image=false',
              'features.sleep_tool=false', 'features.browser_use=false', 'features.computer_use=false',
              'features.unbounded_connection_retries=false',
              'cli_auth_credentials_store="file"', 'project_doc_max_bytes=0', 'allow_login_shell=false')
    argv = [binary.path, '--strict-config', '--sandbox', 'read-only', '--ask-for-approval', 'never']
    for value in config:
        argv += ['-c', value]
    argv += ['exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
             '--skip-git-repo-check', '--color', 'never', '--cd', str(folder), '--model', request.model, '-']
    return CodexDraft(tuple(argv), request.prompt.encode('utf-8'), request.model, request.attempt_id, binary.sha256)


def dispatch(*_args, **_kwargs):
    # Deliberately impossible to turn a preview into authorization with a bool,
    # a copied API key/grant, caller-supplied proof or an environment toggle.
    raise CliFailure('cli_native_bridge_pending')
