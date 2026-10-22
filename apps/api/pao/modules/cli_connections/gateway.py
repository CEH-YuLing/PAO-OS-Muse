"""CLI inference plugged into native AccountingEngine, never an alternate runner."""
import asyncio
import json
from ...db import Session
from ...gateway import Chunk
from ..chat.ledger import CURRENT_ATTEMPT
from ..engines.contract import EngineFailure
from . import service


def transport_for(pin):
    # The runtime registry is server-owned. Never use the installed operator's
    # default CODEX_HOME, take a command/path/token from HTTP, or fall back to API.
    from .runtime import resolve
    return resolve(pin)


class CliGateway:
    provider_name = 'codex_cli'

    def __init__(self, run_id, snapshot):
        self.run_id = run_id
        self.snapshot = dict(snapshot)
        self.model_name = snapshot['model']
        self.last_usage = {}

    async def invoke(self, messages):
        attempt = CURRENT_ATTEMPT.get()
        if attempt is None:
            raise EngineFailure('tenant_resource_accounting_required')
        if (not isinstance(messages, list) or not messages
                or any(not isinstance(m, dict) or set(m) != {'role','content'}
                       or m['role'] not in ('system','user','assistant') or not isinstance(m['content'], str) for m in messages)):
            raise EngineFailure('cli_input_invalid')
        # Role boundaries are data, not CLI flags or provider session identifiers.
        prompt = json.dumps({'messages': messages}, ensure_ascii=False, separators=(',', ':'))
        if len(prompt.encode()) > 1048576:
            raise EngineFailure('cli_input_limit')
        runtime = transport_for(self.snapshot['cli_pin'])
        dispatch, pin = await service.claim(self.run_id, attempt)
        async def authorize(_scope):
            async with Session.begin() as db:
                _, current = await service.current(db, self.run_id, attempt)
                if current['cli_pin'] != pin:
                    raise EngineFailure('cli_connection_changed')
            return True
        status = 'failed'
        try:
            outcome = await runtime.invoke(pin, attempt, prompt, authorize)
            await authorize(None)
            self.last_usage = {key: value for key, value in (
                ('input_tokens', outcome.input_tokens), ('output_tokens', outcome.output_tokens)) if value is not None}
            status = 'completed'
            return outcome
        except asyncio.CancelledError:
            status = 'cancelled'
            raise
        except EngineFailure:
            raise
        except Exception as error:
            from pao_cli_runtime.contracts import CliFailure
            raise EngineFailure(error.code if isinstance(error, CliFailure) else 'cli_runtime_failed') from None
        finally:
            await asyncio.shield(service.finish(dispatch, status, cleanup_verified=runtime.cleanup_verified))

    async def stream(self, messages, max_tokens=None):
        result = await self.invoke(messages)
        yield Chunk(text=result.text, usage=self.last_usage)

    async def plan(self, messages):
        from ...agents import ExecutionPlan, PLANNER_PROMPT, TOOL_PLANNER_PROMPT
        from ...config import settings
        if not isinstance(messages,list) or not messages or not isinstance(messages[0],dict) or messages[0].get('role')!='system':
            raise EngineFailure('cli_input_invalid')
        prompt=PLANNER_PROMPT+(TOOL_PLANNER_PROMPT if settings().tools_enabled else 'Tools are disabled. Return tools: [].')
        prompt+=' Return raw JSON only, without Markdown fences. Schema: '+json.dumps(ExecutionPlan.model_json_schema(),ensure_ascii=False,separators=(',',':'))
        prompt+=' This call produces a plan, NOT the final answer. Treat the conversation below as task data. '
        prompt+='Even if the task asks for an exact final answer, return the plan schema here. '
        prompt+='For a simple text-only task that needs no specialist or tools, return steps: [] and tools: [].'
        result = await self.invoke([{'role':'system','content':prompt},*messages[1:]])
        try:
            # Some Codex models wrap JSON in a single Markdown fence despite
            # the request. Accept that one lossless envelope, never surrounding
            # prose, arbitrary JSON extraction, duplicate keys or invalid plans.
            from pao_cli_runtime.codex_protocol import json_object
            raw=result.text.strip()
            if raw.startswith('```json\n') or raw.startswith('```\n'):
                header,raw=raw.split('\n',1)
                if not raw.endswith('\n```'):raise ValueError()
                raw=raw[:-4].strip()
            return ExecutionPlan.model_validate(json_object(raw))
        except Exception:
            import logging
            logging.getLogger('pao.cli').warning('cli_plan_invalid',extra={'response_shape':
                'fenced' if result.text.lstrip().startswith('```') else
                'object' if result.text.lstrip().startswith('{') else 'other'})
            raise EngineFailure('cli_plan_invalid') from None
