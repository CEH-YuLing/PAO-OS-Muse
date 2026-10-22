"""Real Temporal + PAO API/DB; only fixture step, no ARQ/provider/model call."""
import asyncio,json
from datetime import timedelta
from uuid import uuid4
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker,Replayer
from sqlalchemy import select,func
from pao.db import Session
from pao.config import ROOT,settings
from temporal_fixture import cached_binary
from pao.models import StudioCommand,TaskAttempt,Run
from pao.modules.studio import durable
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as W
from test_durable_admission import plan,start,BASE

@activity.defn(name='p62_dryrun_step')
async def fixture_step(data:dict):
    await durable.authorize_step(data['plan_id'],data['step_id'],data['execution_id'])
    return {'execution_id':data['execution_id'],'status':'completed','dry_run':True}

async def test_real_api_db_temporal_projection_and_replay(client,identity,monkeypatch):
    for key in ('studio_enabled','workflow_planning_enabled','workflow_durable_enabled','workflow_dispatch_enabled','temporal_enabled'):
        monkeypatch.setattr(settings(),key,True)
    queue='p62b-test-'+uuid4().hex;monkeypatch.setattr(settings(),'workflow_temporal_task_queue',queue)
    directory=ROOT/'.runtime'/('p62b-temporal-'+uuid4().hex);directory.mkdir()
    options={'dev_server_existing_path':cached_binary(ROOT)}
    async with await WorkflowEnvironment.start_local(ui=False,download_dest_dir=str(directory),
        dev_server_database_filename=str(directory/'temporal.sqlite'),**options) as env:
        monkeypatch.setattr(durable.gateway,'client',env.client)
        async with Worker(env.client,task_queue=queue,workflows=[W],activities=[durable.project_state,fixture_step],
                          graceful_shutdown_timeout=timedelta(seconds=2)):
            value=await plan(client,identity);body,response=await start(client,identity,value,timeout_seconds=30)
            assert response.status_code==202,response.text
            assert await durable.dispatch_commands()==1
            handle=env.client.get_workflow_handle('p62-'+value['plan_id'])
            for key in ('first','second'):
                for _ in range(150):
                    response=await client.get(BASE+'/executions/'+value['plan_id'],headers=identity['owner']);row=response.json()
                    if row['status']=='waiting_approval' and row['state'].get('current_step')==key:break
                    await asyncio.sleep(.1)
                else:raise AssertionError(row)
                decision={'request_key':str(uuid4()),'version':row['version'],'step_id':key,'decision':'approve'}
                response=await client.post(BASE+'/executions/'+value['plan_id']+'/decision',json=decision,headers=identity['owner'])
                assert response.status_code==200,response.text
                assert (await client.post(BASE+'/executions/'+value['plan_id']+'/decision',json=decision,headers=identity['owner'])).status_code==200
                assert await durable.dispatch_commands()==1
                assert await durable.dispatch_commands()==0
            result=await asyncio.wait_for(handle.result(),30);assert result['status']=='completed'
            response=await client.get(BASE+'/executions/'+value['plan_id'],headers=identity['owner']);assert response.json()['status']=='completed'
            async with Session() as db:
                commands=list(await db.scalars(select(StudioCommand)))
                assert len(commands)==3 and all(c.status=='delivered' for c in commands)
                assert await db.scalar(select(func.count(TaskAttempt.id)))==0
                assert await db.scalar(select(func.count(Run.id)))==0
            history=await handle.fetch_history()
        await Replayer(workflows=[W]).replay_workflow(history)
        (directory/'history.json').write_text(history.to_json(),encoding='utf-8')
        (directory/'report.json').write_text(json.dumps({'pass':True,'real_api_db_temporal':True,
            'commands':3,'projection_sequence':result['sequence'],'replay':True,'model_calls':0,'arq_jobs':0}),encoding='utf-8')
