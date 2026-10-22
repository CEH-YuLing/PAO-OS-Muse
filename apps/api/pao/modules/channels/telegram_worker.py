"""Dedicated bounded polling worker. No public route, host token or startup I/O.

Redis tickets/cursors are scheduling metadata, never authorization. PostgreSQL
bot lease and current profile/identity/actor/Brain checks remain authoritative.
Webhook ingress and report routing are separate S3.2C gates, not enabled here.
"""
import asyncio,math,sys
from dataclasses import asdict
from uuid import uuid4,UUID
from arq.connections import RedisSettings
from sqlalchemy import select,text
from pao.config import settings
from pao.db import Session
from pao.models import TelegramConnection,TelegramBotIdentity,TelegramRuntimeProfile,ChannelOutbox,Member,User,now
from pao.skills import execution_binding,require_execution_binding
from . import telegram_runtime as rt,telegram_store as store,telegram_polling as polling,telegram_scoped as scoped,telegram_sender as sender

PREFIX='pao:telegram:scoped:'
QUEUE=PREFIX+'queue'
CAPACITY=8
TICKET_SECONDS=900
TURN_SECONDS=80
RELEASE="if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"


def _text(value):return value.decode() if isinstance(value,bytes) else value


def _cursor(value):
    try:
        value=_text(value)
        return value if type(value) is str and len(value)==36 and str(UUID(value))==value else None
    except Exception:return None


def _gate():
    rt._enabled()
    if not settings().channels_enabled:raise rt.TelegramRuntimeError('telegram_worker_channels_disabled')


def _ticket(wid):return PREFIX+'ticket:'+wid
def _backoff(pin,generation):return PREFIX+'backoff:'+pin.connection_id+':'+str(generation)


async def _release(redis,wid,ticket):
    await redis.eval(RELEASE,1,_ticket(wid),ticket)


def _eligible():
    return (select(TelegramConnection,TelegramBotIdentity.bot_user_id,TelegramRuntimeProfile.generation)
        .join(TelegramBotIdentity,TelegramBotIdentity.connection_id==TelegramConnection.id)
        .join(TelegramRuntimeProfile,TelegramRuntimeProfile.connection_id==TelegramConnection.id)
        .join(Member,(Member.workspace_id==TelegramConnection.workspace_id)&(Member.user_id==TelegramConnection.owner_id))
        .join(User,User.id==TelegramConnection.owner_id)
        .where(TelegramConnection.status=='staged',TelegramRuntimeProfile.status=='enabled',
            TelegramRuntimeProfile.connection_version==TelegramConnection.version,
            TelegramBotIdentity.connection_version==TelegramConnection.version,
            Member.role.in_(('owner','admin')),User.active.is_(True)))


async def _cycle(db,query,column,cursor,limit):
    rows=list(await db.execute(query.where(column>cursor).order_by(column).limit(limit))) if cursor else list(
        await db.execute(query.order_by(column).limit(limit)))
    if cursor and len(rows)<limit:
        rows+=list(await db.execute(query.where(column<=cursor).order_by(column).limit(limit-len(rows))))
    return rows


async def dispatch(ctx):
    """At most eight SME visits, one pending/running ticket per SME, queue<=8.

    Cross-process dispatcher lock is transaction-scoped and held <=5s. No bot
    credential or permanent DB connection per SME. Cursors expire after a day.
    Queued jobs carry immutable generation/source pins, no text or credentials.
    """
    if not settings().telegram_scoped_runtime_enabled or settings().telegram_enabled or not settings().channels_enabled:
        return {'enqueued':0}
    redis=ctx['redis'];published=0
    try:
        async with asyncio.timeout(5),Session.begin() as db:
            if not await db.scalar(text("SELECT pg_try_advisory_xact_lock(hashtextextended('pao-telegram-dispatch-v1',0))")):
                return {'enqueued':0}
            base=_eligible()
            spaces=base.with_only_columns(TelegramConnection.workspace_id).distinct()
            rows=await _cycle(db,spaces,TelegramConnection.workspace_id,_cursor(await redis.get(PREFIX+'cursor:workspace')),CAPACITY)
            for (wid,) in rows:
                _gate()
                if await redis.zcard(QUEUE)>=CAPACITY:break
                await redis.set(PREFIX+'cursor:workspace',wid,ex=86400)
                if await redis.exists(_ticket(wid)):continue
                cursor_key=PREFIX+'cursor:connection:'+wid
                bots=await _cycle(db,base.where(TelegramConnection.workspace_id==wid),TelegramConnection.id,
                    _cursor(await redis.get(cursor_key)),CAPACITY)
                for connection,bot,generation in bots:
                    await redis.set(cursor_key,connection.id,ex=86400)
                    pin=rt.RuntimePin(wid,connection.id,connection.owner_id,connection.version,bot)
                    if await redis.exists(_backoff(pin,generation)):continue
                    ticket=PREFIX+'turn:'+str(uuid4())
                    if not await redis.set(_ticket(wid),ticket,nx=True,ex=TICKET_SECONDS):break
                    try:
                        job=await redis.enqueue_job('telegram_turn',asdict(pin),generation,execution_binding(),
                            _job_id=ticket,_queue_name=QUEUE,_expires=900)
                    except BaseException:
                        # Publication may have succeeded without its ACK. Keep
                        # ticket: deleting it could admit a second owner early.
                        raise
                    if job is None:await _release(redis,wid,ticket)
                    else:published+=1
                    break
        return {'enqueued':published}
    except asyncio.CancelledError:raise
    except Exception:return {'enqueued':published,'code':'telegram_worker_dispatch_unavailable'}


async def telegram_turn(ctx,payload,generation,binding):
    """One queued epoch, one PG slot, <=80s; no ARQ auto retry or parallel LLM.

    Ticket is rechecked at admission and HTTP boundaries. An admitted HTTP call
    cannot be recalled; loss after claim retains sending/unknown, never resend.
    Test-only transport factory comes from trusted Worker.ctx, never job args.
    """
    redis=ctx['redis'];pin=None;ticket=ctx.get('job_id')
    try:
        if type(payload) is not dict:raise ValueError()
        pin=rt.RuntimePin(**payload);store._integer(generation,1)
        if type(ticket) is not str or not ticket.startswith(PREFIX+'turn:') or not _cursor(ticket.removeprefix(PREFIX+'turn:')):
            raise ValueError()
        _gate();require_execution_binding(binding)
        async def checkpoint():
            _gate()
            if _text(await redis.get(_ticket(pin.workspace_id)))!=ticket:
                raise rt.TelegramRuntimeError('telegram_worker_ticket_stale')
        await checkpoint()
        async with asyncio.timeout(TURN_SECONDS),rt.own_bot(pin) as lease:
            factory=ctx.get('telegram_transport_factory')
            http=factory(pin) if factory else None
            async with store._transaction(lease) as db:
                profile=await store._profile(db,pin,generation)
                mode,offset=profile.transport_mode,profile.next_offset
            result=(await polling._poll_owned(lease,redis,expected_generation=generation,transport=http,checkpoint=checkpoint)
                if mode=='polling' else polling.PollResult(0,offset))
            await checkpoint()
            collected=await scoped.collect_results(lease,generation=generation)
            await checkpoint()
            async with store._transaction(lease) as db:
                await store._profile(db,pin,generation)
                ident=await db.scalar(select(ChannelOutbox.id).where(ChannelOutbox.connection_id==pin.connection_id,
                    ChannelOutbox.workspace_id==pin.workspace_id,ChannelOutbox.status=='queued',ChannelOutbox.available_at<=now())
                    .order_by(ChannelOutbox.created_at,ChannelOutbox.id).limit(1))
            delivery='noop'
            if ident:
                delivery=(await sender._send_owned(lease,ident,expected_generation=generation,
                    transport=factory(pin) if factory else None,checkpoint=checkpoint)).disposition
            async with store._transaction(lease) as db:
                profile=await store._profile(db,pin,generation)
                delay=max(0,math.ceil((profile.cooldown_until-now()).total_seconds())) if profile.cooldown_until else 0
            await checkpoint()
            if delay:await redis.set(_backoff(pin,generation),'1',ex=min(delay,3600))
            return {'status':'completed','processed':result.processed,'collected':collected,'delivery':delivery}
    except asyncio.CancelledError:raise
    except Exception:
        # Stable result only. Never log exception/SQL/job args/provider bodies.
        if pin:
            try:
                if _text(await redis.get(_ticket(pin.workspace_id)))==ticket:
                    await redis.set(_backoff(pin,generation),'1',ex=5)
            except Exception:pass
        return {'status':'deferred','code':'telegram_worker_turn_unavailable'}
    finally:
        if pin and type(ticket) is str:
            try:await _release(redis,pin.workspace_id,ticket)
            except Exception:pass  # Keep reservation until TTL on uncertain Redis.


async def _dispatch_loop(ctx):
    # Do not enqueue cron wakeups behind long-running I/O turns. One small
    # background scanner has its own bounded transaction, not a DB slot per bot.
    while True:
        await asyncio.sleep(5)
        ctx['telegram_last_dispatch']=await dispatch(ctx)


async def startup(ctx):
    task=ctx.get('telegram_dispatch_task')
    if task and not task.done():return
    if not settings().telegram_scoped_runtime_enabled or settings().telegram_enabled or not settings().channels_enabled:return
    ctx['telegram_last_dispatch']=await dispatch(ctx)
    ctx['telegram_dispatch_task']=asyncio.create_task(_dispatch_loop(ctx))


async def shutdown(ctx):
    task=ctx.pop('telegram_dispatch_task',None)
    if task:
        task.cancel();await asyncio.gather(task,return_exceptions=True)


class WorkerSettings:
    """Separate process/queue: never consumes chat, tools or campaign jobs."""
    functions=[telegram_turn]
    queue_name=QUEUE
    redis_settings=RedisSettings.from_dsn(settings().redis_url)
    max_jobs=1
    max_tries=1
    retry_jobs=False
    job_timeout=90
    keep_result=0
    handle_signals=sys.platform!='win32'
    health_check_key=PREFIX+'health'
    health_check_interval=15
    on_startup=startup
    on_shutdown=shutdown
    cron_jobs=[]
