"""Synthetic Responses server + actual Codex binary in a network-none container.

This is a bounded operator acceptance fixture, not a PAO job runner or a provider
proxy. It contains no auth, external endpoints, user prompts or real model calls.
"""
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import sys
from uuid import uuid4

from pao_cli_runtime.codex_protocol import CodexExecParser
from pao_cli_runtime.contracts import Limits
from pao_cli_runtime.codex_catalog import text_catalog

ANSWER = 'PAO: phản hồi từ máy chủ giả lập, không phải suy luận AI.'


class Fixture(http.server.BaseHTTPRequestHandler):
    requests = []
    adversarial = False

    def log_message(self, *_args):
        pass

    def do_POST(self):
        size = int(self.headers.get('Content-Length', '0'))
        if size > 262144 or self.path != '/v1/responses':
            self.send_error(400)
            return
        body = json.loads(self.rfile.read(size))
        self.requests.append({'path': self.path, 'model': body.get('model'),
                              'reasoning': body.get('reasoning'),
                              'tools': [{'type': t.get('type'), 'name': t.get('name')}
                                        for t in body.get('tools', [])],
                              'authorization_present': 'Authorization' in self.headers})
        message = {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant',
                   'content': [{'type': 'output_text', 'text': ANSWER, 'annotations': []}], 'status': 'completed'}
        if self.adversarial and len(self.requests) == 1:
            message = {'id': 'tool_fixture', 'type': 'custom_tool_call', 'call_id': 'call_fixture',
                       'name': 'apply_patch', 'status': 'completed',
                       'input': '*** Begin Patch\n*** Add File: /tmp/forbidden-tool-write.txt\n+unsafe\n*** End Patch'}
        response = {'id': 'resp_fixture', 'object': 'response', 'created_at': 1,
                    'status': 'completed', 'model': body.get('model'), 'output': [message],
                    'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15,
                              'input_tokens_details': {'cached_tokens': 0},
                              'output_tokens_details': {'reasoning_tokens': 0}}}
        events = [
            {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
            {'type': 'response.output_item.added', 'output_index': 0, 'item': {**message, 'status': 'in_progress', 'content': []}},
            {'type': 'response.content_part.added', 'output_index': 0, 'item_id': 'msg_fixture', 'content_index': 0,
             'part': {'type': 'output_text', 'text': '', 'annotations': []}},
            {'type': 'response.output_text.delta', 'output_index': 0, 'item_id': 'msg_fixture', 'content_index': 0, 'delta': ANSWER},
            {'type': 'response.output_text.done', 'output_index': 0, 'item_id': 'msg_fixture', 'content_index': 0, 'text': ANSWER},
            {'type': 'response.output_item.done', 'output_index': 0, 'item': message},
            {'type': 'response.completed', 'response': response},
        ]
        if message['type'] == 'custom_tool_call':
            events = [events[0], {'type': 'response.output_item.done', 'output_index': 0, 'item': message}, events[-1]]
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Connection', 'close')
        self.end_headers()
        for number, event in enumerate(events):
            event['sequence_number'] = number
            self.wfile.write(('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n').encode())
        self.wfile.flush()
        self.close_connection = True


def main():
    home = Path('/tmp/home')
    home.mkdir(mode=0o700)
    work = Path('/tmp/work')
    work.mkdir(mode=0o700)
    (home / '.codex').mkdir(mode=0o700)
    # Explicit local model metadata for this protocol fixture only. No model
    # entitlement claim: the responder is synthetic and network is disabled.
    catalog = work / 'models.json'
    mode=sys.argv[1] if len(sys.argv)==2 else 'normal'
    if mode not in ('normal','tool-injection','effort-high','effort-low','model-a-high','model-b-low'):
        raise ValueError('Unknown offline fixture case')
    effort=mode.removeprefix('effort-') if mode.startswith('effort-') else {'model-a-high':'high','model-b-low':'low'}.get(mode)
    model='pao-synthetic-specialist' if mode=='model-b-low' else 'gpt-5.4'
    catalog.write_text(json.dumps(text_catalog(model,effort) if effort else text_catalog(model)))
    Fixture.adversarial = sys.argv[1:] == ['tool-injection']
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    command = ['/usr/local/bin/codex', '--strict-config', '--sandbox', 'read-only', '--ask-for-approval', 'never']
    configs = [f'model_catalog_json="{catalog}"', 'model_provider="pao_fixture"', 'model_providers.pao_fixture.name="PAO offline fixture"',
               f'model_providers.pao_fixture.base_url="http://127.0.0.1:{server.server_port}/v1"',
               'model_providers.pao_fixture.wire_api="responses"', 'model_providers.pao_fixture.requires_openai_auth=false',
               'features.shell_tool=false', 'features.apps=false', 'web_search="disabled"',
               'features.multi_agent=false', 'features.goals=false', 'features.hooks=false',
               'features.plugins=false', 'features.memories=false', 'features.view_image=false',
               'features.sleep_tool=false', 'features.browser_use=false', 'features.computer_use=false',
               'cli_auth_credentials_store="file"', 'project_doc_max_bytes=0', 'allow_login_shell=false']
    for value in configs:
        command += ['-c', value]
    if effort:command+=['-c','model_reasoning_effort='+json.dumps(effort)]
    command += ['exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                '--skip-git-repo-check', '--color', 'never', '--cd', str(work), '--model', model, '-']
    try:
        result = subprocess.run(command, input=b'Synthetic test only.', capture_output=True, timeout=35,
                                env={'HOME': str(home), 'CODEX_HOME': str(home / '.codex'),
                                     'TMPDIR': '/tmp', 'PATH': '/usr/local/bin:/usr/bin:/bin'})
        parser = CodexExecParser(Limits())
        outcome = None
        protocol_failure = None
        try:
            parser.feed(result.stdout)
            outcome = parser.finish(result.returncode)
        except Exception as failure:
            protocol_failure = str(failure)
        expected_tools = [{'type': 'function', 'name': 'request_user_input'}]
        passed = ((Fixture.adversarial or outcome and outcome.text == ANSWER)
                  and 1 <= len(Fixture.requests) <= 2
                  and all(not r['authorization_present'] and r['tools'] == expected_tools and r['model']==model for r in Fixture.requests)
                  and not Path('/tmp/forbidden-tool-write.txt').exists())
        if effort:passed=passed and all((row.get('reasoning') or {}).get('effort')==effort for row in Fixture.requests)
        print(json.dumps({'pass': passed, 'codex_returncode': result.returncode,
                          'response': outcome.text if outcome else None, 'protocol_failure': protocol_failure,
                          'adversarial': Fixture.adversarial, 'forbidden_file_exists': Path('/tmp/forbidden-tool-write.txt').exists(),
                          'requests': Fixture.requests, 'input_tokens': outcome.input_tokens if outcome else None,
                          'output_tokens': outcome.output_tokens if outcome else None, 'provider_inference_verified': False,
                          'uid': os.getuid(), 'stderr_bytes': len(result.stderr)}))
        raise SystemExit(0 if passed else 1)
    except Exception as failure:
        print(json.dumps({'pass': False, 'failure': type(failure).__name__, 'code': str(failure),
                          'requests': Fixture.requests,
                          'stdout': result.stdout.decode(errors='replace') if 'result' in locals() else '',
                          'stderr': result.stderr.decode(errors='replace') if 'result' in locals() else ''}))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
