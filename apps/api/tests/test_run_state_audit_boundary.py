"""P0.3C characterization of shared run state and append-only tool audit."""
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pao.modules.conversations import state
from pao.modules.tools.audit import audit


def test_compatibility_and_http_share_state_not_runtime():
    from pao import runtime, core_api, tool_gateway
    assert runtime.finish is core_api.finish is state.finish
    assert runtime.emit is core_api.emit is state.emit
    assert runtime.TERMINAL is core_api.TERMINAL is state.TERMINAL
    assert tool_gateway.audit is audit


def test_emit_increments_sequence_and_preserves_scope():
    rows = []
    run = SimpleNamespace(id='run', workspace_id='workspace', next_seq=3)
    state.emit(SimpleNamespace(add=rows.append), run, 'run.started', {'safe': True})
    assert run.next_seq == 4
    assert (rows[0].run_id, rows[0].workspace_id, rows[0].seq) == ('run', 'workspace', 3)
    assert rows[0].data == {'safe': True}


async def test_finish_terminal_is_noop():
    db = SimpleNamespace(scalars=AsyncMock())
    run = SimpleNamespace(status='completed')
    assert await state.finish(db, run, 'failed', 'ignored') is None
    db.scalars.assert_not_awaited()
    assert run.status == 'completed'


async def test_finish_closes_agents_response_and_events_without_committing(monkeypatch):
    rows = []
    agent = SimpleNamespace(status='running', agent_key='chief_of_staff', id='agent', output='')
    db = SimpleNamespace(add=rows.append, scalars=AsyncMock(return_value=[agent]),
                         get=AsyncMock(), commit=AsyncMock())
    run = SimpleNamespace(id='run', workspace_id='workspace', session_id='session',
                          status='running', response='safe response', next_seq=10)
    monkeypatch.setattr(state, 'settings', lambda: SimpleNamespace(memory_enabled=False))
    await state.finish(db, run, 'completed')
    assert run.status == agent.status == 'completed'
    assert agent.output == 'safe response'
    events = [row for row in rows if hasattr(row, 'seq')]
    assert [row.type for row in events] == ['agent.completed','response.completed','core.standby','run.completed']
    assert [row.seq for row in events] == [10,11,12,13]
    assert run.next_seq == 14
    assert any(getattr(row, 'role', None) == 'assistant' for row in rows)
    db.commit.assert_not_awaited()
    db.get.assert_not_awaited()


def test_tool_audit_preserves_actor_and_call_without_transaction():
    rows=[]
    db=SimpleNamespace(add=rows.append)
    run=SimpleNamespace(id='run',workspace_id='workspace')
    audit(db,run,'actor','tool.claimed',SimpleNamespace(id='call'), reason='safe')
    row=rows[0]
    assert (row.workspace_id,row.run_id,row.actor_id,row.tool_call_id)==('workspace','run','actor','call')
    assert row.event=='tool.claimed' and row.data=={'reason':'safe'}


def test_state_audit_fresh_import_avoids_http_and_runtime():
    code = """
import socket, sys
def forbidden(*args, **kwargs): raise AssertionError('Unexpected network')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao.modules.conversations.state import emit, finish
from pao.modules.tools.audit import audit
for name in ('pao.runtime','pao.core_api','pao.main','pao.tool_gateway','pao.tool_api'):
    assert name not in sys.modules, name
print('PASS state audit boundary')
"""
    result=subprocess.run([sys.executable,'-c',code],
        env={**os.environ,'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1'},
        capture_output=True,text=True,check=True,timeout=20)
    assert 'PASS state audit boundary' in result.stdout
