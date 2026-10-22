"""P6.3A pure reducer: no DB, clock, model, tools, queue or authorization.

Timestamps must later come from Temporal. Receipts must later come from the
trusted DB adapter: hashes bind data, not authenticity. Echo cost is zero;
reservations are conservative ceilings, not measured model billing.
"""
from copy import deepcopy
import hashlib
import json
import re
from uuid import UUID

TERMINAL={'completed','cancelled','budget_exhausted','deadline_exceeded','manual_review'}

def fail(code):raise ValueError(code)

def closed(value,keys):
    if type(value) is not dict or set(value)!=set(keys):fail('p63_contract_invalid')

def integer(value,lo,hi):
    if type(value) is not int or not lo<=value<=hi:fail('p63_integer_invalid')

def uuid(value):
    if type(value) is not str:fail('p63_uuid_invalid')
    try:
        if str(UUID(value))!=value:fail('p63_uuid_invalid')
    except (ValueError,AttributeError):fail('p63_uuid_invalid')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
        ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def pin(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value):fail('p63_pin_invalid')

def text(value):
    if type(value) is not str or len(value)>4096 or any(ord(c)<32 for c in value):fail('p63_text_invalid')
    if re.search(r'(?i)(Bearer\s+\S{12,}|sk-[\w-]{12,}|-----BEGIN .*PRIVATE KEY)',value):fail('p63_text_unsafe')

def validate(value):
    closed(value,{'format','execution_id','goal_id','goal_version','actor_id','workspace_id','plan_id','snapshot_hash','policy','success_criteria'})
    if value['format']!='p63-dryrun-goal-v1':fail('p63_dryrun_only')
    for k in ('execution_id','goal_id','actor_id','workspace_id','plan_id'):uuid(value[k])
    integer(value['goal_version'],1,2_147_483_647)
    pin(value['snapshot_hash']);p=value['policy']
    closed(p,{'max_iterations','max_cost_microusd','max_elapsed_seconds','deadline_unix_ms'})
    integer(p['max_iterations'],1,20);integer(p['max_cost_microusd'],0,1_000_000_000)
    integer(p['max_elapsed_seconds'],1,86400);integer(p['deadline_unix_ms'],0,253402300799000)
    criteria=value['success_criteria']
    if type(criteria) is not list or not 1<=len(criteria)<=5:fail('p63_criteria_invalid')
    seen=set()
    for c in criteria:
        closed(c,{'field','rule','value'})
        if c['field']!='text' or c['rule'] not in ('non_empty','equals'):fail('p63_criteria_subset')
        if c['rule']=='non_empty':
            if c['value'] is not None:fail('p63_criteria_invalid')
        else:text(c['value'])
        signature=digest(c)
        if signature in seen:fail('p63_criteria_duplicate')
        seen.add(signature)

class GoalControl:
    """One approval per iteration; never automatically replan/retry UNKNOWN."""
    def __init__(self,envelope,started_unix_ms):
        validate(envelope);integer(started_unix_ms,0,253402300799000)
        self._envelope=deepcopy(envelope)
        self._deadline=min(envelope['policy']['deadline_unix_ms'],
            started_unix_ms+envelope['policy']['max_elapsed_seconds']*1000)
        self._now=started_unix_ms
        self._state={'status':'ready','reason':None,'iteration':0,'cost_microusd':0,
            'reserved_cost_microusd':0,'cancel_requested':False,'proposal':None,
            'proposal_hash':None,'checks':[],'receipt_hash':None}
        self._decisions={};self._receipts={};self._approved_plans=set()

    def snapshot(self):
        return deepcopy({**self._state,'execution_id':self._envelope['execution_id'],
            'deadline_unix_ms':self._deadline,'dry_run':True,'model_executed':False})

    def advance(self,now):
        """Check the pinned deadline without inventing an execution outcome."""
        self._tick(now)
        return self.snapshot()

    def _tick(self,now):
        integer(now,0,253402300799000)
        if now<self._now:fail('p63_clock_regressed')
        self._now=now
        if self._state['status'] in TERMINAL:return False
        if now>=self._deadline:
            self._state.update(status='deadline_exceeded',reason='deadline');return False
        return True

    def propose(self,proposal,now):
        closed(proposal,{'plan_id','snapshot_hash','cost_ceiling_microusd','max_duration_seconds'})
        uuid(proposal['plan_id']);pin(proposal['snapshot_hash'])
        integer(proposal['cost_ceiling_microusd'],0,1_000_000_000)
        integer(proposal['max_duration_seconds'],1,120)
        if not self._tick(now):return self.snapshot()
        s=self._state
        if s['status']=='waiting_approval':
            if s['proposal']==proposal:return self.snapshot()
            fail('p63_pending_proposal_conflict')
        if s['status'] not in ('ready','waiting_replan'):fail('p63_not_plannable')
        if proposal['plan_id'] in self._approved_plans:fail('p63_plan_already_used')
        if not s['iteration'] and (proposal['plan_id']!=self._envelope['plan_id'] or
                proposal['snapshot_hash']!=self._envelope['snapshot_hash']):fail('p63_initial_pin_mismatch')
        p=self._envelope['policy']
        if s['iteration']>=p['max_iterations']:
            s.update(status='budget_exhausted',reason='iterations');return self.snapshot()
        if s['cost_microusd']+proposal['cost_ceiling_microusd']>p['max_cost_microusd']:
            s.update(status='budget_exhausted',reason='cost');return self.snapshot()
        if now+proposal['max_duration_seconds']*1000>self._deadline:
            s.update(status='deadline_exceeded',reason='insufficient_time');return self.snapshot()
        s.update(status='waiting_approval',proposal=deepcopy(proposal),proposal_hash=digest({
            'envelope_hash':digest(self._envelope),'iteration':s['iteration']+1,'proposal':proposal}))
        return self.snapshot()

    def decide(self,proposal_hash,decision,now):
        pin(proposal_hash)
        if decision not in ('approve','reject'):fail('p63_decision_invalid')
        if not self._tick(now):return self.snapshot()
        if proposal_hash in self._decisions:
            if self._decisions[proposal_hash]!=decision:fail('p63_decision_conflict')
            return self.snapshot()
        s=self._state
        if s['status']!='waiting_approval' or s['proposal_hash']!=proposal_hash:fail('p63_decision_stale')
        self._decisions[proposal_hash]=decision
        if decision=='reject':s.update(status='cancelled',reason='rejected');return self.snapshot()
        if now+s['proposal']['max_duration_seconds']*1000>self._deadline:
            s.update(status='deadline_exceeded',reason='insufficient_time');return self.snapshot()
        s.update(status='running',iteration=s['iteration']+1,
            reserved_cost_microusd=s['proposal']['cost_ceiling_microusd'])
        self._approved_plans.add(s['proposal']['plan_id'])
        return self.snapshot()

    def finish(self,receipt,now):
        s=self._state
        try:
            closed(receipt,{'execution_id','iteration','proposal_hash','output','cost_microusd','dry_run','origin'})
            uuid(receipt['execution_id']);pin(receipt['proposal_hash'])
            integer(receipt['iteration'],1,20);integer(receipt['cost_microusd'],0,0)
            closed(receipt['output'],{'text'});text(receipt['output']['text'])
            if receipt['dry_run'] is not True or receipt['origin']!='fixture_echo':fail('p63_untrusted_receipt')
            if receipt['execution_id']!=self._envelope['execution_id']:fail('p63_receipt_scope')
            key=receipt['iteration'];signature=digest(receipt)
            if key in self._receipts:
                if self._receipts[key]!=signature:fail('p63_receipt_conflict')
                self._tick(now);return self.snapshot()
            if key!=s['iteration'] or receipt['proposal_hash']!=s['proposal_hash']:fail('p63_receipt_scope')
            if s['status']!='running':fail('p63_not_running')
        except (ValueError,TypeError):
            if s['status'] not in TERMINAL:s.update(status='manual_review',reason='unverified_receipt')
            raise ValueError('p63_unverified_receipt') from None
        if not self._tick(now):return self.snapshot()
        self._receipts[key]=signature
        checks=[{'field':c['field'],'rule':c['rule'],'passed':bool(receipt['output']['text'].strip())
            if c['rule']=='non_empty' else receipt['output']['text']==c['value']}
            for c in self._envelope['success_criteria']]
        s.update(cost_microusd=s['cost_microusd']+receipt['cost_microusd'],
            reserved_cost_microusd=0,receipt_hash=signature,checks=checks)
        if s['cancel_requested']:s.update(status='cancelled',reason='cancel_acknowledged')
        elif all(c['passed'] for c in checks):s.update(status='completed',reason='criteria_passed')
        elif s['iteration']>=self._envelope['policy']['max_iterations']:
            s.update(status='budget_exhausted',reason='iterations')
        else:s.update(status='waiting_replan',reason='criteria_unmet')
        return self.snapshot()

    def cancel(self,now):
        if not self._tick(now):return self.snapshot()
        self._state['cancel_requested']=True
        if self._state['status']!='running':self._state.update(status='cancelled',reason='requested')
        return self.snapshot()

    def uncertain(self,now):
        if self._tick(now):self._state.update(status='manual_review',reason='execution_unknown')
        return self.snapshot()

    def drained(self,proof,now):
        """Trusted adapter only: release a verified cancellation reservation.

        A digest or child transport status alone is not a drain proof; the
        versioned runner verifies immutable native/queue evidence beforehand.
        """
        closed(proof,{'execution_id','iteration','proposal_hash','drained'})
        s=self._state
        if (proof['execution_id']!=self._envelope['execution_id'] or
            proof['iteration']!=s['iteration'] or proof['proposal_hash']!=s['proposal_hash'] or
            proof['drained'] is not True):fail('p63_drain_scope')
        self._tick(now)
        if not s['cancel_requested'] and s['status'] not in ('deadline_exceeded','manual_review'):
            fail('p63_drain_not_stopped')
        s['reserved_cost_microusd']=0
        if s['cancel_requested']:s.update(status='cancelled',reason='cancel_acknowledged')
        return self.snapshot()
