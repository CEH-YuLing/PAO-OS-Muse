import hashlib
import time
from uuid import uuid4
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .config import settings
from .db import database
from .models import User, LoginSession

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash('invalid-account-placeholder')
bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    id: str
    expires: int
    token_hash: str | None = None
    auth_version: int = 0


def issue_token(user_id: str, auth_version: int = 0) -> str:
    return jwt.encode({'sub': user_id, 'iat': int(time.time()),
                       'exp': int(time.time()) + settings().jwt_minutes * 60,
                       'iss': 'pao-local', 'aud': 'pao-api', 'jti': uuid4().hex, 'ver': auth_version},
                      settings().jwt_secret, algorithm='HS256')


async def principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                    db: AsyncSession = Depends(database)) -> Principal:
    try:
        if not credentials:
            raise ValueError()
        payload = jwt.decode(credentials.credentials, settings().jwt_secret,
                             algorithms=['HS256'], issuer='pao-local', audience='pao-api',
                             options={'require': ['sub', 'exp', 'iat']})
        user = await db.get(User, payload['sub'])
        if not user or not user.active:
            raise ValueError()
        who = Principal(user.id, payload['exp'], hashlib.sha256(credentials.credentials.encode()).hexdigest(), payload.get('ver', 0))
        await check_session(db, who)
        from .modules.operations.request_trace import bind_actor
        bind_actor(who.id)
        return who
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, 'Đăng nhập lại để tiếp tục', headers={'WWW-Authenticate': 'Bearer'})


async def check_session(db, who):
    # Internal worker principals have no bearer token; domain grants/membership
    # remain their authority. Browser streams recheck the original token here.
    if not getattr(who, 'token_hash', None):
        return
    user = await db.get(User, who.id, populate_existing=True)
    row = await db.scalar(select(LoginSession).where(LoginSession.token_hash == who.token_hash)
                          .execution_options(populate_existing=True))
    if (not user or not user.active or who.expires <= time.time()
            or type(who.auth_version) is not int or user.auth_version != who.auth_version
            or (row and (row.revoked or row.user_id != who.id))):
        raise HTTPException(401, 'Phiên đăng nhập đã hết hạn hoặc bị thu hồi', headers={'WWW-Authenticate': 'Bearer'})


async def rate_limit(redis, namespace: str, subject: str, limit: int, window: int):
    key = f'limit:{namespace}:{hashlib.sha256(subject.encode()).hexdigest()}'
    # INCR and expiry must be atomic, including on worker/process failure.
    count = await redis.eval("local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n", 1, key, window)
    if count > limit:
        raise HTTPException(429, 'Quá nhiều yêu cầu. Vui lòng thử lại sau.', headers={'Retry-After': str(window)})
