"""Read retained synthetic pao_test evidence; never invoke a model or mutate DB."""
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from pao.config import settings
from local_cycle_test_lock import isolated_test_slot
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.models import Run,LlmAttempt,AgentRun,ToolCall


async def main():
    url=make_url(settings().database_url)
    assert (url.host,url.port,url.database)==('127.0.0.1',15432,'pao_acos_local')
    target=url.set(database='pao_test')
    assert target.database=='pao_test'
    folder=ROOT/'.runtime'/('muse-orchestrator-review-'+uuid4().hex)
    folder.mkdir()
    state={'pass':False,'read_only':True,'new_provider_calls':0,'primary_mutations':0,
           'original_receipt':'.runtime/gd01-tests-9e2862914820468b94d63a99f4d0774b/receipt.json',
           'original_test_remains_failed':True,'replay_tested':False}
    engine=create_async_engine(target)
    try:
        async with async_sessionmaker(engine)() as db:
            await db.execute(text('SET TRANSACTION READ ONLY'))
            assert await db.scalar(text('SHOW transaction_read_only'))=='on'
            runs=list(await db.scalars(select(Run).where(Run.prompt.contains('PAO_MUSE_ORCHESTRATOR_OK'))))
            assert len(runs)==1,'Retained synthetic run missing or ambiguous; do not replay automatically'
            run=runs[0]
            attempts=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run.id).order_by(LlmAttempt.created_at)))
            agents=list(await db.scalars(select(AgentRun).where(AgentRun.run_id==run.id)))
            tools=list(await db.scalars(select(ToolCall.id).where(ToolCall.run_id==run.id)))
            state.update(run_id=run.id,run_status=run.status,exact_marker=run.response.strip()=='PAO_MUSE_ORCHESTRATOR_OK',
                tools=len(tools),agents=[{'key':a.agent_key,'step':a.step_index,'status':a.status} for a in agents],
                actual_recorded_attempts=len(attempts),calls=[{'provider':a.provider,'model':a.model,'source':a.source,
                'status':a.status,'usage_state':a.usage_state,'input_tokens':a.input_tokens,'output_tokens':a.output_tokens,
                'effort':a.trace.get('engine_selection',{}).get('reasoning_effort'),
                'cleanup_verified':a.trace.get('muse_dispatch',{}).get('cleanup_verified')} for a in attempts])
            assert run.status=='completed' and state['exact_marker'] and not tools
            assert len(attempts)==2 and {a.source for a in attempts}=={'chat_planner','chat_final'}
            assert len(agents)==1 and agents[0].agent_key=='chief_of_staff' and agents[0].step_index==0
            assert all(a.provider=='muse' and a.status=='completed' and a.usage_state=='reported'
                and a.trace['muse_dispatch']['cleanup_verified'] for a in attempts)
            state['pass']=True
    finally:
        await engine.dispose()
        with (folder/'receipt.json').open('x',encoding='utf-8') as output:json.dump(state,output,indent=2)
        print(json.dumps({'folder':str(folder),**state}))


if __name__=='__main__':
    with isolated_test_slot():asyncio.run(main())
