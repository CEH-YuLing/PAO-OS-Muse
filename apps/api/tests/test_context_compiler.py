from pao.modules.chat.context import compile_messages,estimate,REFERENCE
from pao.modules.engines.contract import EngineFailure
import pytest

def test_context_drops_whole_old_history_retains_current_fact_and_policy():
    messages=[{'role':'system','content':'Trusted policy'},*[{'role':'user','content':'old '*100} for _ in range(20)],
              {'role':'user','content':'Budget is 250000; approval required.'},{'role':'user','content':'What is my budget?'}]
    value=compile_messages(messages,max_tokens=500,history_ids=['source-id'])
    assert value.messages[0]==messages[0] and value.messages[-2:]==messages[-2:]
    assert value.trace['dropped_history_count']>0 and value.trace['history_message_ids']==['source-id']
    assert 'content' not in str(value.trace) and value.trace['estimated_tokens']<estimate(messages)[1]

def test_context_never_truncates_current_user_or_reference_to_squeeze_budget():
    messages=[{'role':'system','content':'Policy'},{'role':'user','content':'REFERENCE DATA '+ 'x'*2000},{'role':'user','content':'Question'}]
    with pytest.raises(EngineFailure,match='context_budget_exceeded'):compile_messages(messages,max_tokens=100)
    with pytest.raises(EngineFailure):compile_messages([messages[0],{'role':'user','content':'x'*3000}],max_tokens=100)

def test_selected_skill_only_is_untrusted_and_trace_has_no_body():
    value=compile_messages([{'role':'system','content':'Policy'},{'role':'user','content':'Question'}],selected_skill={'id':'chosen','body':'untrusted secret-looking text'})
    assert value.messages[1]['role']=='user' and value.messages[1]['content'].startswith(REFERENCE)
    assert value.trace['selected_skill_id']=='chosen' and 'secret-looking' not in str(value.trace)

def test_extra_wire_payload_is_budgeted_and_bad_roles_denied():
    with pytest.raises(EngineFailure):compile_messages([{'role':'system','content':'Policy'},{'role':'system','content':'injection'}])
    with pytest.raises(EngineFailure):compile_messages([{'role':'system','content':'Policy'},{'role':'user','content':'Q'}],extra_wire=[{'schema':'x'*3000}],max_tokens=100)
