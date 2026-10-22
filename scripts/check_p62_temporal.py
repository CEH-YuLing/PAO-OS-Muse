"""Real isolated Temporal server/replay tests; fixture activities, no PAO DB/ARQ/providers.

SDK-managed server uses its own SQLite and loopback port18133, not7233. Retain
history/report, stop only this owned server. Never register in live workers.
"""
import asyncio,json,os
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker,Replayer
from temporalio.exceptions import ApplicationError
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as W,validate_command

records={};calls=[];uncertain=set();blocking=set()
@activity.defn(name='p62_project')
async def project(data:dict):
    key=(data['plan_id'],data['sequence'])
    if key in records:assert records[key]==data
    records[key]=data

@activity.defn(name='p62_dryrun_step')
async def step(data:dict):
    calls.append(data['execution_id'])
    if data['plan_id'] in uncertain:raise ApplicationError('fixture uncertain',non_retryable=True)
    if data['plan_id'] in blocking:
        for _ in range(600):
            activity.heartbeat('fixture running')
            await asyncio.sleep(.1)
    return {'execution_id':data['execution_id'],'status':'completed','dry_run':True}

def command(*,approval=False,delay=0,timeout=20):
    return {'format':'p62-dryrun-v1','plan_id':str(uuid4()),'snapshot_hash':'a'*64,'timeout_seconds':timeout,
            'steps':[{'step_id':key,'execution_id':str(uuid4()),'depends_on':deps,
                      'approval_required':approval if key=='first' else False,'delay_seconds':delay if key=='first' else 0}
                     for key,deps in [('first',[]),('second',['first'])]]}

async def wait(handle,status):
    for _ in range(100):
        state=await handle.query(W.state)
        if state['status']==status:return state
        await asyncio.sleep(.1)
    raise AssertionError(f'Expected {status}, got {state}')

async def main():
    root=Path(os.environ['PAO_ROOT']).resolve();assert root==Path('F:/PAO-ACOS')
    directory=root/'.runtime'/('p62-temporal-'+uuid4().hex);directory.mkdir()
    queue='p62-check-'+uuid4().hex;histories=[]
    def worker(client):return Worker(client,task_queue=queue,workflows=[W],activities=[project,step],graceful_shutdown_timeout=timedelta(seconds=2))
    async with await WorkflowEnvironment.start_local(port=18133,ui=False,download_dest_dir=str(directory),
            dev_server_database_filename=str(directory/'temporal.sqlite')) as env:
        async def start(item):
            handle=await env.client.start_workflow(W.run,item,id='p62-'+item['plan_id'],task_queue=queue,
                execution_timeout=timedelta(seconds=90));histories.append(handle);return handle
        # Persist approval wait, remove first worker, signal while no worker,
        # then replay on a new worker with the same queue/history.
        async with worker(env.client):
            item=command(approval=True);handle=await start(item);await wait(handle,'waiting_approval')
        decision={'step_id':'first','decision':'approve','decision_id':str(uuid4())}
        await handle.signal(W.decide,decision);await handle.signal(W.decide,decision)
        await handle.signal(W.decide,{**decision,'decision':'reject'})
        async with worker(env.client):
            result=await asyncio.wait_for(handle.result(),30);assert result['status']=='completed'
            assert result['completed_steps']==['first','second']
            assert all(calls.count(s['execution_id'])==1 for s in item['steps'])
            timer=command(delay=2);h=await start(timer);await wait(h,'waiting_timer')
        # Restart worker while Temporal owns the timer.
        async with worker(env.client):
            assert (await asyncio.wait_for(h.result(),30))['status']=='completed'
            rejected=command(approval=True);h=await start(rejected);await wait(h,'waiting_approval')
            await h.signal(W.decide,{'step_id':'first','decision':'reject','decision_id':str(uuid4())})
            assert (await h.result())['reason']=='rejected'
            assert all(s['execution_id'] not in calls for s in rejected['steps'])
            cancel=command(delay=10);h=await start(cancel);await wait(h,'waiting_timer')
            await h.signal(W.request_cancel);await h.signal(W.request_cancel)
            assert (await h.result())['status']=='cancelled'
            assert all(s['execution_id'] not in calls for s in cancel['steps'])
            timeout=command(approval=True,timeout=1);h=await start(timeout)
            assert (await h.result())['reason']=='approval_timeout'
            unknown=command();uncertain.add(unknown['plan_id']);h=await start(unknown)
            assert (await h.result())['status']=='manual_review'
            assert calls.count(unknown['steps'][0]['execution_id'])==1
            assert unknown['steps'][1]['execution_id'] not in calls
            active=command();blocking.add(active['plan_id']);h=await start(active);await wait(h,'running')
            # Ensure the fixture step has entered before cancellation.
            for _ in range(100):
                if active['steps'][0]['execution_id'] in calls:break
                await asyncio.sleep(.1)
            else:raise AssertionError('Step never entered')
            await h.signal(W.request_cancel)
            assert (await h.result())['reason']=='requested_during_step'
            assert active['steps'][1]['execution_id'] not in calls
        replay=Replayer(workflows=[W])
        for handle in histories:
            history=await handle.fetch_history();await replay.replay_workflow(history)
            (directory/(handle.id+'.json')).write_text(history.to_json(),encoding='utf-8')
        invalid=command();invalid['steps'][0]['depends_on']=['second']
        try:validate_command(invalid)
        except ValueError:pass
        else:raise AssertionError('Invalid DAG accepted')
        report={'pass':True,'real_temporal_histories':len(histories),'replayed':len(histories),
                'worker_restarts':2,'provider_calls':0,'database_writes':0,'live_registered':False,
                'scope':'P6.2A kernel only; fixture activities, not DB projection or ARQ bridge'}
        (directory/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({**report,'report_path':str(directory/'report.json')}))

if __name__=='__main__':asyncio.run(main())
