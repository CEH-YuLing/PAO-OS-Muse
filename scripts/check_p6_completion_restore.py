"""P6.5–P6.7 owned-clone migration and populated restore verification."""
import argparse,asyncio,hashlib,json,os,re,subprocess,sys
from uuid import uuid4
from pathlib import Path
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import GoalExecution,GoalResultReceipt,GoalResultDelivery,ResultInboxReceipt,ResultDelivery,ArtifactLearningProposal,ArtifactLearningAudit,BrainNoteVersion,OutcomeObservation
from pao.modules.goals.evidence import verify_admission
from pao.modules.goals import runner
from pao.modules.studio.contracts import digest
from pao.auth import Principal
from pao.modules.results.api import source as result_source
from pao.modules.learning.artifacts import source as artifact_source,derive,ArtifactInput
from pao.models import Brain
from check_p11_migration import docker,snapshot,CONTAINER
from check_studio_schedule_restore import revision,migrate
from check_goal_schedule_restore import restored_clone
from pao.modules.operations.checkpoint import digest as file_digest,verify
from pao.skills import execution_binding

NEW={'goal_result_receipts','goal_result_deliveries','artifact_learning_proposals','artifact_learning_audits','outcome_observations'}

async def populated(url):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            goal=await db.scalar(select(GoalExecution));assert goal.status=='completed'
            await verify_admission(db,goal)
            assert (await runner.reconstruct(db,goal)).snapshot()['iteration']==1
            receipt=await db.scalar(select(GoalResultReceipt));assert receipt.ack_at and receipt.source_id==goal.id
            who=Principal(id=receipt.user_id,expires=0)
            assert (await result_source(db,goal.id,who))[1]==receipt.source_hash
            delivery=await db.scalar(select(GoalResultDelivery));assert delivery.status=='delivered' and delivery.attempts==1
            assert delivery.source_hash==receipt.source_hash and delivery.source_id==goal.id
            studio_receipt=await db.scalar(select(ResultInboxReceipt));assert studio_receipt.ack_at
            assert (await result_source(db,studio_receipt.source_id,who))[1]==studio_receipt.source_hash
            pending=await db.scalar(select(ResultDelivery));assert pending.status=='pending' and pending.attempts==0
            proposal=await db.scalar(select(ArtifactLearningProposal));assert proposal.status=='promoted' and len(proposal.segments)==2
            brain=await db.get(Brain,proposal.brain_id)
            _,content,source_hash=await artifact_source(db,who,brain,proposal.source_id)
            assert source_hash==proposal.source_hash
            body=ArtifactInput(source_id=proposal.source_id,derivation=proposal.derivation,segments=[{'start':s['start'],'end':s['end']} for s in proposal.segments])
            candidate,segments,fingerprint=derive(body,content,source_hash)
            assert (candidate,segments,fingerprint)==(proposal.candidate,proposal.segments,proposal.fingerprint)
            note=await db.get(BrainNoteVersion,(proposal.note_id,1));assert note.content==proposal.candidate
            assert note.sha256==hashlib.sha256(note.content.encode()).hexdigest()
            audits=list(await db.scalars(select(ArtifactLearningAudit)));assert {a.action for a in audits}=={'proposed','promoted'}
            assert all(a.proposal_id==proposal.id for a in audits)
            observation=await db.scalar(select(OutcomeObservation))
            assert observation.source_hash==digest(observation.snapshot)
            assert all(v['status']=='observed' and not v['causal_effect_proven'] for v in observation.snapshot['outcomes'].values())
        for statement in ("UPDATE artifact_learning_proposals SET candidate='tampered'",'DELETE FROM artifact_learning_audits','DELETE FROM outcome_observations'):
            try:
                async with engine.begin() as db:await db.execute(text(statement))
            except DBAPIError:pass
            else:raise AssertionError('Restored immutable trigger missing')
    finally:await engine.dispose()

async def apply_primary(url,manifest):
    path=Path(manifest).resolve()
    assert path.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    saved=json.loads(path.read_text(encoding='utf-8'))
    assert saved['database']['revision_before']=='0043' and saved['binding']==execution_binding()
    dump=Path(saved['database']['backup']).resolve();archive=Path(saved['source']['path']).resolve()
    assert dump.is_relative_to((ROOT/'.runtime').resolve()) and archive.is_relative_to(path.parent)
    assert file_digest(dump)==saved['database']['sha256'] and file_digest(archive)==saved['source']['sha256']
    verify(archive,saved['source']['files'])
    assert await revision(url)=='0043'
    columns,before=await snapshot(url)
    async def identical(target):
        assert await revision(target)=='0043' and await snapshot(target)==(columns,before)
    await restored_clone(url,url,dump,identical)
    assert await snapshot(url)==(columns,before)
    migrate(url,'upgrade','0046');migrate(url,'check')
    new_columns,new_rows=await snapshot(url)
    assert (await snapshot(url,columns))[1]==before and await revision(url)=='0046'
    assert set(new_columns)-set(columns)==NEW and all(new_rows[t]['count']==0 for t in NEW)
    print(json.dumps({'pass':True,'mode':'verified_primary_rollout','revision':'0046','legacy_tables':len(columns),
        'old_rows_hash_exact':True,'new_tables_empty':True,'external_send':False}))

async def main(migration,manifest=None):
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    if manifest:return await apply_primary(url,manifest)
    primary=await snapshot(url);source=url if migration else url.set(database='pao_test')
    columns,before=await snapshot(source)
    assert await revision(source)==('0043' if migration else '0046')
    if not migration:await populated(source)
    name='pao_p6_completion_restore_'+uuid4().hex
    assert re.fullmatch('pao_p6_completion_restore_[0-9a-f]{32}',name)
    dump=ROOT/'.runtime'/('p6-completion-'+uuid4().hex+'.dump');created=False
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d',source.database,'-Fc',stdout=output)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name);assert await snapshot(target)==(columns,before)
        if migration:
            migrate(target,'upgrade','0046');migrate(target,'check')
            assert (await snapshot(target,columns))[1]==before
            new_columns,new_rows=await snapshot(target)
            assert set(new_columns)-set(columns)==NEW and all(new_rows[t]['count']==0 for t in NEW)
            migrate(target,'downgrade','0043');assert await snapshot(target)==(columns,before)
            migrate(target,'upgrade','0046');migrate(target,'check')
            assert (await snapshot(target,columns))[1]==before
        else:
            await populated(target);assert await snapshot(target)==(columns,before)
            env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False),'RESULT_INBOX_ENABLED':'true'}
            code="import asyncio;from pao.modules.results.outbox import dispatch_results;from pao.db import engine\nasync def main():\n assert (await dispatch_results())['processed']==1\n assert (await dispatch_results())['processed']==0\n await engine.dispose()\nasyncio.run(main())"
            subprocess.run([sys.executable,'-c',code],env=env,check=True,timeout=30)
            after=(await snapshot(target))[1]
            assert all(after[t]==before[t] for t in columns if t!='result_deliveries')
            engine=create_async_engine(target)
            try:
                async with engine.connect() as db:
                    assert await db.scalar(text("SELECT count(*) FROM result_deliveries WHERE status='delivered' AND attempts=1"))==1
            finally:await engine.dispose()
        assert await snapshot(source)==(columns,before) and await snapshot(url)==primary
        print(json.dumps({'pass':True,'mode':'0043_0046_clone_roundtrip' if migration else 'populated_p6_restore_and_outbox_restart','tables':len(columns),'source_hash_exact':True,'primary_unchanged':True,'external_send':False,'dump_retained':True}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--migration',action='store_true');parser.add_argument('--apply-manifest')
    args=parser.parse_args()
    if args.migration and args.apply_manifest:parser.error('Choose clone roundtrip or verified primary rollout, not both')
    asyncio.run(main(args.migration,args.apply_manifest))
