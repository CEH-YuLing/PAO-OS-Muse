"""Read-only replay of retained P6.2A fixture histories with current kernel."""
import asyncio,json
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer
from pao.config import ROOT
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as W

async def main():
    paths=sorted((ROOT/'.runtime/p62-temporal-2e2521227f744558bfb631b05736c66e').glob('p62-*.json'))
    assert len(paths)==7
    replayer=Replayer(workflows=[W])
    for path in paths:await replayer.replay_workflow(WorkflowHistory.from_json(path.stem,path.read_text(encoding='utf-8')))
    print(json.dumps({'pass':True,'historical_p62a_replays':len(paths),'database_calls':0,'provider_calls':0}))
if __name__=='__main__':asyncio.run(main())
