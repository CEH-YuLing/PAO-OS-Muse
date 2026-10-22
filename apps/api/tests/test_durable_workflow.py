"""P6.2A pure admission contract; live registration intentionally absent."""
from copy import deepcopy
from uuid import uuid4
import pytest
from pao.modules.studio.durable_workflow import validate_command

def command():
    return {'format':'p62-dryrun-v1','plan_id':str(uuid4()),'snapshot_hash':'a'*64,'timeout_seconds':60,
            'steps':[{'step_id':'first','execution_id':str(uuid4()),'depends_on':[],
                      'approval_required':True,'delay_seconds':0},
                     {'step_id':'second','execution_id':str(uuid4()),'depends_on':['first'],
                      'approval_required':False,'delay_seconds':1}]}

def test_dryrun_valid_contract_does_not_mutate():
    value=command();original=deepcopy(value);validate_command(value);assert value==original

@pytest.mark.parametrize('field,bad',[('format','live'),('plan_id','wrong'),('snapshot_hash','z'*64),
    ('timeout_seconds',True),('timeout_seconds',0),('timeout_seconds',86401),('steps',[])])
def test_invalid_envelope(field,bad):
    value=command();value[field]=bad
    with pytest.raises((ValueError,TypeError,AttributeError)):validate_command(value)

@pytest.mark.parametrize('field,bad',[('depends_on',['second']),('depends_on',['first','first']),
    ('depends_on',[1]),('approval_required','true'),('delay_seconds',True),('delay_seconds',-1),
    ('delay_seconds',86401),('execution_id','wrong'),('step_id','')])
def test_invalid_step(field,bad):
    value=command();value['steps'][0][field]=bad
    with pytest.raises((ValueError,TypeError,AttributeError)):validate_command(value)

def test_duplicate_ids_and_arbitrary_activity_rejected():
    for field in ('step_id','execution_id'):
        value=command();value['steps'][1][field]=value['steps'][0][field]
        with pytest.raises(ValueError):validate_command(value)
    value=command();value['steps'][0]['activity']='execute_shell'
    with pytest.raises(ValueError):validate_command(value)
