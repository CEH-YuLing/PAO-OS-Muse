"""Local operator CLI. Password comes from hidden prompt, never an argument."""
import argparse
import asyncio
import getpass

from sqlalchemy import select

from .auth import passwords
from .db import Session, engine
from .models import Member, User, Workspace


async def create(email, workspace_name, password):
    async with Session.begin() as db:
        if await db.scalar(select(User).where(User.email == email)):
            raise ValueError('User already exists; no changes made')
        user = User(email=email, password_hash=passwords.hash(password))
        workspace = Workspace(name=workspace_name)
        db.add_all([user, workspace])
        await db.flush()
        db.add(Member(workspace_id=workspace.id, user_id=user.id, role='owner'))
    await engine.dispose()
    print('Created owner and workspace.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--workspace', default='Personal')
    args = parser.parse_args()
    password = getpass.getpass('Password (at least 12 characters): ')
    if len(password) < 12 or len(password) > 256:
        raise SystemExit('Password must be 12–256 characters')
    asyncio.run(create(args.email.strip().lower(), args.workspace, password))
