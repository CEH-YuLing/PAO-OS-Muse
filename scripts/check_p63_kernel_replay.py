"""Replay retained P6.3B1 synthetic histories; never connects to DB/providers."""
import asyncio
import json
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer
from pao.config import ROOT
from pao.modules.goals.workflow import PaoBoundedDryRunGoalWorkflow
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow


async def main():
    paths = sorted((ROOT/'.runtime').glob('p63b1-temporal-*/*.json'))
    if not paths:
        raise SystemExit('No retained goal histories; run kernel tests first')
    replayer = Replayer(workflows=[PaoBoundedDryRunGoalWorkflow,PaoPlannedDryRunWorkflow])
    for path in paths:
        history = WorkflowHistory.from_json(path.stem,path.read_text(encoding='utf-8'))
        await replayer.replay_workflow(history)
    print(json.dumps({'pass':True,'synthetic_goal_and_child_histories':len(paths),
        'database_calls':0,'provider_calls':0,'db_api_acceptance':False}))


if __name__ == '__main__':
    asyncio.run(main())
