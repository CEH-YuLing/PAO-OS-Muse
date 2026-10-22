"""Synthetic protocol corpus only. No binary, profile, DB or network access."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pao_client_adapters import AdapterFailure, AntigravityStream, ClaudeStream, Limits, external_dispatch

TEXT = 'Tiếng Việt: nhãn hàng 🐾\nDòng 2'
MODEL = 'synthetic-model'


def wire(rows):
    return b''.join(json.dumps(r, ensure_ascii=False).encode('utf-8') + b'\n' for r in rows)


class CommonCases:
    def parser(self, **kwargs):
        return self.cls(MODEL, **kwargs)

    def parse(self, rows):
        parser = self.parser()
        self.assertIsNone(parser.feed(wire(rows)))
        return parser.finish(0)

    def reject(self, rows, code=None):
        with self.assertRaises(AdapterFailure) as error:
            self.parse(rows)
        if code:
            self.assertEqual(error.exception.code, code)
        self.assertNotIn('SECRET_SENTINEL', str(error.exception))

    def test_unicode_all_byte_boundaries(self):
        raw = wire(self.rows())
        for size in (1, 2, 3, 7, 4096):
            with self.subTest(size=size):
                parser = self.parser()
                for start in range(0, len(raw), size):
                    self.assertIsNone(parser.feed(raw[start:start+size]))
                value = parser.finish(0)
                self.assertEqual(value.text, TEXT)
                self.assertFalse(value.provider_inference_verified)
                self.assertEqual(value.mode, 'ea3_offline_parsed_unverified')

    def test_reported_usage_without_cost_claim(self):
        value = self.parse(self.rows())
        self.assertEqual(value.usage.input_tokens, 17)
        self.assertEqual(value.usage.output_tokens, 5)
        self.assertEqual(value.usage.state, 'reported')
        self.assertFalse(hasattr(value, 'cost_usd'))
        self.assertFalse(hasattr(value, 'remaining_quota'))

    def test_missing_usage_stays_unknown(self):
        for usage in (None, {}, {'output_tokens':3}):
            rows = self.rows()
            self.terminal(rows)['usage'] = usage
            value = self.parse(rows)
            self.assertIsNone(value.usage.input_tokens)
            self.assertEqual(value.usage.state, 'unknown')

    def test_bad_usage_is_not_zero_or_estimated(self):
        for usage in (False, [], {'input_tokens':True}, {'output_tokens':-1},
                      {'input_tokens':1.5}, {'input_tokens':'17'}, {'input_tokens':10**9+1}):
            rows = self.rows()
            self.terminal(rows)['usage'] = usage
            with self.subTest(usage=usage):
                self.reject(rows)

    def test_no_final_without_terminal(self):
        self.reject(self.rows()[:-1], 'adapter_incomplete')

    def test_exit_nonzero_cannot_succeed(self):
        for code in (1, -9, True, None, 0.0):
            parser = self.parser()
            parser.feed(wire(self.rows()))
            with self.assertRaisesRegex(AdapterFailure, '^adapter_process_failed$'):
                parser.finish(code)

    def test_missing_newline_is_incomplete(self):
        parser = self.parser()
        parser.feed(wire(self.rows())[:-1])
        with self.assertRaisesRegex(AdapterFailure, '^adapter_incomplete$'):
            parser.finish(0)

    def test_duplicate_final_is_rejected(self):
        rows = self.rows()
        self.reject(rows + [rows[-1]])

    def test_duplicate_init_is_rejected(self):
        rows = self.rows()
        self.reject(rows[:1] + rows)

    def test_trailing_garbage_is_not_text(self):
        parser = self.parser()
        parser.feed(wire(self.rows()) + b'SECRET_SENTINEL')
        with self.assertRaises(AdapterFailure):
            parser.finish(0)

    def test_bad_json_and_duplicate_keys(self):
        for raw in (b'raw output SECRET_SENTINEL\n', b'{"a":1,"a":2}\n',
                    b'{"nested":{"n":1,"n":2}}\n', b'{"n":NaN}\n', b'[]\n', b'null\n', b'\xff\n'):
            parser = self.parser()
            with self.assertRaises(AdapterFailure) as error:
                parser.feed(raw)
            self.assertNotIn('SECRET_SENTINEL', str(error.exception))

    def test_model_mismatch_denied(self):
        rows = self.rows()
        self.init(rows)['model'] = 'different-model'
        self.reject(rows, 'adapter_model_mismatch')

    def test_escaped_surrogate_is_not_publishable_utf8(self):
        rows = self.rows()
        self.terminal(rows)[self.text_field] = '\ud800'
        raw = b''.join(json.dumps(row, ensure_ascii=True).encode('ascii') + b'\n' for row in rows)
        parser = self.parser()
        with self.assertRaises(AdapterFailure):
            parser.feed(raw)

    def test_missing_model_is_not_an_implicit_default(self):
        rows = self.rows()
        self.init(rows).pop('model')
        self.reject(rows, 'adapter_model_mismatch')

    def test_usage_zero_is_reported_not_missing(self):
        rows = self.rows()
        self.terminal(rows)['usage'] = {'input_tokens':0,'output_tokens':0}
        result = self.parse(rows)
        self.assertEqual(result.usage.state, 'reported')
        self.assertEqual(result.usage.input_tokens, 0)

    def test_non_bytes_input_invalidates_parser(self):
        parser = self.parser()
        with self.assertRaises(AdapterFailure):
            parser.feed('not bytes')
        with self.assertRaises(AdapterFailure):
            parser.feed(wire(self.rows()))

    def test_session_mismatch_denied(self):
        rows = self.rows()
        self.terminal(rows)[self.sid_field] = str(uuid4())
        self.reject(rows, 'adapter_session_mismatch')

    def test_non_uuid_session_denied(self):
        rows = self.rows()
        rows[0][self.sid_field] = 'SECRET_SENTINEL'
        self.reject(rows)

    def test_nonempty_tool_catalog_denied(self):
        rows = self.rows()
        self.init(rows)['tools'] = ['run_command']
        self.reject(rows, 'adapter_tool_denied')

    def test_terminal_text_mismatch_denied(self):
        rows = self.rows()
        self.terminal(rows)[self.text_field] = 'different result'
        self.reject(rows)

    def test_empty_answer_denied(self):
        rows = self.rows()
        self.terminal(rows)[self.text_field] = '  '
        self.reject(rows)

    def test_multiple_turns_denied(self):
        for count in (2, 0, True, '1', 1.0):
            rows = self.rows()
            self.terminal(rows)['num_turns'] = count
            self.reject(rows)

    def test_unknown_event_denied(self):
        rows = self.rows()
        unknown = {'type':'surprise','event':'surprise','session_id':rows[0][self.sid_field]}
        self.reject(rows[:1] + [unknown] + rows[1:])

    def test_byte_line_and_event_limits(self):
        parser = self.parser(limits=Limits(max_bytes=64, max_line_bytes=64))
        with self.assertRaisesRegex(AdapterFailure, '^adapter_output_limit$'):
            parser.feed(b'x'*65)
        parser = self.parser(limits=Limits(max_events=1))
        with self.assertRaisesRegex(AdapterFailure, '^adapter_output_limit$'):
            parser.feed(wire(self.rows()))
        parser = self.parser(limits=Limits(max_bytes=128, max_line_bytes=64))
        with self.assertRaisesRegex(AdapterFailure, '^adapter_output_limit$'):
            parser.feed(b'x'*65 + b'\n')

    def test_success_cannot_be_reused(self):
        parser = self.parser()
        parser.feed(wire(self.rows()))
        parser.finish(0)
        with self.assertRaises(AdapterFailure):
            parser.finish(0)
        with self.assertRaises(AdapterFailure):
            parser.feed(b'')

    def test_failed_parser_cannot_recover(self):
        parser = self.parser()
        with self.assertRaises(AdapterFailure):
            parser.feed(b'bad\n')
        with self.assertRaises(AdapterFailure):
            parser.feed(wire(self.rows()))
        with self.assertRaises(AdapterFailure):
            parser.finish(0)

    def test_result_repr_omits_prompt_response(self):
        rows = self.rows()
        # Keep stream and terminal consistent while inserting a synthetic secret.
        payload = wire(rows).replace(TEXT.encode('utf-8').replace(b'\n', b'\\n'), b'SECRET_SENTINEL')
        parser = self.parser()
        parser.feed(payload)
        value = parser.finish(0)
        self.assertEqual(value.text, 'SECRET_SENTINEL')
        self.assertNotIn('SECRET_SENTINEL', repr(value))


class ClaudeTests(CommonCases, unittest.TestCase):
    cls = ClaudeStream
    sid_field = 'session_id'
    text_field = 'result'

    def rows(self):
        sid = str(uuid4())
        return [
            {'type':'system','subtype':'init','session_id':sid,'model':MODEL,'tools':[],'mcp_servers':[],'plugins':[]},
            {'type':'assistant','session_id':sid,'parent_tool_use_id':None,
             'message':{'model':MODEL,'role':'assistant','content':[{'type':'text','text':TEXT}]}},
            {'type':'result','subtype':'success','is_error':False,'session_id':sid,'num_turns':1,'result':TEXT,
             'usage':{'input_tokens':17,'output_tokens':5,'cache_read_input_tokens':8,'cache_creation_input_tokens':2}}]

    def init(self, rows):
        return rows[0]

    def terminal(self, rows):
        return rows[-1]

    def test_api_retry_does_not_become_another_attempt(self):
        rows = self.rows()
        retry = {'type':'system','subtype':'api_retry','session_id':rows[0]['session_id'],'error':'SECRET_SENTINEL'}
        self.reject(rows[:1] + [retry] + rows[1:], 'adapter_provider_failed')

    def test_tool_thinking_and_subagent_blocks_denied(self):
        for kind in ('tool_use','tool_result','thinking','server_tool_use'):
            rows = self.rows()
            rows[1]['message']['content'] = [{'type':kind,'text':'SECRET_SENTINEL'}]
            self.reject(rows, 'adapter_tool_denied')
        rows = self.rows()
        rows[1]['parent_tool_use_id'] = 'tool-123'
        self.reject(rows, 'adapter_tool_denied')

    def test_hooks_plugins_mcp_not_silently_accepted(self):
        for field in ('mcp_servers','plugins'):
            rows = self.rows()
            rows[0][field] = ['unexpected']
            self.reject(rows, 'adapter_tool_denied')
        rows = self.rows()
        rows.insert(1, {'type':'system','subtype':'hook_started','session_id':rows[0]['session_id']})
        self.reject(rows)

    def test_error_result_never_leaks_raw_error(self):
        rows = self.rows()
        rows[-1].update(is_error=True, subtype='error_during_execution', result='SECRET_SENTINEL')
        self.reject(rows, 'adapter_provider_failed')

    def test_measured_cli_success_subtype_with_is_error_true_is_failure(self):
        rows = self.rows()
        rows[-1].update(is_error=True, subtype='success', result='SECRET_SENTINEL')
        self.reject(rows, 'adapter_provider_failed')

    def test_partial_usage_not_summed_as_final(self):
        rows = self.rows()
        rows[1]['message']['usage'] = {'input_tokens':99999,'output_tokens':99999}
        value = self.parse(rows)
        self.assertEqual(value.usage.input_tokens, 17)
        self.assertEqual(value.usage.cache_read_tokens, 8)
        self.assertEqual(value.usage.cache_creation_tokens, 2)
        self.assertIsNone(value.usage.total_tokens)


class AntigravityTests(CommonCases, unittest.TestCase):
    cls = AntigravityStream
    sid_field = 'conversation_id'
    text_field = 'response'

    def rows(self):
        sid = str(uuid4())
        return [
            {'event':'init','conversation_id':sid,'init':{'model':MODEL,'tools':[],'permission_mode':'request-review'}},
            {'event':'step_update','step_update':{'conversation_id':sid,'step_index':0,'state':'DONE','step_type':'user_input'}},
            {'event':'step_update','step_update':{'conversation_id':sid,'step_index':1,'state':'DONE','step_type':'agent_response','text_delta':TEXT}},
            {'event':'result','result':{'conversation_id':sid,'status':'SUCCESS','response':TEXT,'num_turns':1,
             'usage':{'input_tokens':17,'output_tokens':5,'cache_read_tokens':8,'thinking_tokens':2,'total_tokens':22}}}]

    def init(self, rows):
        return rows[0]['init']

    def terminal(self, rows):
        return rows[-1]['result']

    def test_active_done_fragments_concatenate_once(self):
        rows = self.rows()
        step = rows[2]['step_update']
        step['text_delta'] = TEXT[4:]
        first = deepcopy(rows[2])
        first['step_update'].update(state='ACTIVE', text_delta=TEXT[:4])
        rows.insert(2, first)
        self.assertEqual(self.parse(rows).text, TEXT)

    def test_step_usage_not_double_counted(self):
        rows = self.rows()
        rows[2]['step_update']['usage'] = {'input_tokens':99999,'output_tokens':99999}
        result = self.parse(rows)
        self.assertEqual(result.usage.input_tokens, 17)
        self.assertEqual(result.usage.thinking_tokens, 2)
        self.assertEqual(result.usage.total_tokens, 22)

    def test_duplicate_done_is_not_another_delta(self):
        rows = self.rows()
        self.reject(rows[:3] + [rows[2]] + rows[3:])

    def test_open_or_out_of_order_steps_denied(self):
        rows = self.rows()
        rows[2]['step_update']['state'] = 'ACTIVE'
        self.reject(rows)
        rows = self.rows()
        rows[2]['step_update']['step_index'] = -1
        self.reject(rows)

    def test_tool_and_subagent_events_denied(self):
        for field in ('tool_info','tool_name','subagent_info'):
            rows = self.rows()
            rows[2]['step_update'][field] = 'SECRET_SENTINEL'
            self.reject(rows, 'adapter_tool_denied')
        rows = self.rows()
        rows[2]['step_update']['step_type'] = 'tool'
        self.reject(rows, 'adapter_tool_denied')

    def test_skip_permissions_denied(self):
        rows = self.rows()
        rows[0]['init']['permission_mode'] = 'always-proceed'
        self.reject(rows, 'adapter_tool_denied')

    def test_every_non_success_state_denied(self):
        for state in ('ERROR','CANCELED','INTERRUPTED','INVALID','WAITING','RUNNING','unknown'):
            rows = self.rows()
            rows[-1]['result'].update(status=state, error='SECRET_SENTINEL')
            self.reject(rows, 'adapter_provider_failed')


class ContractTests(unittest.TestCase):
    def test_live_is_not_unlocked_by_flags_or_credentials(self):
        with self.assertRaisesRegex(AdapterFailure, '^adapter_live_disabled$'):
            external_dispatch(enabled=True, token='SECRET_SENTINEL', command=['agy'])

    def test_model_and_limits_validation(self):
        for cls in (ClaudeStream, AntigravityStream):
            for model in ('', None, '--dangerously-skip-permissions', 'bad model', 'x\n', 'x'*121):
                with self.assertRaises(AdapterFailure):
                    cls(model)
        for kwargs in ({'max_bytes':True},{'max_bytes':63},{'max_line_bytes':1048577},{'max_events':0}):
            with self.assertRaises(AdapterFailure):
                Limits(**kwargs)

    def test_unknown_failure_never_reflects_raw_data(self):
        self.assertEqual(str(AdapterFailure('SECRET_SENTINEL')), 'adapter_protocol_invalid')


if __name__ == '__main__':
    unittest.main()
