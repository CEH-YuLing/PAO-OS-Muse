"""Actual refused TCP connections, not injected exception stubs.

Live PostgreSQL/Redis/Temporal containers are never stopped. These checks cover
client connection loss/recovery, not production service reboot durability.
"""
import asyncio
import socket
from uuid import uuid4
import pytest
from arq.connections import ArqRedis
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from sqlalchemy import select, func
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from temporalio.testing import WorkflowEnvironment
from pao.config import ROOT, settings
from pao.db import Session
from pao.models import TaskAttempt, StudioCommand
from pao.modules.studio import arq_bridge as bridge, durable
from test_durable_admission import plan, start, gates
from test_studio_step_jobs import ready


def closed_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


async def test_real_db_and_redis_connection_loss_keeps_pending(client,identity,gates,monkeypatch):
    value,ident=await ready(client,identity);args=(value['plan_id'],'first',ident)
    await bridge.jobs.reserve(*args)
    unreachable=make_url(settings().database_url).set(host='127.0.0.1',port=closed_port())
    failed=create_async_engine(unreachable,connect_args={'timeout':1})
    original=bridge.jobs.Session
    try:
        monkeypatch.setattr(bridge.jobs,'Session',async_sessionmaker(failed,expire_on_commit=False))
        with pytest.raises((OSError,asyncio.TimeoutError)):
            await bridge.execute_studio_echo({},*args)
    finally:
        monkeypatch.setattr(bridge.jobs,'Session',original);await failed.dispose()
    assert (await bridge.jobs.recover(*args))['status']=='pending'
    badredis=ArqRedis(host='127.0.0.1',port=closed_port(),db=15,socket_connect_timeout=.3)
    monkeypatch.setattr(settings(),'workflow_worker_enabled',True)
    try:
        with pytest.raises((RedisConnectionError,RedisTimeoutError)):
            await bridge.dispatch_studio({'redis':badredis})
    finally:await badredis.aclose()
    async with Session() as db:assert await db.scalar(select(func.count(TaskAttempt.id)))==0
    assert (await bridge.execute_studio_echo({},*args))['status']=='completed'
    async with Session() as db:assert await db.scalar(select(func.count(TaskAttempt.id)))==1


async def test_real_temporal_connection_loss_then_outbox_delivery(client,identity,gates,monkeypatch):
    value=await plan(client,identity);_,response=await start(client,identity,value)
    assert response.status_code==202
    monkeypatch.setattr(durable.gateway,'deliver',durable.Gateway.deliver.__get__(durable.gateway))
    monkeypatch.setattr(durable.gateway,'client',None)
    monkeypatch.setattr(settings(),'temporal_address','127.0.0.1:'+str(closed_port()))
    assert await asyncio.wait_for(durable.dispatch_commands(),5)==0
    async with Session() as db:
        command=await db.scalar(select(StudioCommand));assert command.status=='pending' and command.attempts==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
    directory=ROOT/'.runtime'/('p62-outage-'+uuid4().hex);directory.mkdir()
    from temporal_fixture import cached_binary, namespace_ready
    async with await WorkflowEnvironment.start_local(ui=False,dev_server_existing_path=cached_binary(ROOT),
            dev_server_database_filename=str(directory/'temporal.sqlite')) as env:
        await namespace_ready(env.client)
        monkeypatch.setattr(durable.gateway,'client',env.client)
        await asyncio.sleep(2.1) # real bounded delivery backoff
        assert await durable.dispatch_commands()==1
        async with Session() as db:
            command=await db.scalar(select(StudioCommand));assert command.status=='delivered' and command.attempts==2
            assert await db.scalar(select(func.count(TaskAttempt.id)))==0
