"""Real Ollama acceptance in pao_test only. Creates synthetic data, never uses personal chats."""
import os
import asyncio
import json
import time
from pathlib import Path
from uuid import uuid4
from pao.config import settings

config = settings()
os.environ['DATABASE_URL'] = config.database_url.rsplit('/', 1)[0] + '/pao_test'
settings.cache_clear()
assert settings().database_url.endswith('/pao_test')

from sqlalchemy import select
from pao.db import Session, engine
from pao.models import User, Workspace, Member, Brand, ChatSession, Run, Message, Memory, MemoryJob, RunEvent
from pao.memory import extract_memory, retrieve
from pao.runtime import execute_run


async def main():
    started = time.monotonic()
    async with Session.begin() as db:
        user = User(email=f'memory-acceptance-{uuid4().hex}@example.test', password_hash='disabled-test-identity')
        workspace = Workspace(name='Isolated local Memory acceptance')
        db.add_all([user, workspace]); await db.flush()
        db.add(Member(user_id=user.id, workspace_id=workspace.id, role='owner'))
        brand = Brand(workspace_id=workspace.id, name='Synthetic tea brand')
        db.add(brand); await db.flush()
        scope = (workspace.id, user.id, brand.id)
    async def chat(prompt):
        async with Session.begin() as db:
            session = ChatSession(workspace_id=scope[0], user_id=scope[1], brand_id=scope[2])
            db.add(session); await db.flush()
            run = Run(workspace_id=scope[0], session_id=session.id, prompt=prompt, request_key=uuid4().hex)
            db.add(run); await db.flush()
            db.add(Message(workspace_id=scope[0], session_id=session.id, run_id=run.id, role='user', content=prompt))
        await execute_run({}, run.id)
        async with Session() as db:
            result = await db.get(Run, run.id)
            assert result.status == 'completed', result.error_code
            return run.id, result.response
    fact = 'Thương hiệu trà thử nghiệm Sen Mây của tôi có thị trường mục tiêu chính là Malaysia.'
    first, _ = await chat(fact + ' Chỉ xác nhận đã nhận thông tin bằng một câu ngắn.')
    print('PASS real local chat A completed', flush=True)
    await extract_memory({}, first)
    async with Session() as db:
        job = await db.get(MemoryJob, first)
        assert job.status == 'completed' and job.extracted > 0, (job.status, job.error_code)
        facts = list(await db.scalars(select(Memory).where(Memory.source_run_id == first)))
        assert all(m.embedding is not None and len(m.embedding) == 768 for m in facts)
        assert all(m.value in fact for m in facts)
    print('PASS real structured extraction and 768-dimensional embeddings', flush=True)
    question = 'Thị trường mục tiêu chính của thương hiệu trà Sen Mây của tôi là nước nào? Trả lời một câu ngắn.'
    hits, degraded = await retrieve(*scope, question)
    assert not degraded and any('Malaysia' in m.value for m, _ in hits)
    assert await retrieve(scope[0], scope[1], None, question) == ([], False)
    second, answer = await chat(question)
    assert 'Malaysia' in answer, 'Recall response omitted the stored market'
    async with Session() as db:
        events = list(await db.scalars(select(RunEvent).where(RunEvent.run_id == second)))
        assert any(e.type == 'memory.search.completed' and e.data['count'] > 0 for e in events)
    report = {'database': 'pao_test', 'model': settings().ollama_model, 'embedding_model': settings().embedding_model,
              'embedding_dimensions': 768, 'facts': len(facts), 'cross_session_recall': True,
              'other_brand_excluded': True, 'elapsed_seconds': round(time.monotonic()-started, 1),
              'synthetic_answer': answer}
    Path('.runtime/phase-3-local-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True), flush=True)
    await engine.dispose()

asyncio.run(main())
