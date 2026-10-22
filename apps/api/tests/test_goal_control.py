"""Pure P6.3A tests; NOT Temporal/API acceptance or authenticated receipts."""
from copy import deepcopy
from uuid import uuid4
import pytest
from pao.modules.goals.control import GoalControl, validate

NOW=1_800_000_000_000
def envelope():
    return {'format':'p63-dryrun-goal-v1','execution_id':str(uuid4()),'goal_id':str(uuid4()),'goal_version':1,'actor_id':str(uuid4()),
        'workspace_id':str(uuid4()),'plan_id':str(uuid4()),'snapshot_hash':'a'*64,
        'policy':{'max_iterations':2,'max_cost_microusd':10,'max_elapsed_seconds':60,'deadline_unix_ms':NOW+100000},
        'success_criteria':[{'field':'text','rule':'non_empty','value':None},{'field':'text','rule':'equals','value':'done'}]}
def proposal(e):
    return {'plan_id':e['plan_id'],'snapshot_hash':e['snapshot_hash'],'cost_ceiling_microusd':5,'max_duration_seconds':1}
def start(e=None):
    e=e or envelope();g=GoalControl(e,NOW);p=g.propose(proposal(e),NOW)
    g.decide(p['proposal_hash'],'approve',NOW);return e,g,p
def receipt(e,g,output='done'):
    s=g.snapshot()
    return {'execution_id':e['execution_id'],'iteration':s['iteration'],'proposal_hash':s['proposal_hash'],
        'output':{'text':output},'cost_microusd':0,'dry_run':True,'origin':'fixture_echo'}

def test_success_immutable_inputs_duplicate_receipts_and_late_proposals():
    e=envelope();original=deepcopy(e);e,g,p=start(e)
    r=receipt(e,g);out=g.finish(r,NOW+1);assert out['status']=='completed' and all(c['passed'] for c in out['checks'])
    assert g.finish(r,NOW+2)==out
    assert g.propose(proposal(e),NOW+3)==out
    out['status']='running';assert g.snapshot()['status']=='completed'
    assert e==original and r['output']=={'text':'done'}

def test_replan_needs_new_approval_and_cannot_extend_budget():
    e,g,p=start();assert g.finish(receipt(e,g,'not done'),NOW+1)['status']=='waiting_replan'
    new={**proposal(e),'plan_id':str(uuid4()),'snapshot_hash':'b'*64}
    candidate=g.propose(new,NOW+2);assert candidate['status']=='waiting_approval' and candidate['iteration']==1
    assert candidate['proposal_hash']!=p['proposal_hash']
    assert g.decide(p['proposal_hash'],'approve',NOW+3)['iteration']==1
    g.decide(candidate['proposal_hash'],'approve',NOW+4)
    assert g.finish(receipt(e,g,'still unmet'),NOW+5)['reason']=='iterations'
    assert g.propose(new,NOW+6)['status']=='budget_exhausted'
    assert g.snapshot()['deadline_unix_ms']==NOW+60000

@pytest.mark.parametrize('status',['before','running'])
def test_cancel_and_unknown_never_auto_retry(status):
    e=envelope();g=GoalControl(e,NOW);p=g.propose(proposal(e),NOW)
    if status=='running':
        g.decide(p['proposal_hash'],'approve',NOW)
        assert g.cancel(NOW+1)['status']=='running' and g.snapshot()['reserved_cost_microusd']==5
        assert g.finish(receipt(e,g),NOW+2)['status']=='cancelled'
    else:assert g.cancel(NOW+1)['status']=='cancelled'
    assert g.propose(proposal(e),NOW+3)['status']=='cancelled'
    _,u,_=start();assert u.uncertain(NOW+1)['status']=='manual_review'
    assert u.snapshot()['reserved_cost_microusd']==5
    assert u.propose(proposal(e),NOW+2)['status']=='manual_review'

@pytest.mark.parametrize('field,bad',[('max_iterations',True),('max_iterations',0),('max_iterations',21),
    ('max_cost_microusd',-1),('max_cost_microusd',1.5),('max_elapsed_seconds',0),
    ('max_elapsed_seconds',86401),('deadline_unix_ms',True)])
def test_strict_budget_policy(field,bad):
    e=envelope();e['policy'][field]=bad
    with pytest.raises(ValueError):validate(e)

@pytest.mark.parametrize('change',[{'format':'live'},{'goal_id':'bad'},{'snapshot_hash':'z'*64},
    {'command':'shell'},{'success_criteria':[]},
    {'success_criteria':[{'field':'text','rule':'python','value':'pass'}]},
    {'success_criteria':[{'field':'text','rule':'equals','value':'Bearer synthetic-secret-123456'}]}])
def test_closed_envelope_and_no_executable_criteria(change):
    with pytest.raises(ValueError):validate({**envelope(),**change})

def test_cost_reservation_and_approval_time_recheck():
    e=envelope();g=GoalControl(e,NOW)
    assert g.propose({**proposal(e),'cost_ceiling_microusd':11},NOW)['reason']=='cost'
    g=GoalControl(e,NOW);p=g.propose(proposal(e),NOW)
    assert g.decide(p['proposal_hash'],'approve',NOW+59500)['status']=='deadline_exceeded'
    assert g.snapshot()['iteration']==0 and g.snapshot()['reserved_cost_microusd']==0

def test_earliest_deadline_no_regression_or_late_success():
    e=envelope();e['policy']['deadline_unix_ms']=NOW+2000;e,g,p=start(e)
    assert g.snapshot()['deadline_unix_ms']==NOW+2000
    assert g.finish(receipt(e,g),NOW+2000)['status']=='deadline_exceeded'
    assert g.snapshot()['reserved_cost_microusd']==5
    with pytest.raises(ValueError):g.cancel(NOW)

def test_decision_idempotent_first_wins_and_pending_pin_is_immutable():
    e=envelope();g=GoalControl(e,NOW);p=g.propose(proposal(e),NOW)
    assert g.propose(proposal(e),NOW)==p
    with pytest.raises(ValueError):g.propose({**proposal(e),'plan_id':str(uuid4())},NOW)
    with pytest.raises(ValueError):g.decide('c'*64,'approve',NOW)
    g.decide(p['proposal_hash'],'approve',NOW)
    assert g.decide(p['proposal_hash'],'approve',NOW)['iteration']==1
    with pytest.raises(ValueError):g.decide(p['proposal_hash'],'reject',NOW)

@pytest.mark.parametrize('change',[{'origin':'model'},{'dry_run':False},{'cost_microusd':1},
    {'execution_id':str(uuid4())},{'iteration':True},{'proposal_hash':'c'*64},
    {'output':{'text':'done','tool_result':True}}])
def test_untrusted_receipt_freezes_reservation(change):
    e,g,_=start()
    with pytest.raises(ValueError):g.finish({**receipt(e,g),**change},NOW+1)
    assert g.snapshot()['status']=='manual_review' and g.snapshot()['reserved_cost_microusd']==5

def test_conflicting_duplicate_cannot_mutate_terminal_success():
    e,g,_=start();r=receipt(e,g);g.finish(r,NOW+1)
    with pytest.raises(ValueError):g.finish({**r,'output':{'text':'bad'}},NOW+2)
    assert g.snapshot()['status']=='completed'

def test_initial_plan_pin_and_receipt_before_approval():
    e=envelope();g=GoalControl(e,NOW)
    with pytest.raises(ValueError):g.propose({**proposal(e),'snapshot_hash':'b'*64},NOW)
    g.propose(proposal(e),NOW)
    with pytest.raises(ValueError):g.finish(receipt(e,g),NOW)
    assert g.snapshot()['status']=='manual_review'

def test_used_p62_plan_cannot_restart_for_a_replan():
    e,g,_=start();g.finish(receipt(e,g,'unmet'),NOW+1)
    with pytest.raises(ValueError,match='p63_plan_already_used'):g.propose(proposal(e),NOW+2)

def test_zero_budget_boundary_all_criteria_required_and_envelope_copy():
    e=envelope();e['policy']['max_cost_microusd']=0;g=GoalControl(e,NOW)
    p={**proposal(e),'cost_ceiling_microusd':0};out=g.propose(p,NOW)
    e['policy']['max_iterations']=20;out['proposal']['snapshot_hash']='b'*64
    g.decide(g.snapshot()['proposal_hash'],'approve',NOW)
    assert g.finish(receipt(e,g,' '),NOW+1)['status']=='waiting_replan'
    new={**p,'plan_id':str(uuid4())};s=g.propose(new,NOW+2)
    g.decide(s['proposal_hash'],'approve',NOW+3)
    assert g.finish(receipt(e,g,'unmet'),NOW+4)['reason']=='iterations'

@pytest.mark.parametrize('bad',[0,True,'1',2147483648])
def test_goal_version_pin_strict(bad):
    e=envelope();e['goal_version']=bad
    with pytest.raises(ValueError):validate(e)

def test_advance_deadline_does_not_invent_cancellation_ack():
    e,g,_=start()
    state=g.advance(NOW+60000)
    assert state['status']=='deadline_exceeded'
    assert state['reserved_cost_microusd']==5 and state['receipt_hash'] is None
    assert g.advance(NOW+60001)==state

def test_advance_is_monotonic_without_modifying_approval():
    e=envelope();g=GoalControl(e,NOW);s=g.propose(proposal(e),NOW)
    assert g.advance(NOW+1)==s
    with pytest.raises(ValueError,match='p63_clock_regressed'):g.advance(NOW)
