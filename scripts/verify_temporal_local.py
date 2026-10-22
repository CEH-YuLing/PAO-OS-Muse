"""Run a real Temporal approval workflow without writing synthetic rows to PAO DB."""
import asyncio,json
from pathlib import Path
from uuid import uuid4
from temporalio.client import Client
from pao.automation_workflows import PaoAutomationWorkflow
from pao.config import settings

async def main():
    client=await Client.connect(settings().temporal_address,namespace=settings().temporal_namespace)
    key=f'pao-phase17-smoke-{uuid4()}'
    item={'id':str(uuid4()),'kind':'approval_wait','payload':{'synthetic':True},'approval_required':True,'approval_timeout_hours':1,'wait_until':None}
    handle=await client.start_workflow(PaoAutomationWorkflow.run,item,id=key,task_queue=settings().temporal_task_queue)
    await handle.signal(PaoAutomationWorkflow.approve,{'actor_id':'phase17-smoke','version':1})
    result=await asyncio.wait_for(handle.result(),timeout=30)
    assert result['completed'] is True
    report={'workflow_id':key,'run_id':handle.first_execution_run_id,'result':result}
    Path('.runtime/phase-17-temporal-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
asyncio.run(main())
