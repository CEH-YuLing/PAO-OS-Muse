"""S23F native options semantics, ACL/revocation, bounded SELECT-only snapshot."""
from sqlalchemy import event,select
from pao.db import Session,engine
from pao.models import Brand,Member,User,Workspace

async def test_team_options_scoped_active_roles_revocation_no_store(client,identity):
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        outside=await db.scalar(select(User).where(User.email=='outside@example.test'))
        second=Workspace(name='Other SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=identity['user_id'],role='owner'))
        db.add(Member(workspace_id=second.id,user_id=outside.id,role='admin'))
        a=Brand(workspace_id=identity['workspace'],name='A brand');b=Brand(workspace_id=second.id,name='B brand');db.add_all([a,b]);await db.flush()
    path=lambda wid:f'/v1/workspaces/{wid}/connection-inventory/options'
    assert (await client.get(path(identity['workspace']))).status_code==401
    assert (await client.get(path(identity['workspace']),headers=identity['other'])).status_code==403
    assert (await client.get(path(identity['workspace']),headers=identity['outsider'])).status_code==404
    statements=[]
    def record(conn,cursor,statement,params,context,many):statements.append(statement.strip().split()[0].upper())
    event.listen(engine.sync_engine,'before_cursor_execute',record)
    try:
        for wid,ids,brand in [(identity['workspace'],{identity['user_id'],other.id},a.id),(second.id,{identity['user_id'],outside.id},b.id)]:
            response=await client.get(path(wid),headers=identity['owner']);body=response.json()
            assert response.status_code==200 and response.headers['cache-control']=='no-store'
            assert set(body)=={'members','brands','has_more'} and body['has_more'] is False
            assert {row['id'] for row in body['members']}==ids and {row['id'] for row in body['brands']}=={brand}
            assert all(set(row)=={'id','email','role'} for row in body['members'])
        assert statements and set(statements)=={'SELECT'}
    finally:event.remove(engine.sync_engine,'before_cursor_execute',record)
    async with Session.begin() as db:
        (await db.get(Member,(identity['workspace'],other.id))).role='viewer'
        (await db.get(User,outside.id)).active=False
        (await db.get(Member,(identity['workspace'],identity['user_id']))).role='admin'
    assert len((await client.get(path(identity['workspace']),headers=identity['owner'])).json()['members'])==1
    assert len((await client.get(path(second.id),headers=identity['owner'])).json()['members'])==1
    async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='operator'
    assert (await client.get(path(identity['workspace']),headers=identity['owner'])).status_code==403
    async with Session.begin() as db:await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
    assert (await client.get(path(identity['workspace']),headers=identity['owner'])).status_code==404

async def test_team_options_bounded_eligible_not_full_roster(client,identity):
    async with Session.begin() as db:
        for i in range(101):
            user=User(email=f'team-{i}@example.test',password_hash='not-a-login-fixture');db.add(user);await db.flush()
            db.add(Member(workspace_id=identity['workspace'],user_id=user.id,role='analyst'))
            db.add(Brand(workspace_id=identity['workspace'],name=f'Brand {i}'))
    response=await client.get(f"/v1/workspaces/{identity['workspace']}/connection-inventory/options",headers=identity['owner'])
    body=response.json();assert response.status_code==200
    assert len(body['members'])==len(body['brands'])==100 and body['has_more'] is True
    assert len({row['id'] for row in body['members']})==100
