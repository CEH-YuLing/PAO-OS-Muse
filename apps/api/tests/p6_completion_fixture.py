"""Explicit populated P6 restore ledger; isolated pao_test only, no live Ads."""
from unittest.mock import AsyncMock
from pao.config import settings
from test_durable_admission import gates
from test_goal_admission import goal_gates
from test_goal_iterations import iteration_gates
from test_goal_runner import runner_gates,stack,admission,approve,approve_steps,wait
from test_goal_temporal_kernel import temporal
from test_brain_manager import brains_on
from test_brain_files import upload
from test_learning_review import fixture as conversation
from test_artifact_learning import proposal
from test_outcome_observations import fixture as outcomes,preview,payload
from test_meta import meta
from pao.modules.results import outbox


async def test_populated_completion(client,identity,gates,runner_gates,temporal,brains_on,meta,monkeypatch):
    monkeypatch.setattr(settings(),'result_inbox_enabled',True)
    async with stack(temporal[0],monkeypatch) as (worker,_):
        async with worker():
            _,plan,row,_=await admission(client,identity,target='Fixture planning')
            await approve(client,identity,row)
            await approve_steps(client,identity,plan['plan_id'])
            await wait(client,identity,row,'completed')
    items=(await client.get('/v1/results',params={'workspace_id':identity['workspace']},headers=identity['owner'])).json()
    goal=next(i for i in items if i['source']=='goal_dry_run')
    base='/v1/results/'+goal['id']
    r=await client.post(base+'/receipt',headers=identity['owner'],json={'source_hash':goal['source_hash'],'action':'ack'})
    assert r.status_code==200 and r.json()['acknowledged']
    r=await client.post(base+'/deliveries',headers=identity['owner'],json={'source_hash':goal['source_hash'],'recipient_id':identity['user_id']})
    assert r.status_code==200 and r.json()['status']=='delivered'
    # Use the runner's genuinely completed Studio child. Creating another
    # fixture workflow here would duplicate its fixed test slug.
    items=(await client.get('/v1/results',params={'workspace_id':identity['workspace']},headers=identity['owner'])).json()
    studio=next(i for i in items if i['source']=='studio_dry_run')
    r=await client.post('/v1/results/'+studio['id']+'/receipt',headers=identity['owner'],json={'source_hash':studio['source_hash'],'action':'ack'})
    assert r.status_code==200
    original=outbox.dispatch_one
    monkeypatch.setattr(outbox,'dispatch_one',AsyncMock())
    r=await client.post('/v1/results/'+studio['id']+'/deliveries',headers=identity['owner'],json={'source_hash':studio['source_hash'],'recipient_id':identity['user_id']})
    assert r.status_code==200 and r.json()['status']=='pending'
    monkeypatch.setattr(outbox,'dispatch_one',original)
    brain,body=await conversation(client,identity,monkeypatch)
    r=await client.post('/v1/learning/brains/'+brain['id']+'/proposals',headers=identity['owner'],json=body)
    assert r.status_code==200
    learned=r.json()
    r=await client.post('/v1/learning/proposals/'+learned['id']+'/review',headers=identity['owner'],json={'fingerprint':learned['fingerprint'],'decision':'promote'})
    assert r.status_code==200
    content='Tài liệu nguồn để phục hồi.\nNgân sách cần được chủ sở hữu duyệt.'
    file=await upload(client,identity,brain['id'],content=content.encode())
    assert file.status_code==201
    split=content.index('\n')
    learned,_=await proposal(client,identity,brain,{'source_id':file.json()['id'],'derivation':'extractive_summary_v1','segments':[{'start':0,'end':split},{'start':split+1,'end':len(content)}]})
    r=await client.post('/v1/learning/artifact-proposals/'+learned['id']+'/review',headers=identity['owner'],json={'fingerprint':learned['fingerprint'],'decision':'promote'})
    assert r.status_code==200
    ident,_,_=await outcomes(identity,monkeypatch)
    value=await preview(client,identity,ident)
    r=await client.post('/v1/ads/actions/'+ident+'/outcome-observations',headers=identity['owner'],json=payload(value))
    assert r.status_code==201 and all(s=='observed' for s in r.json()['statuses'].values())
