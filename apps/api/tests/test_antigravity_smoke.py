import asyncio
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from pao.modules.cli_connections import antigravity_smoke as smoke


def initial(**patch):
    return {'event':'init','conversation_id':'11111111-1111-4111-8111-111111111111',
            'init':{'tools':[],'model':smoke.MODEL,'agent':smoke.AGENT,
                    'permission_mode':'request-review',**patch}}


@pytest.mark.parametrize('patch,code',[
    ({'tools':['run_command']},'tools_not_disabled'),
    ({'tools':['ask_permission']},'tools_not_disabled'),
    ({'tools':None},'tools_not_disabled'),
    ({'model':'other'},'configuration_mismatch'),
    ({'agent':'other'},'configuration_mismatch'),
    ({'permission_mode':'always-proceed'},'configuration_mismatch')])
def test_gate_denies_tools_and_mismatches(patch,code):
    with pytest.raises(smoke.SmokeFailure,match=code):smoke.init_gate(initial(**patch))


@pytest.mark.parametrize('raw',[b'{"event":"init","event":"result"}',b'{"x":NaN}',b'[]',b'\xff',b''])
def test_strict_json(raw):
    with pytest.raises(smoke.SmokeFailure):smoke.decode(raw)


def stream(*values):
    reader=asyncio.StreamReader()
    reader.feed_data(b''.join(json.dumps(v).encode()+b'\n' for v in values));reader.feed_eof()
    return reader


@pytest_asyncio.fixture
async def process(tmp_path,monkeypatch):
    monkeypatch.setattr(smoke,'ROOT',tmp_path)
    (tmp_path/'.runtime').mkdir()
    binary=tmp_path/'fake';binary.write_bytes(b'never executed')
    stdin=SimpleNamespace(writes=[],closed=False)
    stdin.write=lambda value:stdin.writes.append(value)
    async def drain():pass
    stdin.drain=drain
    stdin.close=lambda:setattr(stdin,'closed',True)
    p=SimpleNamespace(stdin=stdin,stdout=None,stderr=stream(),returncode=None,killed=False)
    async def wait():p.returncode=0;return 0
    p.wait=wait
    p.kill=lambda:setattr(p,'killed',True)
    async def launch(*args,**kw):
        assert '--dangerously-skip-permissions' not in args and '-p' not in args
        assert kw['env'].get('OPENAI_API_KEY') is None
        return p
    monkeypatch.setattr(smoke.asyncio,'create_subprocess_exec',launch)
    monkeypatch.setattr(smoke.subprocess,'CREATE_NO_WINDOW',0,raising=False)
    return p,{'binary':str(binary),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}


async def test_live_gate_never_writes_prompt_when_tools_are_available(process):
    p,cfg=process;p.stdout=stream(initial(tools=['run_command','write_to_file']))
    async def check():raise AssertionError('must gate before dispatch')
    with pytest.raises(smoke.SmokeFailure,match='tools_not_disabled'):await smoke.native_smoke(cfg,check)
    assert not p.stdin.writes and p.killed


async def test_authority_recheck_prevents_prompt(process):
    p,cfg=process;p.stdout=stream(initial())
    async def revoked():raise PermissionError('revoked')
    with pytest.raises(PermissionError):await smoke.native_smoke(cfg,revoked)
    assert not p.stdin.writes and p.killed


async def test_one_fixed_prompt_only_after_safe_init_and_two_authority_checks(process):
    p,cfg=process
    p.stdout=stream(initial(),{'event':'result','result':{
        'conversation_id':initial()['conversation_id'],'status':'SUCCESS','num_turns':1,
        'response':smoke.ANSWER,'usage':{'input_tokens':10,'output_tokens':5,'total_tokens':15}}})
    checks=[]
    async def check():checks.append(True)
    value=await smoke.native_smoke(cfg,check)
    assert value['response']==smoke.ANSWER and value['inference_verified']
    assert len(p.stdin.writes)==1 and len(checks)==2 and p.stdin.closed
    assert json.loads(p.stdin.writes[0])['message']['content']==smoke.PROMPT


async def test_late_tool_never_becomes_success(process):
    p,cfg=process
    p.stdout=stream(initial(),{'event':'step_update','step_update':{
        'conversation_id':initial()['conversation_id'],'step_type':'tool','tool_name':'run_command'}})
    async def check():pass
    with pytest.raises(smoke.SmokeFailure,match='unexpected_tool'):await smoke.native_smoke(cfg,check)
    assert len(p.stdin.writes)==1 and p.killed
