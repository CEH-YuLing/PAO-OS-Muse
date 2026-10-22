import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from pao.automation import project_workflow
from pao.automation_workflows import PaoAutomationWorkflow
from pao.config import settings

async def main():
    if not settings().temporal_enabled: return
    client=await Client.connect(settings().temporal_address,namespace=settings().temporal_namespace)
    worker=Worker(client,task_queue=settings().temporal_task_queue,workflows=[PaoAutomationWorkflow],activities=[project_workflow])
    await worker.run()
if __name__=='__main__':asyncio.run(main())
