"""Offline parser/preview tests; no binary launch, DB, credentials or network."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.contracts import CliFailure, CliProvider, CliRequest, CliScope, Limits
from pao_cli_runtime.codex_probe import CodexBinary
from pao_cli_runtime.codex_protocol import CodexExecParser, REQUIRED_FLAGS, dispatch, json_object, prepare


def start():
    return [{'type': 'thread.started', 'thread_id': str(uuid4())}, {'type': 'turn.started'}]


def message(text='Xin chào Việt Nam', key='item_1', kind='agent_message'):
    return {'type': 'item.completed', 'item': {'id': key, 'type': kind, 'text': text}}


def complete(**extra):
    return {'type': 'turn.completed', **extra}


def lines(events):
    return ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events).encode()


class ProtocolTests(unittest.TestCase):
    def parser(self, events=None, limits=None):
        parser = CodexExecParser(limits or Limits())
        if events is not None:
            parser.feed(lines(events))
        return parser

    def denied(self, events, code='cli_protocol_invalid'):
        with self.assertRaisesRegex(CliFailure, '^' + code + '$'):
            self.parser(events)

    def test_realistic_event_shape_and_reported_usage(self):
        result = self.parser([*start(), message(), complete(usage={'input_tokens': 10,
            'cached_input_tokens': 5, 'output_tokens': 3, 'reasoning_output_tokens': 1})]).finish(0)
        self.assertEqual(result.text, 'Xin chào Việt Nam')
        self.assertEqual((result.input_tokens, result.output_tokens), (10, 3))
        self.assertFalse(result.provider_inference_verified)

    def test_arbitrary_utf8_byte_boundaries(self):
        raw = lines([*start(), message(), complete()])
        for step in (1, 2, 3, 7, 64, len(raw)):
            with self.subTest(step=step):
                parser = self.parser()
                output = []
                for offset in range(0, len(raw), step):
                    output += parser.feed(raw[offset:offset + step])
                self.assertEqual(output, ['Xin chào Việt Nam'])
                self.assertEqual(parser.finish(0).text, output[0])

    def test_unknown_usage_is_not_zero(self):
        for end in (complete(), complete(usage=None)):
            result = self.parser([*start(), message(), end]).finish(0)
            self.assertIsNone(result.input_tokens)
            self.assertIsNone(result.output_tokens)

    def test_reasoning_and_partial_text_not_delivered(self):
        parser = self.parser(start())
        reasoning = message('SECRET_REASONING', 'reason_0', 'reasoning')
        self.assertEqual(parser.feed(lines([reasoning])), [])
        partial = {'type': 'item.updated', 'item': {'id': 'item_1', 'type': 'agent_message', 'text': 'PARTIAL'}}
        self.assertEqual(parser.feed(lines([partial])), [])
        self.assertEqual(parser.feed(lines([message(), complete()])), ['Xin chào Việt Nam'])
        self.assertNotIn('SECRET', parser.finish(0).text)

    def test_tool_events_are_rejected(self):
        for kind in ('command_execution', 'mcp_tool_call', 'web_search', 'file_change', 'plan', 'future_tool'):
            for event in ('item.started', 'item.updated', 'item.completed'):
                with self.subTest(kind=kind, event=event):
                    tool = message('SECRET', kind=kind)
                    tool['type'] = event
                    self.denied([*start(), tool], 'cli_tool_event_denied')

    def test_provider_errors_are_redacted(self):
        for event in ('error', 'turn.failed'):
            self.denied([*start(), {'type': event, 'message': 'SECRET_TOKEN'}], 'cli_provider_failed')

    def test_sequence_and_identifiers(self):
        thread, turn = start()
        for events in ([turn], [message()], [complete()], [thread, thread],
                       [thread, turn, turn], [*start(), message(), message()],
                       [*start(), message(), complete(), complete()],
                       [{'type': 'thread.started', 'thread_id': 'not-an-id'}],
                       [*start(), {'type': 'new.unknown'}]):
            with self.subTest(events=events):
                self.denied(events)

    def test_item_type_drift_rejected(self):
        self.denied([*start(), {'type': 'item.started', 'item': {'id': 'x', 'type': 'reasoning'}},
                     message('x', 'x')])

    def test_bad_items(self):
        for item in (None, [], {'id': '', 'type': 'agent_message'},
                     {'id': 'x', 'type': 'agent_message', 'text': None},
                     {'id': 'bad id', 'type': 'agent_message', 'text': 'x'}):
            self.denied([*start(), {'type': 'item.completed', 'item': item}])

    def test_usage_validation(self):
        for usage in ([], {}, {'input_tokens': True, 'output_tokens': 1},
                      {'input_tokens': 1, 'output_tokens': -1}, {'input_tokens': 1.0, 'output_tokens': 2},
                      {'input_tokens': 1, 'output_tokens': 2, 'cached_input_tokens': 2},
                      {'input_tokens': 1, 'output_tokens': 10**10}):
            with self.subTest(usage=usage):
                self.denied([*start(), message(), complete(usage=usage)])

    def test_malformed_json_and_duplicate_keys(self):
        for raw in ('[]', 'null', '{}{}', '{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{'):
            with self.subTest(raw=raw), self.assertRaises(CliFailure):
                json_object(raw)

    def test_bad_utf8_and_empty_lines(self):
        for raw in (b'\xff\n', b'\n', b'not-json\n'):
            with self.subTest(raw=raw), self.assertRaises(CliFailure):
                self.parser().feed(raw)

    def test_byte_and_line_limits(self):
        for raw in (b'x' * 65, b'x' * 65 + b'\n'):
            with self.assertRaisesRegex(CliFailure, '^cli_output_limit$'):
                self.parser(limits=Limits(max_line_bytes=64)).feed(raw)
        with self.assertRaisesRegex(CliFailure, '^cli_output_limit$'):
            self.parser(limits=Limits(max_output_bytes=64, max_line_bytes=64)).feed(b'x' * 65)

    def test_nonzero_exit_discards_success(self):
        for code in (1, -1, True, '0'):
            with self.subTest(code=code), self.assertRaisesRegex(CliFailure, '^cli_process_failed$'):
                self.parser([*start(), message(), complete()]).finish(code)

    def test_missing_terminal_text_or_newline(self):
        for events in (start(), [*start(), message()], [*start(), complete()], [*start(), message(' '), complete()]):
            with self.assertRaisesRegex(CliFailure, '^cli_incomplete$'):
                self.parser(events).finish(0)
        parser = self.parser([*start(), message(), complete()])
        parser.feed(b'{')
        with self.assertRaises(CliFailure):
            parser.finish(0)

    def test_failed_parser_cannot_be_reused(self):
        parser = self.parser()
        with self.assertRaises(CliFailure):
            parser.feed(b'bad\n')
        with self.assertRaises(CliFailure):
            parser.feed(lines([*start(), message(), complete()]))
        with self.assertRaises(CliFailure):
            parser.finish(0)

    def test_finished_parser_cannot_be_reused(self):
        parser = self.parser([*start(), message(), complete()])
        parser.finish(0)
        with self.assertRaises(CliFailure):
            parser.finish(0)
        with self.assertRaises(CliFailure):
            parser.feed(b'')

    def test_contract_types(self):
        with self.assertRaises(CliFailure):
            CodexExecParser(None)
        with self.assertRaises(CliFailure):
            self.parser().feed('string')


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / ('codex.exe' if sys.platform == 'win32' else 'codex')
        self.path.write_bytes(b'NOT_EXECUTABLE_TEST_SENTINEL')
        self.pin = CodexBinary(str(self.path), hashlib.sha256(self.path.read_bytes()).hexdigest(), '0.157.1', REQUIRED_FLAGS)
        self.request = CliRequest(CliProvider.CODEX, CliScope(*(str(uuid4()) for _ in range(5))),
                                  str(uuid4()), 'SECRET_PROMPT', 'fixture-only')

    def test_only_inert_preview_and_stdin_prompt(self):
        draft = prepare(self.request, self.pin, self.folder)
        self.assertFalse(draft.live_dispatch_allowed)
        self.assertEqual(draft.stdin, b'SECRET_PROMPT')
        self.assertNotIn('SECRET', repr(draft))
        self.assertNotIn('SECRET_PROMPT', draft.argv)
        self.assertIn('--ephemeral', draft.argv)
        self.assertIn('features.shell_tool=false', draft.argv)
        self.assertNotIn('resume', draft.argv)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', draft.argv)

    def test_preview_is_not_authority(self):
        draft = prepare(self.request, self.pin, self.folder)
        with self.assertRaisesRegex(CliFailure, '^cli_native_bridge_pending$'):
            dispatch(draft, enabled=True, grant=True)

    def test_hash_change_and_missing_capabilities(self):
        with self.assertRaisesRegex(CliFailure, '^cli_binary_changed$'):
            prepare(self.request, replace(self.pin, sha256='0' * 64), self.folder)
        with self.assertRaisesRegex(CliFailure, '^cli_binary_unsupported$'):
            prepare(self.request, replace(self.pin, flags=frozenset()), self.folder)

    def test_model_flag_injection_and_provider(self):
        for model in ('--help', '-c=bad', '"foo"', 'x;bad'):
            with self.subTest(model=model), self.assertRaises(CliFailure):
                prepare(replace(self.request, model=model), self.pin, self.folder)
        with self.assertRaises(CliFailure):
            prepare(replace(self.request, provider=CliProvider.CLAUDE), self.pin, self.folder)

    def test_path_and_contract_validation(self):
        for path in (self.folder / 'missing', Path('relative')):
            with self.assertRaises(CliFailure):
                prepare(self.request, self.pin, path)
        with self.assertRaises(CliFailure):
            prepare(None, self.pin, self.folder)


if __name__ == '__main__':
    unittest.main(verbosity=2)
