"""Owner consent UI uses native HTTP/DB; no Telegram provider I/O."""
from sqlalchemy import select,func
from pao.config import ROOT
from pao.db import Session
from pao.models import Workspace,Member,TelegramLegacyMapping,TelegramLegacyMappingAudit,TelegramDelivery,ChannelOutbox,TelegramPeer,ChannelBinding,TelegramLegacyPeerMap
from pao.modules.operations.checkpoint import digest
from test_telegram_legacy_mapping import legacy
from p6_browser_harness import browser

async def test_telegram_mapping_owner_lost_ack_scope_and_revoke(client,legacy):
    c=legacy;env_before=digest(ROOT/'.env')
    async with Session.begin() as db:
        second=Workspace(name='Operator SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=c['user_id'],role='operator'));wid=second.id
    report=await browser('scripts/verify_s31b_browser.cjs','PAO_TELEGRAM_MAPPING_BROWSER',{'workspace':c['workspace'],'second':wid},'s31b-mapping')
    assert all(report[key] for key in ('malformed_denied','two_consents','lost_ack_no_retry','manual_get_recovery','owner_revoke','operator_no_mapping_get','late_scope_denied','mobile_controls'))
    assert not report['real_provider_calls'] and digest(ROOT/'.env')==env_before
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramLegacyMapping))==1
        assert await db.scalar(select(func.count()).select_from(TelegramLegacyMappingAudit))==2
        assert sorted(row.status for row in await db.scalars(select(TelegramDelivery)))==['queued','unknown']
        assert all(row.status in ('queued','unknown') and row.attempts==0 for row in await db.scalars(select(ChannelOutbox)))
        link=await db.scalar(select(TelegramLegacyPeerMap))
        peer=await db.get(TelegramPeer,link.peer_id);binding=await db.get(ChannelBinding,link.binding_id)
        assert not peer.enabled and peer.session_id is None
        assert not binding.enabled and not binding.outbound_confirmed and binding.brain_id is binding.session_id is None
