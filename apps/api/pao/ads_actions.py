"""Copilot-only Meta writes with snapshots, resource locks and immutable audit events."""
import asyncio
import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .db import Session
from .integrations.meta.client import MetaClient, MetaError, decrypt
from .integrations.meta.sync import permitted
from .models import (AdAction, AdActionAudit, AdEntity, AdRecommendation, Member,
                     MetaConnection, User, now)
from .ads_policy import assess, snapshot as policy_snapshot
from .modules.events.producer import requested as record_approval_requested
from .modules.events.guards import execution_hash
from .modules.events.approvals import require_snapshot
from .auth import Principal
from .modules.connections import read_authority
from .integrations import ads_apps
from .integrations.meta.client import MetaClient as _NativeMetaClient

TERMINAL={'simulated','succeeded','failed','unknown','stale','cancelled'}


def audit(db,action,actor,event,**data):
    db.add(AdActionAudit(workspace_id=action.workspace_id,action_id=action.id,actor_id=actor,
        event=event,action_version=action.version,data=data))


def payload_hash(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def clean_state(state):
    return {key:state[key] for key in ('id','account_id','campaign_id','adset_id','name','status','effective_status','daily_budget','lifetime_budget','updated_time') if key in state}


def proposed(body,before):
    if body.action_type in ('pause','resume'):
        desired='PAUSED' if body.action_type=='pause' else 'ACTIVE'
        current=str(before.get('status') or '').upper()
        if current==desired:raise ValueError('action_no_change')
        return {'status':desired},{'action_type':'resume' if desired=='PAUSED' else 'pause','state':{'status':current}}
    if body.resource_type=='ad':raise ValueError('budget_resource_invalid')
    current=before.get('daily_budget')
    if not isinstance(current,str) or not current.isdecimal() or int(current)<=0:raise ValueError('daily_budget_unavailable')
    old=int(current);new=body.budget_minor_units
    if new==old:raise ValueError('action_no_change')
    change=abs(Decimal(new-old)/Decimal(old)*100)
    if change>settings().meta_write_max_budget_change_pct:raise ValueError('budget_change_limit_exceeded')
    return {'daily_budget':new},{'action_type':'update_budget','state':{'daily_budget':old}}


async def create_action(db,conn,user_id,body,client_factory=None):
    client_factory=client_factory or MetaClient
    serialized=body.model_dump(mode='json',exclude={'workspace_id','request_key'})
    digest=payload_hash(serialized)
    old=await db.scalar(select(AdAction).where(AdAction.connection_id==conn.id,AdAction.request_key==str(body.request_key)))
    if old:
        if old.payload_hash!=digest:raise HTTPException(409,'request_key đã dùng cho action khác')
        return old
    if not body.dry_run and not settings().meta_write_enabled:raise HTTPException(503,'Meta live write đang tắt')
    if not body.dry_run and 'ads_management' not in conn.scopes:raise HTTPException(409,'Kết nối Meta chưa có quyền ads_management; hãy kết nối lại')
    if not await permitted(db,conn,conn.version):raise HTTPException(409,'Kết nối Meta hết hạn hoặc bị thu hồi')
    entity=await db.scalar(select(AdEntity.id).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,
        AdEntity.account_id==body.account_id,AdEntity.kind==body.resource_type,AdEntity.remote_id==body.resource_id))
    if not entity:raise HTTPException(409,'Resource chưa có trong warehouse hiện tại; hãy đồng bộ lại trước')
    recommendation=None
    if body.recommendation_id:
        recommendation=await db.get(AdRecommendation,str(body.recommendation_id))
        if not recommendation or recommendation.connection_id!=conn.id or recommendation.connection_version!=conn.version or recommendation.account_id!=body.account_id:
            raise HTTPException(404,'Không tìm thấy recommendation')
        if recommendation.resource_id!=body.resource_id:raise HTTPException(422,'Recommendation không thuộc resource này')
    try:
        app_context=await ads_apps.bound(db,conn,'meta')
        # create_action already holds source/workspace locks in its caller;
        # avoid a second DB transaction self-deadlocking against those locks.
        client=client_factory(decrypt(conn.token_ciphertext),config=app_context.config) if client_factory is _NativeMetaClient else client_factory(decrypt(conn.token_ciphertext))
        before=clean_state(await client.resource(body.resource_type,body.resource_id,body.account_id))
        desired,compensation=proposed(body,before)
    except ValueError as exc:raise HTTPException(422,str(exc)) from None
    except MetaError as exc:raise HTTPException(409,str(exc)) from None
    action=AdAction(connection_id=conn.id,connection_version=conn.version,workspace_id=conn.workspace_id,user_id=user_id,
        recommendation_id=str(body.recommendation_id) if body.recommendation_id else None,platform='meta',account_id=body.account_id,
        resource_type=body.resource_type,resource_id=body.resource_id,action_type=body.action_type,
        request_key=str(body.request_key),payload_hash=digest,before_state=before,proposed_state=desired,after_state={},
        compensating_action=compensation,reason=body.reason,confidence=body.confidence,source_agent=body.source_agent,
        approval_status='pending',execution_status='pending',dry_run=body.dry_run,version=1,
        approval_expires_at=now()+timedelta(hours=settings().ads_approval_ttl_hours),decision_channel=None,
        result_24h={},result_72h={},result_7d={})
    db.add(action);await db.flush();audit(db,action,user_id,'action.proposed',dry_run=body.dry_run,
        before_state=before,proposed_state=desired,recommendation_id=action.recommendation_id)
    if action.source_agent=='performance_analyst':
        policy,reasons=await assess(db,action,recommendation)
        if policy and not reasons:
            action.approval_status='approved';action.execution_status='queued';action.decision_channel='autopilot'
            action.approved_by=user_id;action.approved_at=now();action.policy_id=policy.id;action.policy_version=policy.version
            action.policy_snapshot=policy_snapshot(policy);action.version+=1;action.updated_at=now()
            audit(db,action,user_id,'autopilot.approved',policy_id=policy.id,policy_version=policy.version,
                policy_snapshot=action.policy_snapshot)
        else:
            audit(db,action,user_id,'autopilot.deferred',reasons=reasons)
    if action.approval_status=='pending':
        await record_approval_requested(db,action,Principal(user_id,0),'ads')
    elif action.approval_status=='approved':
        action.approval_input_hash=execution_hash('ads',action)
    return action


async def decide_action(action_id,user_id,decision,version,channel,reason=None,expected_hash=None):
    if decision not in ('approve','reject') or channel not in ('ui','telegram'):
        raise HTTPException(422,'Quyết định approval không hợp lệ')
    async with Session.begin() as db:
        action=await db.get(AdAction,action_id,with_for_update=True)
        if not action:raise HTTPException(404,'Không tìm thấy approval')
        member=await db.get(Member,(action.workspace_id,user_id));user=await db.get(User,user_id)
        if not member or member.role not in ('owner','admin') or not user or not user.active:
            raise HTTPException(404,'Không tìm thấy approval')
        await require_snapshot(db,'ads',action,expected_hash)
        if action.approval_status=='approved' and decision=='approve':return action
        if action.approval_status=='rejected' and decision=='reject':return action
        if action.approval_status!='pending' or action.execution_status!='pending' or action.version!=version:
            raise HTTPException(409,'Approval đã thay đổi; tải lại trước khi quyết định')
        if action.approval_expires_at<=now():
            action.approval_status='expired';action.execution_status='cancelled';action.error_code='approval_expired'
            action.version+=1;action.updated_at=now();audit(db,action,user_id,'approval.expired',channel=channel)
            return action
        if decision=='approve':
            conn=await db.get(MetaConnection,action.connection_id)
            if not conn or not await permitted(db,conn,action.connection_version):
                raise HTTPException(409,'Kết nối Meta không còn hợp lệ')
            if not action.dry_run and (not settings().meta_write_enabled or 'ads_management' not in conn.scopes):
                raise HTTPException(409,'Meta live write hoặc quyền ads_management không còn hợp lệ')
        action.approval_status='approved' if decision=='approve' else 'rejected'
        action.execution_status='queued' if decision=='approve' else 'cancelled'
        action.approved_by=user_id if decision=='approve' else None
        action.approval_input_hash=execution_hash('ads',action) if decision=='approve' else None
        action.approved_at=now();action.decision_channel=channel
        action.error_code=None if decision=='approve' else 'approval_rejected'
        action.version+=1;action.updated_at=now()
        audit(db,action,user_id,'approval.'+decision,channel=channel,reason=reason,decided_version=version)
        return action


def guard_matches(action,current):
    if current.get('id')!=action.before_state.get('id') or current.get('account_id')!=action.before_state.get('account_id'):return False
    field='daily_budget' if action.action_type=='update_budget' else 'status'
    return str(current.get(field))==str(action.before_state.get(field))


def result_matches(action,current):
    return all(str(current.get(key))==str(value) for key,value in action.proposed_state.items())


async def execute_action(ctx,action_id,client_factory=None):
    client_factory=client_factory or ctx.get('meta_client_factory') or MetaClient
    redis=ctx['redis'];resource_lock=None;token=secrets.token_urlsafe(24)
    async with Session.begin() as db:
        action=await db.get(AdAction,action_id,with_for_update=True)
        if not action or action.approval_status!='approved' or action.execution_status!='queued' or not action.approved_by:return
        user_id=action.approved_by
        member=await db.get(Member,(action.workspace_id,user_id));user=await db.get(User,user_id)
        if not member or member.role not in ('owner','admin') or not user or not user.active:
            action.execution_status='cancelled';action.error_code='approver_access_revoked';action.version+=1;action.updated_at=now()
            audit(db,action,user_id,'action.cancelled',reason=action.error_code);return
        if action.execution_status in TERMINAL:return action
        resource_lock=f'pao:ads-resource:{action.connection_id}:{action.resource_type}:{action.resource_id}'
    if not await redis.set(resource_lock,token,ex=90,nx=True):return
    try:
        async with Session.begin() as db:
            await read_authority.lock_scope(db,action.workspace_id)
            await db.get(MetaConnection,action.connection_id,with_for_update={'read':True})
            action=await db.get(AdAction,action_id,with_for_update=True)
            if not action or action.approval_status!='approved' or action.execution_status!='queued':return
            member=await db.get(Member,(action.workspace_id,user_id));user=await db.get(User,user_id)
            denied = not member or member.role not in ('owner','admin') or not user or not user.active
            changed = action.approval_input_hash and action.approval_input_hash != execution_hash('ads',action)
            expired = action.approval_expires_at <= now()
            if denied or changed or expired:
                action.execution_status='cancelled'
                action.error_code='approver_access_revoked' if denied else 'approval_input_changed' if changed else 'approval_expired'
                action.version+=1;action.updated_at=now();audit(db,action,user_id,'action.cancelled',reason=action.error_code)
                return action
            if action.decision_channel=='autopilot':
                policy,reasons=await assess(db,action)
                if not policy or reasons or policy.id!=action.policy_id or policy.version!=action.policy_version:
                    action.approval_status='pending';action.execution_status='pending';action.decision_channel=None
                    action.approved_by=None;action.approved_at=None;action.error_code='autopilot_policy_blocked'
                    action.version+=1;action.updated_at=now();audit(db,action,user_id,'autopilot.deferred',reasons=reasons)
                    await record_approval_requested(db,action,Principal(user_id,0),'ads')
                    return action
            claimed_from=action.version
            conn=await db.get(MetaConnection,action.connection_id)
            if not conn or not await permitted(db,conn,action.connection_version):
                action.execution_status='cancelled';action.error_code='meta_connection_invalid';action.version+=1;action.updated_at=now()
                audit(db,action,user_id,'action.cancelled',reason=action.error_code);return
            if not action.dry_run and (not settings().meta_write_enabled or 'ads_management' not in conn.scopes):
                action.execution_status='cancelled';action.error_code='meta_write_permission_invalid';action.version+=1;action.updated_at=now()
                audit(db,action,user_id,'action.cancelled',reason=action.error_code);return
            action.execution_status='executing';action.version+=1;action.updated_at=now();claimed=action.version
            audit(db,action,user_id,'action.started',dry_run=action.dry_run,queued_version=claimed_from)
            app_context=await ads_apps.bound(db,conn,'meta')
            request_guard=ads_apps.invocation(conn,'meta',binding=app_context.binding)
            credential=conn.token_ciphertext;resource_type=action.resource_type;resource_id=action.resource_id;account_id=action.account_id
            desired=action.proposed_state;dry_run=action.dry_run
        status='failed';error=None;after={};write_attempted=False
        try:
            client=client_factory(decrypt(credential),config=app_context.config,guard=request_guard) if client_factory is _NativeMetaClient else client_factory(decrypt(credential))
            current=clean_state(await client.resource(resource_type,resource_id,account_id))
            async with Session() as db:
                stored=await db.get(AdAction,action_id)
                member=await db.get(Member,(stored.workspace_id,user_id));user=await db.get(User,user_id)
                conn=await db.get(MetaConnection,stored.connection_id)
                invalid=not member or member.role not in ('owner','admin') or not user or not user.active
                invalid=invalid or stored.execution_status!='executing' or stored.version!=claimed or stored.approval_expires_at<=now()
                invalid=invalid or (stored.approval_input_hash and stored.approval_input_hash!=execution_hash('ads',stored))
                invalid=invalid or not conn or not await permitted(db,conn,stored.connection_version)
                if not dry_run: invalid=invalid or not settings().meta_write_enabled or 'ads_management' not in conn.scopes
                if stored.decision_channel=='autopilot':
                    policy,reasons=await assess(db,stored)
                    invalid=invalid or not policy or bool(reasons) or policy.id!=stored.policy_id or policy.version!=stored.policy_version
            if invalid:status='cancelled';error='permission_or_input_changed'
            elif not guard_matches(stored,current):status='stale';error='meta_state_changed'
            elif dry_run:status='simulated';after={**current,**desired,'simulated':True}
            else:
                write_attempted=True;await client.write_resource(resource_id,desired)
                after=clean_state(await client.resource(resource_type,resource_id,account_id))
                if not result_matches(stored,after):status='unknown';error='meta_write_not_observed'
                else:status='succeeded'
        except MetaError as exc:
            error=str(exc)
            known_rejection=error in ('meta_request_rejected','meta_permission_denied','meta_rate_limited','meta_write_rejected','meta_write_payload_invalid')
            status='failed' if known_rejection else 'unknown' if write_attempted or error=='meta_write_unknown' else 'failed'
        except (asyncio.CancelledError,Exception):
            error='meta_write_interrupted';status='unknown' if write_attempted else 'failed'
        async with Session.begin() as db:
            action=await db.get(AdAction,action_id,with_for_update=True)
            if action.execution_status!='executing' or action.version!=claimed:return action
            action.execution_status=status;action.after_state=after;action.error_code=error;action.executed_at=now()
            action.version+=1;action.updated_at=now();audit(db,action,user_id,'action.'+status,error_code=error,after_state=after)
            return action
    finally:
        try:await redis.eval("if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",1,resource_lock,token)
        except Exception:pass


async def dispatch_actions(ctx):
    async with Session.begin() as db:
        expired=list(await db.scalars(select(AdAction).where(AdAction.approval_status=='pending',
            AdAction.approval_expires_at<=now()).with_for_update(skip_locked=True).limit(100)))
        for action in expired:
            action.approval_status='expired';action.execution_status='cancelled';action.error_code='approval_expired'
            action.version+=1;action.updated_at=now();audit(db,action,action.user_id,'approval.expired',channel='system')
        rows=list(await db.scalars(select(AdAction).where(AdAction.execution_status=='executing',
            AdAction.updated_at<now()-timedelta(seconds=120)).with_for_update(skip_locked=True).limit(50)))
        for action in rows:
            action.execution_status='unknown';action.error_code='execution_worker_lost';action.version+=1;action.updated_at=now()
            audit(db,action,action.user_id,'action.unknown',reason=action.error_code)
        queued=list(await db.scalars(select(AdAction.id).where(AdAction.approval_status=='approved',
            AdAction.execution_status=='queued').order_by(AdAction.approved_at,AdAction.id).limit(50)))
    for action_id in queued:
        await ctx['redis'].enqueue_job('execute_action',action_id,_job_id=f'ads-action:{action_id}',_expires=3600)


recover_actions=dispatch_actions
