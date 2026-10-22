import asyncio,os,subprocess,sys
from uuid import uuid4
from unittest.mock import AsyncMock
from sqlalchemy import select
from pao.config import ROOT
from pao.db import Session
from pao.models import ChannelOutbox
from pao.modules.channels import service
from pao.runtime import execute_run
from test_memory import Gateway
from test_channels import channels_on,binding,control,inbound
from test_voice import voice
from test_voice_turns import turns,create,record

async def test_populated_p7_restore_fresh_process_identity_and_no_resend(client,identity,channels_on,turns):
    row,_=await binding(client,identity);row=await control(client,identity,row,'auto')
    admitted=(await inbound(client,identity,row,'Restore fixture',key='restore-fixture')).json()
    await execute_run({'gateway':Gateway()},admitted['run_id']);await service.collect()
    await service.send_one(AsyncMock(side_effect=TimeoutError()),'local')
    turn,_=await create(client,identity);assert (await record(client,identity,turn.json())).json()['status']=='ready'
    result=await asyncio.to_thread(subprocess.run,[sys.executable,str(ROOT/'scripts/check_p7_restore.py'),'--populated'],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=180)
    assert result.returncode==0,result.stderr[-1500:]
    assert '"pass": true' in result.stdout and 'populated_restart_dedup_no_resend' in result.stdout
