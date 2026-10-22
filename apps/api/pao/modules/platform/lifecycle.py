"""Tenant account/data lifecycle. No mail, remote actions or deletion executor."""
import asyncio
import hashlib
import json
import secrets
import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, delete, update, func, text, or_
from sqlalchemy.exc import IntegrityError

from ...access import membership
from ...auth import Principal, bearer, principal, passwords, rate_limit
from ...config import settings
from ...db import database
from ...models import (Base, User, Workspace, Member, Brain, BrainMember, BrainFile,
    BrainNote, BrainNoteVersion, ChatSession, Run, TenantConnectionGrant, ChannelBinding, ChannelOutbox,
    TelegramPeer, TelegramPairing, WorkspaceInvitation, LoginSession,
    LifecycleAudit, DataLifecycleRequest, now)

router = APIRouter()
Role = Literal['admin', 'operator', 'analyst', 'viewer']
PREFIX = '/v1/workspaces/{workspace_id}/lifecycle'
MAX_EXPORT_BYTES = 2 * 1024 * 1024
MAX_EXPORT_ROWS = 2000


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Invite(Input):
    email: str = Field(min_length=3, max_length=254)
    role: Role = 'viewer'
    hours: int = Field(default=24, ge=1, le=168)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value = value.strip().lower()
        if value.count('@') != 1 or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in value) or not all(value.split('@')):
            raise ValueError('Email không hợp lệ')
        return value


class AcceptInvite(Invite):
    code: str = Field(min_length=40, max_length=100)
    password: str | None = Field(default=None, min_length=12, max_length=128, repr=False)


class RoleChange(Input):
    role: Role


class Confirmation(Input):
    confirm: Literal[True]


class Scope(Input):
    brain_ids: list[UUID] = Field(default_factory=list, max_length=20)
    include_business: bool = True


class ScopeConfirmation(Confirmation):
    preview_hash: str = Field(pattern='^[a-f0-9]{64}$')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), default=str).encode()).hexdigest()


def audit(db, who, action, subject, workspace=None, **details):
    db.add(LifecycleAudit(actor_id=who.id, action=action, subject_id=subject,
                          workspace_id=workspace, details=details))


async def owner(db, workspace_id, who, lock=False):
    workspace_id = str(workspace_id)
    workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id)
        .with_for_update() if lock else select(Workspace).where(Workspace.id == workspace_id))
    member = await membership(db, workspace_id, who)
    if member.role != 'owner':
        raise HTTPException(403, 'Chỉ chủ doanh nghiệp được quản lý mục này')
    if not workspace:
        raise HTTPException(404, 'Không tìm thấy doanh nghiệp')
    return workspace


def invitation_out(row):
    return {'id': row.id, 'email': row.email, 'role': row.role, 'status': row.status,
            'expires_at': row.expires_at, 'expired': row.expires_at <= now()}


@router.get(PREFIX+'/members')
async def members(workspace_id: UUID, offset: int = Query(0, ge=0, le=10000),
                  who: Principal = Depends(principal), db=Depends(database)):
    await owner(db, workspace_id, who)
    rows = (await db.execute(select(User.id, User.email, Member.role).join(Member)
        .where(Member.workspace_id == str(workspace_id)).order_by(User.email, User.id)
        .offset(offset).limit(101))).all()
    return {'members': [dict(row._mapping) for row in rows[:100]], 'has_more': len(rows)>100, 'offset': offset}


@router.get(PREFIX+'/invitations')
async def invitations(workspace_id: UUID, offset: int = Query(0, ge=0, le=10000),
                      who: Principal = Depends(principal), db=Depends(database)):
    await owner(db, workspace_id, who)
    rows = list(await db.scalars(select(WorkspaceInvitation).where(WorkspaceInvitation.workspace_id == str(workspace_id))
        .order_by(WorkspaceInvitation.created_at.desc(), WorkspaceInvitation.id).offset(offset).limit(101)))
    return {'invitations': [invitation_out(row) for row in rows[:100]], 'has_more': len(rows)>100}


@router.post(PREFIX+'/invitations', status_code=201)
async def create_invite(workspace_id: UUID, body: Invite, request: Request,
                        who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    await rate_limit(request.app.state.redis, 'invite-create', workspace.id+who.id, 20, 3600)
    pending = await db.scalar(select(func.count()).select_from(WorkspaceInvitation).where(
        WorkspaceInvitation.workspace_id == workspace.id, WorkspaceInvitation.status == 'pending', WorkspaceInvitation.expires_at > now()))
    if pending >= 50:
        raise HTTPException(409, 'Tối đa 50 lời mời còn hiệu lực; hãy thu hồi lời mời cũ')
    existing = await db.scalar(select(User.id).join(Member).where(Member.workspace_id == workspace.id, User.email == body.email))
    if existing:
        raise HTTPException(409, 'Người dùng đã là thành viên doanh nghiệp')
    code = secrets.token_urlsafe(32)
    row = WorkspaceInvitation(workspace_id=workspace.id, creator_id=who.id,
        email=body.email, role=body.role, code_hash=hashlib.sha256(code.encode()).hexdigest(),
        expires_at=now()+timedelta(hours=body.hours))
    db.add(row)
    await db.flush()
    audit(db, who, 'invitation.created', row.id, workspace.id, role=body.role)
    await db.commit()
    return {**invitation_out(row), 'code': code, 'delivery': 'manual_once_not_sent'}


@router.post(PREFIX+'/invitations/{invitation_id}/revoke')
async def revoke_invite(workspace_id: UUID, invitation_id: UUID, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    row = await db.get(WorkspaceInvitation, str(invitation_id), with_for_update=True)
    if not row or row.workspace_id != workspace.id:
        raise HTTPException(404, 'Không tìm thấy lời mời')
    if row.status == 'accepted':
        raise HTTPException(409, 'Lời mời đã nhận; dùng quản lý thành viên để thu hồi quyền')
    if row.status != 'revoked':
        row.status = 'revoked'
        audit(db, who, 'invitation.revoked', row.id, workspace.id)
    await db.commit()
    return invitation_out(row)


@router.post('/v1/auth/invitations/accept')
async def accept_invite(body: AcceptInvite, request: Request, credentials=Depends(bearer), db=Depends(database)):
    await rate_limit(request.app.state.redis, 'invite-accept-ip', request.client.host, 10, 60)
    code_hash = hashlib.sha256(body.code.encode()).hexdigest()
    row = await db.scalar(select(WorkspaceInvitation).where(WorkspaceInvitation.code_hash == code_hash))
    invalid = HTTPException(422, 'Không thể nhận lời mời; kiểm tra mã, email, thời hạn và tài khoản đăng nhập')
    if not row:
        raise invalid
    workspace = await db.scalar(select(Workspace).where(Workspace.id == row.workspace_id).with_for_update())
    row = await db.get(WorkspaceInvitation, row.id, with_for_update=True, populate_existing=True)
    inviter = await db.get(Member, (row.workspace_id, row.creator_id), populate_existing=True)
    creator = await db.get(User, row.creator_id, populate_existing=True)
    if (not workspace or not inviter or inviter.role != 'owner' or not creator or not creator.active
            or row.status != 'pending' or row.expires_at <= now() or row.email != body.email):
        raise invalid
    # Serializes accepting the same new email across different workspaces too.
    await db.execute(text('SELECT pg_advisory_xact_lock(:key)'),
                     {'key': int(hashlib.sha256(body.email.encode()).hexdigest()[:15],16)})
    user = await db.scalar(select(User).where(User.email == body.email).with_for_update())
    if user:
        if not credentials:
            raise invalid
        current = await principal(credentials, db)
        if current.id != user.id or not user.active:
            raise invalid
    else:
        if credentials or not body.password:
            raise invalid
        user = User(email=body.email, password_hash=await asyncio.to_thread(passwords.hash, body.password))
        db.add(user)
        await db.flush()
    if await db.get(Member, (workspace.id, user.id)):
        raise invalid
    db.add(Member(workspace_id=workspace.id, user_id=user.id, role=row.role))
    row.status = 'accepted'
    row.accepted_by = user.id
    workspace.lifecycle_version += 1
    audit(db, Principal(user.id, 0), 'invitation.accepted', row.id, workspace.id, role=row.role)
    await db.commit()
    return {'accepted': True, 'workspace_id': workspace.id, 'role': row.role, 'login_required': True}


async def revoke_member_grants(db, workspace_id, user_id):
    await db.execute(delete(BrainMember).where(BrainMember.workspace_id == workspace_id, BrainMember.user_id == user_id))
    await db.execute(update(TenantConnectionGrant).where(TenantConnectionGrant.workspace_id == workspace_id,
        or_(TenantConnectionGrant.grantee_id == user_id, TenantConnectionGrant.creator_id == user_id),
        TenantConnectionGrant.status != 'revoked').values(status='revoked', revision=TenantConnectionGrant.revision+1))
    await db.execute(update(TelegramPeer).where(TelegramPeer.workspace_id == workspace_id, TelegramPeer.user_id == user_id).values(enabled=False))
    await db.execute(update(TelegramPairing).where(TelegramPairing.workspace_id == workspace_id, TelegramPairing.user_id == user_id).values(status='revoked'))
    bindings = list(await db.scalars(select(ChannelBinding).where(ChannelBinding.workspace_id == workspace_id,
        ChannelBinding.actor_id == user_id).with_for_update()))
    for binding in bindings:
        binding.enabled = False
        binding.version += 1
        await db.execute(update(ChannelOutbox).where(ChannelOutbox.binding_id == binding.id,
            ChannelOutbox.status.in_(('queued','failed'))).values(status='cancelled'))
    sessions = select(ChatSession.id).where(ChatSession.workspace_id == workspace_id, ChatSession.user_id == user_id)
    await db.execute(update(Run).where(Run.session_id.in_(sessions), Run.status.in_(('queued','running'))).values(cancel_requested=True))
    await db.execute(update(WorkspaceInvitation).where(WorkspaceInvitation.workspace_id == workspace_id,
        WorkspaceInvitation.creator_id == user_id, WorkspaceInvitation.status == 'pending').values(status='revoked'))


async def target_member(db, workspace, user_id, who):
    row = await db.get(Member, (workspace.id, str(user_id)), with_for_update=True, populate_existing=True)
    if not row:
        raise HTTPException(404, 'Không tìm thấy thành viên')
    if row.role == 'owner' or row.user_id == who.id:
        raise HTTPException(409, 'Không sửa/xóa chủ doanh nghiệp tại đây; chuyển chủ là quy trình riêng')
    return row


@router.patch(PREFIX+'/members/{user_id}')
async def change_role(workspace_id: UUID, user_id: UUID, body: RoleChange, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    row = await target_member(db, workspace, user_id, who)
    if row.role != body.role:
        old = row.role
        await revoke_member_grants(db, workspace.id, row.user_id)
        row.role = body.role
        workspace.lifecycle_version += 1
        audit(db, who, 'member.role_changed', row.user_id, workspace.id, before=old, after=body.role)
    await db.commit()
    return {'user_id': str(user_id), 'role': row.role}


@router.post(PREFIX+'/members/{user_id}/remove')
async def remove_member(workspace_id: UUID, user_id: UUID, body: Confirmation, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    row = await target_member(db, workspace, user_id, who)
    await revoke_member_grants(db, workspace.id, row.user_id)
    audit(db, who, 'member.removed', row.user_id, workspace.id, role=row.role)
    await db.delete(row)
    workspace.lifecycle_version += 1
    await db.commit()
    return {'removed': True, 'other_enterprises_unchanged': True}


def session_out(row, who):
    return {'id': row.id, 'created_at': row.created_at, 'expires_at': row.expires_at,
            'current': row.token_hash == who.token_hash, 'revoked': row.revoked}


@router.get('/v1/auth/sessions')
async def login_sessions(who: Principal = Depends(principal), db=Depends(database)):
    rows = list(await db.scalars(select(LoginSession).where(LoginSession.user_id == who.id,
        LoginSession.auth_version == who.auth_version, LoginSession.expires_at > now())
        .order_by(LoginSession.created_at.desc()).limit(100)))
    return {'sessions': [session_out(row, who) for row in rows], 'legacy_current': not any(row.token_hash == who.token_hash for row in rows)}


@router.post('/v1/auth/sessions/revoke-current')
async def revoke_current(who: Principal = Depends(principal), db=Depends(database)):
    await db.scalar(select(User.id).where(User.id == who.id).with_for_update())
    row = await db.scalar(select(LoginSession).where(LoginSession.token_hash == who.token_hash).with_for_update())
    if not row:
        row = LoginSession(user_id=who.id, token_hash=who.token_hash, auth_version=who.auth_version,
                           expires_at=datetime.fromtimestamp(who.expires, timezone.utc))
        db.add(row)
        await db.flush()
    row.revoked = True
    audit(db, who, 'session.revoked', row.id)
    await db.commit()
    return {'revoked': True}


@router.post('/v1/auth/sessions/revoke-all')
async def revoke_all(body: Confirmation, who: Principal = Depends(principal), db=Depends(database)):
    user = await db.scalar(select(User).where(User.id == who.id).with_for_update().execution_options(populate_existing=True))
    user.auth_version += 1
    await db.execute(update(LoginSession).where(LoginSession.user_id == user.id).values(revoked=True))
    audit(db, who, 'session.all_revoked', user.id)
    await db.commit()
    return {'revoked': True, 'scope': 'account_all_enterprises'}


@router.post('/v1/auth/sessions/{session_id}/revoke')
async def revoke_one(session_id: UUID, who: Principal = Depends(principal), db=Depends(database)):
    row = await db.get(LoginSession, str(session_id), with_for_update=True)
    if not row or row.user_id != who.id:
        raise HTTPException(404, 'Không tìm thấy phiên đăng nhập')
    if not row.revoked:
        row.revoked = True
        audit(db, who, 'session.revoked', row.id)
    await db.commit()
    return {'revoked': True}


# Explicit catalog, never dump tables/credentials or arbitrary JSON wholesale.
BUSINESS_TABLES = ('brands','projects','goals','tasks','business_profiles',
    'business_profile_versions','monthly_plans','monthly_plan_versions',
    'business_jobs','business_budgets','business_actions','business_reports')
SAFE_COLUMNS = {'id','workspace_id','brand_id','name','title','description','status',
    'created_at','updated_at','due_at','revision','version','profile_id','plan_id',
    'profile_version_id','plan_version_id','job_id','budget_id','period','currency',
    'amount','reserved','spent','released','content_hash','kind','priority'}


def redact_content(value):
    if isinstance(value, dict):
        return {key: redact_content(item) for key, item in value.items()
                if not re.search(r'(?i)password|secret|token|credential|ciphertext|api.?key', key)}
    if isinstance(value, list):
        return [redact_content(item) for item in value]
    if isinstance(value, str):
        return re.sub(r'(?<![A-Za-z0-9])(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{30,}|\d{8,12}:[A-Za-z0-9_-]{30,})', '[Thông tin xác thực đã ẩn]', value)
    return value


async def snapshot(db, workspace, who, scope):
    result = {'version': 'pao-scoped-export-v1', 'workspace_id': workspace.id,
        'actor_id': who.id, 'lifecycle_version': workspace.lifecycle_version,
        'scope': scope.model_dump(mode='json'), 'collections': {},
        'exclusions': ['Thông tin xác thực, khóa và ciphertext kết nối',
            'Hội thoại và Brain riêng không được cấp quyền',
            'Audit bất biến, backup hạ tầng và dữ liệu doanh nghiệp khác',
            'JSON nội bộ/raw execution; bản xuất là danh mục được nêu rõ, không phải backup toàn hệ thống'],
        'deletion_execution': 'not_implemented_request_only'}
    total = 0
    for table_name in BUSINESS_TABLES if scope.include_business else ():
        table = Base.metadata.tables.get(table_name)
        if table is None or 'workspace_id' not in table.c:
            continue
        columns = [col for col in table.c if col.name in SAFE_COLUMNS or
                   (col.name == 'content' and table_name in ('business_profile_versions','monthly_plan_versions'))]
        query = select(*columns).where(table.c.workspace_id == workspace.id).order_by(table.c.id).limit(MAX_EXPORT_ROWS+1)
        bounded = query.subquery()
        byte_size = sum(func.coalesce(func.pg_column_size(bounded.c[col.name]), 0) for col in columns)
        count, size = (await db.execute(select(func.count(), func.coalesce(func.sum(byte_size),0)).select_from(bounded))).one()
        if total+count > MAX_EXPORT_ROWS or size > MAX_EXPORT_BYTES:
            raise HTTPException(413, 'Phạm vi vượt giới hạn; giảm nhóm dữ liệu trước khi xuất')
        rows = list((await db.execute(query)).mappings())
        total += len(rows)
        if total > MAX_EXPORT_ROWS:
            raise HTTPException(413, 'Phạm vi vượt 2.000 bản ghi; chọn ít nhóm hoặc Brain hơn')
        result['collections'][table_name] = [redact_content(dict(row)) for row in rows]
    from ..brains.access import require_brain
    for brain_id in sorted(set(map(str, scope.brain_ids))):
        brain = await require_brain(db, who, brain_id, allow_archived=True, lock=True)
        if brain.workspace_id != workspace.id:
            raise HTTPException(404, 'Không tìm thấy Brain trong doanh nghiệp')
        key = 'brain:'+brain.id
        count, size = (await db.execute(select(func.count(), func.coalesce(func.sum(BrainFile.size),0))
                                       .where(BrainFile.brain_id == brain.id))).one()
        if total+count > MAX_EXPORT_ROWS or size > MAX_EXPORT_BYTES:
            raise HTTPException(413, 'Nội dung Brain vượt giới hạn; dùng chức năng xuất Brain riêng')
        files = list(await db.scalars(select(BrainFile).where(BrainFile.brain_id == brain.id).order_by(BrainFile.id).limit(MAX_EXPORT_ROWS+1)))
        notes = list(await db.scalars(select(BrainNote).where(BrainNote.brain_id == brain.id).order_by(BrainNote.id).limit(MAX_EXPORT_ROWS+1)))
        total += len(files)+len(notes)+1
        if total > MAX_EXPORT_ROWS:
            raise HTTPException(413, 'Phạm vi vượt 2.000 bản ghi; chọn ít Brain hơn')
        if sum(f.size for f in files) > MAX_EXPORT_BYTES:
            raise HTTPException(413, 'Nội dung Brain vượt 2 MiB; dùng chức năng xuất Brain riêng')
        note_values = []
        for note in notes:
            version = await db.get(BrainNoteVersion, (note.id, note.content_version))
            note_values.append({'id': note.id, 'title': note.title, 'revision': note.revision,
                                'content': redact_content(version.content) if version else None})
        result['collections'][key] = {'id': brain.id, 'name': brain.name,
            'files': [{'id': f.id, 'name': f.name, 'sha256': f.sha256, 'revision': f.revision,
                       'size': f.size, 'content_base64': base64.b64encode(f.content).decode()} for f in files],
            'notes': note_values}
    raw = json.dumps(result, sort_keys=True, ensure_ascii=False, default=str).encode()
    if len(raw) > MAX_EXPORT_BYTES:
        raise HTTPException(413, 'Bản xuất vượt 2 MiB; giảm phạm vi')
    return result, raw


def data_out(row):
    return {'id': row.id, 'kind': row.kind, 'status': row.status, 'preview_hash': row.scope_hash,
            'summary': row.summary, 'expires_at': row.expires_at, 'created_at': row.created_at,
            'deletion_executed': False}


def cipher():
    try:
        return Fernet(settings().integration_encryption_key.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, 'Máy chủ chưa có khóa mã hóa cho bản xuất dữ liệu') from None


async def data_record(db, workspace, who, request_id, kind):
    row = await db.get(DataLifecycleRequest, str(request_id), with_for_update=True)
    if not row or row.workspace_id != workspace.id or row.actor_id != who.id or row.kind != kind:
        raise HTTPException(404, 'Không tìm thấy yêu cầu dữ liệu của bạn')
    if row.expires_at <= now():
        raise HTTPException(409, 'Yêu cầu đã hết hạn; tạo bản xem trước mới')
    return row


@router.post(PREFIX+'/data/exports', status_code=201)
async def create_export(workspace_id: UUID, body: Scope, request: Request, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    await rate_limit(request.app.state.redis, 'data-export', workspace.id+who.id, 5, 3600)
    value, raw = await snapshot(db, workspace, who, body)
    row = DataLifecycleRequest(workspace_id=workspace.id, actor_id=who.id, kind='export', status='ready',
        scope_hash=hashlib.sha256(raw).hexdigest(), summary={'scope': body.model_dump(mode='json'),
        'bytes': len(raw), 'collections': list(value['collections']), 'exclusions': value['exclusions']},
        payload=cipher().encrypt(raw), expires_at=now()+timedelta(minutes=15))
    db.add(row)
    await db.flush()
    audit(db, who, 'data.export_created', row.id, workspace.id, scope_hash=row.scope_hash)
    await db.commit()
    return data_out(row)


@router.get(PREFIX+'/data/exports/{request_id}/download')
async def download_export(workspace_id: UUID, request_id: UUID, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    row = await data_record(db, workspace, who, request_id, 'export')
    # Fresh authorization for each explicitly selected Brain, including after revoke.
    scope = Scope.model_validate(row.summary['scope'])
    from ..brains.access import require_brain
    for brain_id in scope.brain_ids:
        brain = await require_brain(db, who, str(brain_id), allow_archived=True)
        if brain.workspace_id != workspace.id:
            raise HTTPException(404, 'Không tìm thấy Brain')
    try:
        raw = cipher().decrypt(row.payload)
    except InvalidToken:
        raise HTTPException(409, 'Không đọc được bản xuất sau thay khóa; hãy tạo bản xuất mới') from None
    if hashlib.sha256(raw).hexdigest() != row.scope_hash:
        raise HTTPException(409, 'Bản xuất không còn toàn vẹn')
    audit(db, who, 'data.export_downloaded', row.id, workspace.id)
    await db.commit()
    return Response(raw, media_type='application/json', headers={
        'Cache-Control': 'no-store', 'Content-Disposition': f'attachment; filename="pao-export-{row.id}.json"'})


@router.post(PREFIX+'/data/deletions/preview', status_code=201)
async def deletion_preview(workspace_id: UUID, body: Scope, request: Request, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who, True)
    await rate_limit(request.app.state.redis, 'data-preview', workspace.id+who.id, 10, 3600)
    value, raw = await snapshot(db, workspace, who, body)
    row = DataLifecycleRequest(workspace_id=workspace.id, actor_id=who.id, kind='deletion', status='preview',
        scope_hash=hashlib.sha256(raw).hexdigest(), summary={'scope': body.model_dump(mode='json'),
        'collections': {key: len(val) if isinstance(val,list) else 1+len(val['files'])+len(val['notes']) for key,val in value['collections'].items()},
        'exclusions': value['exclusions'], 'warning': 'Chỉ tạo yêu cầu; không có job xóa tự động. Audit, backup, công việc đang chạy và hành động chưa rõ kết quả cần quản trị kiểm tra riêng.'},
        expires_at=now()+timedelta(minutes=15))
    db.add(row)
    await db.flush()
    audit(db, who, 'data.deletion_previewed', row.id, workspace.id, scope_hash=row.scope_hash)
    await db.commit()
    return data_out(row)


async def advance_deletion(db, workspace_id, request_id, who, body, target):
    workspace = await owner(db, workspace_id, who, True)
    row = await data_record(db, workspace, who, request_id, 'deletion')
    _, raw = await snapshot(db, workspace, who, Scope.model_validate(row.summary['scope']))
    if body.preview_hash != row.scope_hash or hashlib.sha256(raw).hexdigest() != row.scope_hash:
        raise HTTPException(409, 'Phạm vi hoặc dữ liệu đã thay đổi; xem trước lại')
    expected = 'preview' if target == 'requested' else 'requested'
    if row.status == target:
        return data_out(row)
    if row.status != expected:
        raise HTTPException(409, 'Cần tạo yêu cầu trước khi xác nhận riêng')
    row.status = target
    audit(db, who, 'data.deletion_'+target, row.id, workspace.id, scope_hash=row.scope_hash)
    await db.commit()
    return data_out(row)


@router.post(PREFIX+'/data/deletions/{request_id}/request')
async def request_deletion(workspace_id: UUID, request_id: UUID, body: ScopeConfirmation, who: Principal = Depends(principal), db=Depends(database)):
    return await advance_deletion(db, workspace_id, request_id, who, body, 'requested')


@router.post(PREFIX+'/data/deletions/{request_id}/confirm')
async def confirm_deletion(workspace_id: UUID, request_id: UUID, body: ScopeConfirmation, who: Principal = Depends(principal), db=Depends(database)):
    return await advance_deletion(db, workspace_id, request_id, who, body, 'confirmed')


@router.get(PREFIX+'/data/requests')
async def data_requests(workspace_id: UUID, who: Principal = Depends(principal), db=Depends(database)):
    workspace = await owner(db, workspace_id, who)
    rows = list(await db.scalars(select(DataLifecycleRequest).where(DataLifecycleRequest.workspace_id == workspace.id,
        DataLifecycleRequest.actor_id == who.id).order_by(DataLifecycleRequest.created_at.desc()).limit(100)))
    return {'requests': [data_out(row) for row in rows], 'automatic_deletion': False}
