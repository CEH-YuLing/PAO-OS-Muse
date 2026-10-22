"""One durable attempt per provider invocation; replay never adds tokens/cost.

Actual counts nullable; estimates/reservations are separate. No raw provider
usage/prompt/private reasoning enters the ledger. Unknown price is not zero cost.
"""
import asyncio,json,math,time
from contextvars import ContextVar
from decimal import Decimal
from sqlalchemy import select
from ...config import settings
from ...db import Session
from ...models import ChatSession,Run,LlmAttempt,now,uid
from ...gateway import Chunk
from ..engines.contract import EngineFailure
from .context import compile_messages,REFERENCE
from .policy import run_policy,policy_for,enforce
from ..connections import resources
from . import transport_policy
from .token_policy import automatic, PROVIDER_MANAGED, TRANSPORT_BYTES

CURRENT_ATTEMPT = ContextVar('pao_accounted_attempt', default=None)


def counts(raw):
    def read(keys):
        for key in keys:
            value=raw.get(key)
            if type(value) is int and 0<=value<=1_000_000:return value
        return None
    return read(('input_tokens','prompt_tokens','prompt_eval_count','promptTokenCount')),read(('output_tokens','completion_tokens','eval_count','candidatesTokenCount'))


async def reserve(run_id,key,source,provider,model,trace,output):
    async with Session.begin() as db:
        wid=await db.scalar(select(Run.workspace_id).where(Run.id==run_id))
        if wid is None:raise EngineFailure('engine_run_not_active')
        await resources.lock(db,wid)  # Scope/admission before Run, never lock upgrade.
        run=await db.scalar(select(Run).where(Run.id==run_id).with_for_update())
        chat=await db.get(ChatSession,run.session_id)
        from ..business_planning.jobs import guard_run
        await guard_run(db,run)  # S5 stop/approval pins, without changing legacy extraction authority.
        policy=run_policy(run);enforce(provider,policy,policy_for(chat))
        if provider!='ollama' and policy.get('cloud_references') and not policy_for(chat).get('cloud_references'):
            raise EngineFailure('cloud_reference_egress_denied')
        from ...models import Member,User
        from ..brains.context import check_run_brain
        member=await db.get(Member,(run.workspace_id,chat.user_id));user=await db.get(User,chat.user_id)
        from ..connections.enterprise_ai import run_actor
        await run_actor(db,run,chat)
        if not member or not user.active or run.cancel_requested:
            raise EngineFailure('access_revoked')
        await check_run_brain(db,run,chat)
        if run.status!='running' and not (source=='memory_extraction' and run.status=='completed'):
            raise EngineFailure('engine_run_not_active')
        await transport_policy.require_ready(db,run,provider,model)
        rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run_id)))
        if any(row.request_key==key for row in rows):raise EngineFailure('engine_attempt_replay_denied')
        used=sum(max(row.estimated_input_tokens,row.input_tokens or 0)+max(row.reserved_output_tokens,row.output_tokens or 0) for row in rows)
        if len(rows)>=policy['max_calls'] or (not automatic(policy) and used+trace['estimated_tokens']+output>policy['max_run_tokens']):
            raise EngineFailure('engine_budget_exhausted')
        row=LlmAttempt(id=uid(),workspace_id=run.workspace_id,user_id=chat.user_id,brain_id=run.brain_id,
            session_id=run.session_id,run_id=run.id,request_key=key,source=source,provider=provider,model=model,
            estimated_input_tokens=trace['estimated_tokens'],reserved_output_tokens=output,trace=trace,pricing=policy.get('pricing'))
        await resources.admit(db,wid,chat.user_id,'llm',row.id,trace['estimated_tokens']+output,attempt=row.id,provider_managed=automatic(policy))
        db.add(row);await db.flush();return row.id


async def complete(attempt_id,status,usage,text_chars,ttft,elapsed,failure_code=None):
    async with Session.begin() as db:
        wid=await db.scalar(select(LlmAttempt.workspace_id).where(LlmAttempt.id==attempt_id))
        if wid is None:return
        await resources.lock(db,wid)
        row=await db.scalar(select(LlmAttempt).where(LlmAttempt.id==attempt_id).with_for_update())
        if row.status!='started':return  # callback/event replay: no double count
        if failure_code in transport_policy.FAILURE_CODES:
            row.trace={**row.trace,'failure_code':failure_code}
        row.input_tokens,row.output_tokens=counts(usage)
        row.usage_state=('reported' if row.input_tokens is not None and row.output_tokens is not None else
                         'partial' if row.input_tokens is not None or row.output_tokens is not None else 'unknown')
        row.status,row.finished_at=status,now()
        row.estimated_output_tokens=math.ceil(text_chars/2)
        row.ttft_ms,row.elapsed_ms=ttft,elapsed
        await resources.release(db,wid,attempt=row.id)
        if row.usage_state=='reported' and row.pricing:
            row.cost_estimate=(Decimal(row.input_tokens)*Decimal(row.pricing['input_per_million'])+
                               Decimal(row.output_tokens)*Decimal(row.pricing['output_per_million']))/Decimal(1_000_000)


class AccountingEngine:
    def __init__(self,gateway,run,history_ids=(),source_prefix='chat',request_key=None,cache=None,selected_skill=None):
        self.gateway,self.run_id,self.prompt=gateway,run.id,run.prompt
        self.engine_selection=dict(run.engine_snapshot or {})
        self.provider_name,self.model_name=gateway.provider_name,gateway.model_name
        self.policy=run_policy(run);self.history_ids=list(history_ids);self.ordinal=0
        self.source_prefix,self.request_key=source_prefix,request_key
        self.selected_skill=selected_skill
        self.cache_metadata={key:getattr(cache,key) for key in ('id','revision','version','message_ids','source_hash')} if cache else None
        self.queue_wait_ms=int((run.started_at-run.created_at).total_seconds()*1000) if run.started_at and run.created_at else None

    def prepare(self,messages,output,kind):
        if self.provider_name!='ollama' and any('Verified PAO intelligence records' in row['content'] for row in messages):
            raise EngineFailure('cloud_private_intelligence_denied')
        if self.provider_name!='ollama' and not self.policy.get('cloud_references') and any(
            row['content'].startswith(('REFERENCE DATA','Earlier tool results','Tool Gateway results','Specialist reference','Conversation cache'))
            for row in messages[1:]):
            raise EngineFailure('cloud_reference_egress_denied')
        extra=[];wire=messages
        if kind=='planner':
            from ...agents import PLANNER_PROMPT,TOOL_PLANNER_PROMPT,ExecutionPlan
            prompt=PLANNER_PROMPT+(TOOL_PLANNER_PROMPT if settings().tools_enabled else 'Tools are disabled. Return tools: [].')
            wire=[{'role':'system','content':prompt},*messages[1:]]
            if self.provider_name!='ollama':
                instruction=('Return only one JSON object matching this JSON Schema. Do not use markdown. Schema: ' if
                    self.provider_name in ('openai','openrouter') else 'Return only JSON matching this schema, without markdown: ')
                if self.provider_name!='gemini':
                    extra=[{'role':'system','content':instruction+json.dumps(ExecutionPlan.model_json_schema(),ensure_ascii=False)}]
        if kind=='extraction' and self.provider_name not in ('ollama','gemini'):
            from ...memory_schemas import ExtractedFacts
            instruction=('Return only one JSON object matching this JSON Schema. Do not use markdown. Schema: '
                if self.provider_name in ('openai','openrouter') else 'Return only JSON matching this schema, without markdown: ')
            extra=[{'role':'system','content':instruction+json.dumps(ExtractedFacts.model_json_schema(),ensure_ascii=False)}]
        auto=automatic(self.policy)
        compiled=compile_messages(wire,max_bytes=TRANSPORT_BYTES if auto else self.policy['max_bytes'],
            max_tokens=None if auto else self.policy['context_tokens']-output,history_ids=self.history_ids,
            extra_wire=extra,current_prompt=self.prompt,selected_skill=self.selected_skill)
        return compiled

    async def begin(self,messages,output,kind):
        if not settings().chat_features_enabled:
            raise EngineFailure(resources.ACCOUNTING_REQUIRED) # Cached gateway cannot revive disabled accounting.
        if automatic(self.policy):output=0  # No invented reservation for an unknown native output.
        compiled=self.prepare(messages,output,kind);self.ordinal+=1
        if self.provider_name=='muse':
            from ..cli_connections.muse_resource import NATIVE_INPUT_RESERVATION
            # Conservative reservation for the pinned native system prompt,
            # separate from actual provider counts; never fabricate usage.
            compiled.trace['estimated_tokens']+=NATIVE_INPUT_RESERVATION
            compiled.trace['native_input_reservation']=NATIVE_INPUT_RESERVATION
        key=self.request_key or f'{self.source_prefix}:{self.ordinal}'
        trace={**compiled.trace,'stage':kind,'queue_wait_ms':self.queue_wait_ms,'compaction':self.cache_metadata}
        # Public selection evidence, not credentials, raw usage or private reasoning.
        # Local historical memory may intentionally differ from its parent engine.
        selected=self.engine_selection
        trace['engine_selection']=transport_policy.selection(selected,self.provider_name,self.model_name)
        row=await reserve(self.run_id,key,self.source_prefix+'_'+kind if self.source_prefix=='chat' else self.source_prefix,
                          self.provider_name,self.model_name,trace,output)
        return row,compiled.messages

    @resources.bounded
    async def stream(self,messages,max_tokens=None):
        auto=automatic(self.policy)
        output=0 if auto else min(max_tokens or self.policy['max_output_tokens'],self.policy['max_output_tokens'])
        kind='specialist' if max_tokens is not None else 'final'
        row,compiled=await self.begin(messages,output,kind);started=time.monotonic();usage={};size=0;first=None;status='failed';failure=None
        source=self.gateway.stream(compiled,max_tokens=output)
        invocation=CURRENT_ATTEMPT.set(row)
        mode=PROVIDER_MANAGED.set(auto)
        try:
            async for chunk in source:
                if chunk.text:
                    if first is None:first=int((time.monotonic()-started)*1000)
                    size+=len(chunk.text.encode())
                    if size>TRANSPORT_BYTES:raise EngineFailure('context_transport_limit')
                    if not auto and math.ceil(size/2)>output:raise EngineFailure('engine_output_budget_exhausted')
                if chunk.usage:usage.update(chunk.usage)
                inp,out=counts(usage)
                if not auto and out is not None and out>output:raise EngineFailure('engine_output_budget_exhausted')
                safe={}
                if inp is not None:safe['input_tokens']=inp
                if out is not None:safe['output_tokens']=out
                yield Chunk(text=chunk.text,usage=safe)
            if self.policy['require_reported_usage'] and None in counts(usage):raise EngineFailure('engine_usage_unknown')
            inp,out=counts(usage)
            if not auto and inp is not None and inp+output>self.policy['context_tokens']:raise EngineFailure('engine_context_usage_exceeded')
            status='completed'
        except asyncio.CancelledError:
            status='cancelled';raise
        except Exception as exc:
            from ..engines.contract import normalize
            error=normalize(exc);failure=error.code;raise error from None
        finally:
            try:
                async with asyncio.timeout(resources.CLOSE_TIMEOUT):await source.aclose()
            finally:
                CURRENT_ATTEMPT.reset(invocation)
                PROVIDER_MANAGED.reset(mode)
                await complete(row,status,usage,size,first,int((time.monotonic()-started)*1000),failure)

    @resources.bounded
    async def plan(self,messages):
        row,compiled=await self.begin(messages,512,'planner');started=time.monotonic();status='failed';size=0;usage={};failure=None
        invocation=CURRENT_ATTEMPT.set(row)
        auto=automatic(self.policy);mode=PROVIDER_MANAGED.set(auto)
        try:
            result=await self.gateway.plan(compiled)
            size=len(result.model_dump_json().encode())
            usage=getattr(self.gateway,'last_usage',{})
            if self.policy['require_reported_usage'] and None in counts(usage):raise EngineFailure('engine_usage_unknown')
            inp,out=counts(usage)
            if not auto and out is not None and out>512:raise EngineFailure('engine_output_budget_exhausted')
            if not auto and inp is not None and inp+512>self.policy['context_tokens']:raise EngineFailure('engine_context_usage_exceeded')
            status='completed';return result
        except asyncio.CancelledError:
            status='cancelled';raise
        except Exception as exc:
            from ..engines.contract import normalize
            error=normalize(exc);failure=error.code;raise error from None
        finally:
            CURRENT_ATTEMPT.reset(invocation)
            PROVIDER_MANAGED.reset(mode)
            await complete(row,status,usage,size,None,int((time.monotonic()-started)*1000),failure)

    @resources.bounded
    async def extract(self,prompt):
        messages=self.gateway.extraction_messages(prompt)
        row,_=await self.begin(messages,512,'extraction');started=time.monotonic();status='failed';size=0;usage={};failure=None
        invocation=CURRENT_ATTEMPT.set(row)
        auto=automatic(self.policy);mode=PROVIDER_MANAGED.set(auto)
        try:
            result=await self.gateway.extract(prompt);size=len(result.model_dump_json().encode())
            usage=getattr(self.gateway,'last_usage',{})
            if self.policy['require_reported_usage'] and None in counts(usage):raise EngineFailure('engine_usage_unknown')
            inp,out=counts(usage)
            if not auto and out is not None and out>512:raise EngineFailure('engine_output_budget_exhausted')
            if not auto and inp is not None and inp+512>self.policy['context_tokens']:raise EngineFailure('engine_context_usage_exceeded')
            status='completed';return result
        except asyncio.CancelledError:
            status='cancelled';raise
        except Exception as exc:
            from ..engines.contract import normalize
            error=normalize(exc);failure=error.code;raise error from None
        finally:
            CURRENT_ATTEMPT.reset(invocation)
            PROVIDER_MANAGED.reset(mode)
            await complete(row,status,usage,size,None,int((time.monotonic()-started)*1000),failure)
