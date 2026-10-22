"""Restore populated inbox/learning test ledger into one owned clone only."""
import asyncio,hashlib,json
from uuid import uuid4,UUID,uuid5
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import ResultInboxReceipt,ResultDelivery,LearningProposal,LearningAudit,BrainNoteVersion,Message,StudioExecution,StudioEvent,Member,ChatSession
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            receipts=list(await db.scalars(select(ResultInboxReceipt)));assert len(receipts)==1
            receipt=receipts[0];assert receipt.ack_at is not None
            child=await db.get(StudioExecution,receipt.source_id);assert child.status=='cancelled'
            event=await db.get(StudioEvent,str(uuid5(UUID(child.id),'projection:'+str(child.sequence))))
            assert event.workspace_id==receipt.workspace_id==child.workspace_id and event.data['state']==child.state
            assert receipt.source_hash==digest({'event_id':event.id,'data':event.data})
            deliveries=list(await db.scalars(select(ResultDelivery)));assert len(deliveries)==1
            delivery=deliveries[0]
            assert delivery.status=='delivered' and delivery.destination=='in_app' and delivery.delivered_at
            assert (delivery.source_id,delivery.source_hash,delivery.user_id,delivery.workspace_id)==(receipt.source_id,receipt.source_hash,receipt.user_id,receipt.workspace_id)
            rows=list(await db.scalars(select(LearningProposal)));assert len(rows)==1
            row=rows[0];assert row.status=='promoted'
            source=await db.get(Message,row.source_id);session=await db.get(ChatSession,source.session_id)
            assert source.workspace_id==row.workspace_id and session.user_id==row.actor_id
            member=await db.get(Member,(row.workspace_id,row.actor_id));assert member and member.role=='owner'
            source_hash=digest({'id':source.id,'session_id':source.session_id,'content':source.content,'role':source.role})
            assert row.source_hash==source_hash and row.candidate in source.content
            assert row.fingerprint==digest({'source_hash':source_hash,'candidate':row.candidate})
            note=await db.get(BrainNoteVersion,(row.note_id,1))
            assert note.content==row.candidate and note.sha256==hashlib.sha256(note.content.encode()).hexdigest()
            audits=list(await db.scalars(select(LearningAudit)));assert len(audits)==2
            assert {a.action for a in audits}=={'proposed','promoted'}
            for a in audits:assert a.proposal_id==row.id and a.actor_id==row.actor_id and a.data['source_hash']==source_hash
        if probe:
            for statement in ("UPDATE learning_proposals SET candidate='tampered'", "UPDATE learning_audits SET data='{}'::json"):
                try:
                    async with engine.begin() as db:await db.execute(text(statement))
                except DBAPIError:pass
                else:raise AssertionError('Restored learning immutable trigger missing')
    finally:await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');columns,before=await snapshot(source)
    await inspect(source)
    name='pao_p6_review_restore_'+uuid4().hex;dump=ROOT/'.runtime'/('p6-review-'+uuid4().hex+'.dump')
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name)
        assert (await snapshot(target,columns))[1]==before
        await inspect(target,True)
        assert (await snapshot(target,columns))[1]==before
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'revision':'0041','tables':len(columns),'hash_exact':True,
            'inbox_receipt_delivery_restored':True,'learning_source_note_audit_restored':True,
            'immutable_triggers_verified':True,'external_send':False,'primary_unchanged':True}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
