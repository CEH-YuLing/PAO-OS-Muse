"""Populate HTTP-backed local inbox + promoted note for owned restore checks."""
from test_durable_admission import gates
from test_brain_manager import brains_on
from test_result_inbox import terminal
from test_learning_review import fixture


async def test_populated_p6_review_restore_fixture(client,identity,gates,brains_on,monkeypatch):
    value=await terminal(client,identity,monkeypatch)
    items=await client.get('/v1/results?workspace_id='+identity['workspace'],headers=identity['owner'])
    assert items.status_code==200
    item=items.json()[0];base='/v1/results/'+value['plan_id']
    receipt=await client.post(base+'/receipt',headers=identity['owner'],json={
        'source_hash':item['source_hash'],'action':'ack'})
    assert receipt.status_code==200 and receipt.json()['acknowledged']
    delivery=await client.post(base+'/deliveries',headers=identity['owner'],json={
        'source_hash':item['source_hash'],'recipient_id':identity['user_id'],'destination':'in_app'})
    assert delivery.status_code==200 and delivery.json()['status']=='delivered'
    brain,body=await fixture(client,identity,monkeypatch)
    proposed=await client.post('/v1/learning/brains/'+brain['id']+'/proposals',headers=identity['owner'],json=body)
    assert proposed.status_code==200
    row=proposed.json()
    reviewed=await client.post('/v1/learning/proposals/'+row['id']+'/review',headers=identity['owner'],json={
        'fingerprint':row['fingerprint'],'decision':'promote'})
    assert reviewed.status_code==200 and reviewed.json()['status']=='promoted'
