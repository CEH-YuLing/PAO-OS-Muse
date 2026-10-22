"""Characterize permission/outbox helpers without sending Telegram messages."""
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pao.modules.channels import telegram_helpers as service


def test_legacy_and_report_service_share_helpers():
    from pao import telegram
    from pao.modules.business import report_scheduler
    assert telegram.queue is report_scheduler.queue is service.queue
    assert telegram.permitted is report_scheduler.telegram_permitted is service.permitted


async def test_permission_matrix_and_disabled_short_circuit():
    for enabled, active, role, expected in (
        (False, True, 'owner', False), (True, False, 'owner', False),
        (True, True, 'viewer', False), (True, True, None, False),
        (True, True, 'owner', True), (True, True, 'admin', True),
        (True, True, 'operator', True),
    ):
        db = SimpleNamespace(scalar=AsyncMock(return_value=None),get=AsyncMock(side_effect=[
            SimpleNamespace(active=active), SimpleNamespace(role=role) if role else None]))
        peer = SimpleNamespace(id='peer',enabled=enabled, user_id='u', workspace_id='w')
        assert await service.permitted(db, peer) is expected
        assert db.get.await_count == (2 if enabled else 0)
    db = SimpleNamespace(scalar=AsyncMock(return_value=None),get=AsyncMock(side_effect=[None, None]))
    assert await service.permitted(db, None) is False
    db.get.assert_not_awaited()
    assert await service.permitted(db, SimpleNamespace(id='peer',enabled=True, user_id='u', workspace_id='w')) is False


async def test_queue_unicode_final_markup_and_empty_fallback():
    peer = SimpleNamespace(id='peer', chat_id='chat')
    db = SimpleNamespace(execute=AsyncMock(),scalar=AsyncMock(return_value=False))
    markup = {'inline_keyboard': [[{'text': 'Review', 'callback_data': 'example'}]]}
    text = '😀' * 4000
    await service.queue(db, peer, 'key', text, markup)
    statements = [call.args[0] for call in db.execute.await_args_list]
    values = [statement.compile().params for statement in statements]
    assert len(values) == 3
    assert ''.join(v['payload']['text'] for v in values) == text
    for index, (statement, value) in enumerate(zip(statements, values)):
        assert value['dedup_key'] == f'key:{index}'
        assert value['status'] == 'queued'
        assert value['peer_id'] == peer.id
        assert value['payload']['chat_id'] == peer.chat_id
        assert len(value['payload']['text'].encode('utf-16-le')) // 2 <= 3500
        assert value['payload']['link_preview_options'] == {'is_disabled': True}
        assert 'parse_mode' not in value['payload']
        assert ('reply_markup' in value['payload']) == (index == 2)
        assert 'ON CONFLICT (dedup_key) WHERE connection_id IS NULL DO NOTHING' in str(statement.compile())
    assert values[-1]['payload']['reply_markup'] == markup
    db.execute.reset_mock()
    await service.queue(db, peer, 'empty', '')
    assert db.execute.await_args.args[0].compile().params['payload']['text'] == 'Không có nội dung.'


def test_helpers_fresh_import_has_no_router_or_network():
    code = """
import socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('Helper import must not connect')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao.modules.channels import telegram_helpers
assert callable(telegram_helpers.queue) and callable(telegram_helpers.permitted)
for name in ('pao.telegram','pao.main','pao.app','pao.core_api',
             'pao.report_api','pao.warehouse_api'):
    assert name not in sys.modules, name
print('PASS helper import')
"""
    result = subprocess.run([sys.executable, '-c', code],
        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, check=True, timeout=20)
    assert 'PASS helper import' in result.stdout
