"""Owned disposable DB: invocation/rotation serialization and fresh-process keys."""
import asyncio,json,os,re,subprocess,sys
from datetime import timedelta
from uuid import uuid4
from sqlalchemy.engine import make_url
from pao.config import ROOT,settings
from pao.skills import execution_binding


async def fixture(read=False):
    from sqlalchemy import select
    from pao.db import Session,engine
    from pao.models import User,Workspace,Member,MetaConnection,now
    from pao.auth import Principal
    from pao.integrations import ads_apps
    from pao.integrations.meta.client import MetaClient,MetaError,encrypt
    import httpx
    url=make_url(settings().database_url)
    assert os.environ.get('PAO_S4_LOCK_TEST')=='1' and re.fullmatch('pao_s4_lock_[0-9a-f]{32}',url.database or '')
    assert url.host=='127.0.0.1' and url.port==15432
    try:
        if read:
            async with Session() as db:
                wid=str(await db.scalar(select(Workspace.id).where(Workspace.name=='A')))
                context=await ads_apps.resolve(db,wid,'meta')
                assert context.revision==2 and context.mode=='byo' and context.config.meta_app_secret=='synthetic-rotated-key'
                assert context.binding==os.environ['PAO_S4_EXPECT_BINDING']
                conn=await db.scalar(select(MetaConnection));assert conn.status=='disconnected' and conn.token_ciphertext is None
            print(json.dumps({'pass':True,'fresh_process':True,'decrypted_exact':True,'binding_exact':True}));return
        async with Session.begin() as db:
            user=User(email='lock@example.test',password_hash='synthetic-no-login');a=Workspace(name='A');b=Workspace(name='B')
            db.add_all([user,a,b]);await db.flush()
            db.add_all([Member(workspace_id=w.id,user_id=user.id,role='owner') for w in (a,b)])
        who=Principal(user.id,0)
        def body(rev,key):return ads_apps.AppSave(mode='byo',expected_revision=rev,consent=True,client_id='456',client_secret=key,api_version='v26.0')
        async with Session() as db:await ads_apps.save(db,who,a.id,'meta',body(0,'synthetic-initial-key'))
        async with Session.begin() as db:
            context=await ads_apps.resolve(db,a.id,'meta')
            conn=MetaConnection(workspace_id=a.id,user_id=user.id,token_ciphertext=encrypt('synthetic-user-token'),app_binding=context.binding,
                expires_at=now()+timedelta(hours=1),status='connected',scopes=['ads_read']);db.add(conn);await db.flush();cid=conn.id
        entered,release,rotating=asyncio.Event(),asyncio.Event(),asyncio.Event();calls=[]
        async def http(request):
            assert request.url.host=='graph.facebook.com' and request.method=='GET';calls.append(1);entered.set()
            await release.wait();return httpx.Response(200,json={'id':'42'})
        client=MetaClient('synthetic-user-token',config=context.config,guard=ads_apps.invocation(conn,'meta',binding=context.binding),transport=httpx.MockTransport(http))
        async def rotate():
            async with Session() as db:
                rotating.set();return await ads_apps.save(db,who,a.id,'meta',body(1,'synthetic-rotated-key'))
        request=asyncio.create_task(client._request('me'));await asyncio.wait_for(entered.wait(),10)
        rotation=asyncio.create_task(rotate());await asyncio.wait_for(rotating.wait(),10);await asyncio.sleep(.2)
        assert not rotation.done(),'Rotation must wait for the admitted HTTP request'
        # An unrelated SME must remain configurable while A holds invocation locks.
        async with Session() as db:await asyncio.wait_for(ads_apps.save(db,who,b.id,'meta',body(0,'synthetic-other-key')),5)
        assert not rotation.done();release.set();assert (await asyncio.wait_for(request,10))['id']=='42'
        changed=await asyncio.wait_for(rotation,10);assert changed.revision==2
        try:await client._request('me')
        except MetaError as exc:assert str(exc)==ads_apps.DENIED
        else:raise AssertionError('Old client reached HTTP after rotation')
        assert len(calls)==1
        async with Session() as db:
            row=await db.get(MetaConnection,cid);assert row.status=='disconnected' and row.token_ciphertext is None
            final=await ads_apps.resolve(db,a.id,'meta')
        print(json.dumps({'pass':True,'invocation_serialized':True,'other_sme_unblocked':True,'stale_client_denied':True,
            'provider_fixture_calls':1,'fresh_binding':final.binding,'binding':execution_binding()}))
    finally:await engine.dispose()


async def main():
    from check_p11_migration import CONTAINER,snapshot
    from cryptography.fernet import Fernet
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    before=await snapshot(url);name='pao_s4_lock_'+uuid4().hex;assert re.fullmatch('pao_s4_lock_[0-9a-f]{32}',name)
    created=False
    def docker(*args):subprocess.run(['docker','exec',CONTAINER,*args],check=True,timeout=90)
    try:
        docker('createdb','-U','pao',name);created=True
        env={**os.environ,'DATABASE_URL':url.set(database=name).render_as_string(hide_password=False),'PAO_S4_LOCK_TEST':'1',
            'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),'JWT_SECRET':'synthetic-lock-'+uuid4().hex,
            'META_ENABLED':'true','META_REDIRECT_URI':'https://pao.fixture.invalid/v1/integrations/meta/callback','META_WRITE_ENABLED':'false',
            'GOOGLE_ADS_ENABLED':'false','TELEGRAM_ENABLED':'false','TELEGRAM_SCOPED_RUNTIME_ENABLED':'false'}
        subprocess.run([sys.executable,'-m','alembic','upgrade','0065'],cwd=ROOT,env=env,check=True,timeout=120)
        def child(arg):
            r=subprocess.run([sys.executable,__file__,arg],cwd=ROOT,env=env,capture_output=True,text=True,check=True,timeout=90)
            return json.loads(r.stdout.splitlines()[-1])
        live=child('--fixture');env['PAO_S4_EXPECT_BINDING']=live.pop('fresh_binding');restored=child('--read')
        assert live['pass'] and restored['pass'] and await snapshot(url)==before
        result={**live,'fresh_process':restored,'primary_unchanged':True,'real_provider_calls':False}
        (ROOT/'.runtime/s4-locks.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:
        if created:docker('dropdb','-U','pao',name);print('Removed only invocation-owned lock-test DB; primary preserved.')


if __name__=='__main__':
    asyncio.run(fixture('--read' in sys.argv) if '--fixture' in sys.argv or '--read' in sys.argv else main())
