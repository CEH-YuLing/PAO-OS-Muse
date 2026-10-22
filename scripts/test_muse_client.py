"""Offline Muse connection checks. No database, network or real CLI login."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException, Response
from fastapi import FastAPI
import httpx
from pao.modules.cli_connections import muse_client as muse
from pao.modules.cli_connections import muse_profile as profile


def native_rows():
    return {'providerId':'meta','source':'providerCatalog','models':[
        {'modelId':'muse-spark-1.3','displayLabel':'Muse Spark',
         'variants':['low','medium','high'],'defaultReasoningEffort':'high',
         'reasoningEffortVariants':[]}]}


class CatalogTests(unittest.TestCase):
    def test_complete_variants_not_description_subset(self):
        row = muse.catalog_rows(native_rows())[0]
        self.assertEqual(row['reasoning_efforts'], ['low','medium','high'])
        self.assertEqual(row['default_effort'], 'high')

    def test_bad_catalogs_refused(self):
        for change in ({'providerId':'openai'},{'source':'unknown'},{'models':[]},
                       {'models':[{}]},{'models':[native_rows()['models'][0]]*2}):
            with self.subTest(change=change), self.assertRaises(muse.MuseFailure):
                muse.catalog_rows({**native_rows(),**change})

    def test_unsupported_effort_default_refused(self):
        value = native_rows()
        value['models'][0]['defaultReasoningEffort'] = 'ultra'
        with self.assertRaises(muse.MuseFailure): muse.catalog_rows(value)

    def test_metadata_never_certifies_inference(self):
        value = muse.public({'revision':1,'connected':True,'models':muse.catalog_rows(native_rows()),
            'account_label':'private-account','token':'do-not-expose','binary_path':'private'},True)
        self.assertFalse(value['inference_enabled'])
        self.assertFalse(value['inference_verified'])
        self.assertFalse(value['quota_verified'])
        self.assertNotIn('private',json.dumps(value))
        self.assertEqual(value['scope'],'installation')

    def test_atomic_cache_and_missing_state(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(muse,'STATE',Path(folder)/'state.json'):
            self.assertEqual(muse.read_state()['revision'],0)
            data = {'revision':1,'connected':True,'models':muse.catalog_rows(native_rows())}
            muse.write_state(data)
            self.assertEqual(muse.read_state(),data)
            self.assertEqual([p.name for p in Path(folder).iterdir()],['state.json'])

    def test_invalid_state_not_returned(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(muse,'STATE',Path(folder)/'state.json'):
            muse.write_state({'revision':1,'connected':True,'models':[{'token':'private'}]})
            with self.assertRaises(muse.MuseFailure): muse.read_state()


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.state = patch.object(muse,'STATE',Path(self.folder.name)/'state.json')
        self.state.start()
        self.actor = SimpleNamespace(id=str(uuid4()))
        self.workspace = uuid4()
        self.db = SimpleNamespace(expire_all=lambda:None)
        self.metadata = {'account_state':'accountLogin','models':muse.catalog_rows(native_rows()),
            'observed_at':'2026-10-21T00:00:00+00:00','binary_version':muse.VERSION}

    async def asyncTearDown(self):
        self.state.stop()
        self.folder.cleanup()

    def command(self, rev=0, key=None):
        return muse.Command(request_key=key or uuid4(),expected_revision=rev)

    async def test_get_never_starts_cli(self):
        with patch.object(muse,'access',AsyncMock(return_value=True)), patch.object(muse,'discover',AsyncMock()) as probe:
            result = await muse.status(self.workspace,Response(),self.actor,self.db)
            self.assertEqual(result['revision'],0)
            probe.assert_not_called()

    async def test_non_manager_cannot_connect(self):
        with patch.object(muse,'access',AsyncMock(return_value=False)), patch.object(muse,'discover',AsyncMock()) as probe:
            with self.assertRaises(HTTPException) as caught:
                await muse.change(self.workspace,self.command(),Response(),self.actor,self.db,False)
            self.assertEqual(caught.exception.status_code,403)
            probe.assert_not_called()

    async def test_connect_replay_and_wrong_revision(self):
        command = self.command()
        with patch.object(muse,'access',AsyncMock(return_value=True)), patch.object(muse,'discover',AsyncMock(return_value=self.metadata)) as probe:
            first = await muse.change(self.workspace,command,Response(),self.actor,self.db,False)
            second = await muse.change(self.workspace,command,Response(),self.actor,self.db,False)
            self.assertEqual(first,second)
            self.assertTrue(first['connected'])
            self.assertFalse(first['inference_enabled'])
            self.assertEqual(probe.await_count,1)
            with self.assertRaises(HTTPException) as caught:
                await muse.change(self.workspace,self.command(),Response(),self.actor,self.db,False)
            self.assertEqual(caught.exception.detail,'muse_revision_conflict')

    async def test_replay_cannot_change_actor_or_operation(self):
        command = self.command()
        with patch.object(muse,'access',AsyncMock(return_value=True)), patch.object(muse,'discover',AsyncMock(return_value=self.metadata)):
            await muse.change(self.workspace,command,Response(),self.actor,self.db,False)
            for actor, disconnect in ((SimpleNamespace(id=str(uuid4())),False),(self.actor,True)):
                with self.assertRaises(HTTPException) as caught:
                    await muse.change(self.workspace,command,Response(),actor,self.db,disconnect)
                self.assertEqual(caught.exception.detail,'muse_request_conflict')

    async def test_authority_revoked_during_probe_does_not_publish(self):
        with patch.object(muse,'access',AsyncMock(side_effect=[True,False])), patch.object(muse,'discover',AsyncMock(return_value=self.metadata)):
            with self.assertRaises(HTTPException):
                await muse.change(self.workspace,self.command(),Response(),self.actor,self.db,False)
            self.assertEqual(muse.read_state()['revision'],0)

    async def test_disconnect_never_logs_native_out(self):
        muse.write_state({'revision':1,'connected':True,'models':muse.catalog_rows(native_rows())})
        with patch.object(muse,'access',AsyncMock(return_value=True)), patch.object(muse,'discover',AsyncMock()) as probe:
            result = await muse.change(self.workspace,self.command(1),Response(),self.actor,self.db,True)
            self.assertFalse(result['connected'])
            self.assertEqual(result['models'],[])
            self.assertEqual(result['revision'],2)
            probe.assert_not_called()

    async def test_probe_failure_preserves_saved_connection(self):
        old = {'revision':1,'connected':True,'models':muse.catalog_rows(native_rows())}
        muse.write_state(old)
        with patch.object(muse,'access',AsyncMock(return_value=True)), patch.object(muse,'discover',AsyncMock(side_effect=muse.MuseFailure('muse_schema_changed'))):
            with self.assertRaises(HTTPException):
                await muse.change(self.workspace,self.command(1),Response(),self.actor,self.db,False)
        self.assertEqual(muse.read_state(),old)

    async def test_access_checks_session_workspace_and_host_manager(self):
        with patch.object(muse,'check_session',AsyncMock()) as session, patch.object(muse,'membership',AsyncMock()) as member, patch.object(muse,'manager',AsyncMock(return_value=False)) as manager:
            self.assertFalse(await muse.access(self.db,self.workspace,self.actor))
            session.assert_awaited_once_with(self.db,self.actor)
            member.assert_awaited_once_with(self.db,str(self.workspace),self.actor)
            manager.assert_awaited_once_with(self.db,self.actor.id)

    async def test_http_contract_and_unknown_fields(self):
        app = FastAPI()
        app.include_router(muse.router)
        app.dependency_overrides[muse.principal] = lambda:self.actor
        app.dependency_overrides[muse.database] = lambda:self.db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            with patch.object(muse,'access',AsyncMock(return_value=True)), patch.object(muse,'discover',AsyncMock(return_value=self.metadata)) as probe:
                route = '/v1/muse-client?workspace_id='+str(self.workspace)
                response = await client.get(route)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers['cache-control'],'no-store')
                body = {'request_key':str(uuid4()),'expected_revision':0}
                for extra in ({'binary_path':'arbitrary'},{'prompt':'do not send'},{'api_key':'do not store'}):
                    denied = await client.post(route,json={**body,**extra})
                    self.assertEqual(denied.status_code,422)
                probe.assert_not_called()
                result = await client.post(route,json=body)
                self.assertEqual(result.status_code,200)
                self.assertFalse(result.json()['inference_enabled'])
                disconnected = await client.request('DELETE',route,json={'request_key':str(uuid4()),'expected_revision':1})
                self.assertEqual(disconnected.status_code,200)
                self.assertFalse(disconnected.json()['connected'])


class ProfileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old = profile._active
        profile._active = None

    async def asyncTearDown(self):
        await profile.cancel_login()
        profile._active = self.old

    async def test_profile_environment_does_not_forward_api_or_native_home(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(profile,'PROFILE',Path(folder)/'owned'), patch.dict('os.environ',{'META_API_KEY':'fixture-private','MUSE_AUTH_PATH':'old-auth'}):
            env = profile.environment()
            self.assertNotIn('META_API_KEY',env)
            self.assertNotIn('MUSE_AUTH_PATH',env)
            for key in ('HOME','USERPROFILE','XDG_CONFIG_HOME','XDG_DATA_HOME','MUSE_HOME'):
                self.assertTrue(Path(env[key]).is_relative_to(Path(folder)/'owned'))

    async def test_inference_methods_cannot_enter_auth_host(self):
        host = profile.Host(Path('not-run'),'schema')
        for method in ('session/start','turn/start','settings/writeValue','account/logout'):
            with self.assertRaises(profile.ProfileFailure): await host.query(method)

    async def test_login_code_only_visible_to_initiating_actor(self):
        row={'actor':'first','status':'pending','id':'fixture','url':'https://auth.meta.com/device','code':'FIXTURE'}
        self.assertEqual(profile.login_view(row,'other')['status'],'none')
        self.assertNotIn('code',str(profile.login_view(row,'other')))
        self.assertEqual(profile.login_view(row,'first')['user_code'],'FIXTURE')

    def fake_host(self, result=None):
        host = SimpleNamespace(open=AsyncMock(),close=AsyncMock(),query=AsyncMock(side_effect=[
            {'state':'loggedOut'},result or {'verificationUrl':'https://auth.meta.com/device','userCode':'FIXTURE'}]))
        return host

    async def test_pending_login_reused_and_cancel_closes_unscheduled_task(self):
        host = self.fake_host()
        with patch.object(profile,'Host',return_value=host):
            first = await profile.start_login('first',Path('not-run'),'schema')
            second = await profile.start_login('first',Path('not-run'),'schema')
            self.assertEqual(first,second)
            with self.assertRaises(profile.ProfileFailure): await profile.start_login('other',Path('not-run'),'schema')
            await profile.cancel_login('other')
            self.assertFalse(host.close.called)
            await profile.cancel_login('first')
            self.assertTrue(host.close.called)

    async def test_already_authenticated_never_starts_another_login(self):
        host = self.fake_host()
        host.query = AsyncMock(return_value={'state':'accountLogin'})
        with patch.object(profile,'Host',return_value=host):
            value = await profile.start_login('first',Path('not-run'),'schema')
            self.assertEqual(value['status'],'granted')
            host.query.assert_awaited_once_with('account/read')
            self.assertTrue(host.close.called)

    async def test_foreign_login_url_is_refused(self):
        for url in ('http://auth.meta.com/device','https://external.invalid/device','https://u:p@auth.meta.com/device'):
            host = self.fake_host({'verificationUrl':url,'userCode':'FIXTURE'})
            with patch.object(profile,'Host',return_value=host), self.assertRaises(profile.ProfileFailure):
                await profile.start_login('first',Path('not-run'),'schema')
            self.assertTrue(host.close.called)

    async def test_api_lane_does_not_fall_back_to_paid_auth(self):
        host = self.fake_host()
        host.query = AsyncMock(return_value={'state':'apiKey'})
        with patch.object(profile,'Host',return_value=host), self.assertRaises(profile.ProfileFailure):
            await profile.start_login('first',Path('not-run'),'schema')


if __name__ == '__main__':
    unittest.main()
