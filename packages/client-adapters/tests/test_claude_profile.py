import json
from dataclasses import asdict,replace
from pathlib import Path
import sys
import unittest
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pao_client_adapters import AdapterFailure
from pao_client_adapters.claude_profile import Profile,auth_summary
from pao_client_adapters.claude_plan import VERSION

def profile():
    return Profile(*(str(uuid4()) for _ in range(5)),image_id='sha256:'+'a'*64,binary_sha256='b'*64,binary_version=VERSION)

class ProfileTests(unittest.TestCase):
    def test_scope_fields_are_not_customer_commands(self):
        row=profile()
        for field in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
            with self.assertRaises(AdapterFailure):replace(row,**{field:'bad; command'})

    def test_image_digest_and_version_are_pinned(self):
        row=profile()
        for change in ({'image_id':'latest'},{'binary_sha256':'b'*63},{'binary_version':'latest'}):
            with self.assertRaises(AdapterFailure):replace(row,**change)

    def test_volume_labels_reject_cross_scope(self):
        row=profile();info={'Name':row.volume,'Driver':'local','Options':None,'Labels':row.labels}
        row.check_volume(info)
        for field in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
            wrong=replace(row,**{field:str(uuid4())})
            with self.subTest(field=field),self.assertRaises(AdapterFailure):wrong.check_volume(info)

    def test_unexpected_volume_options_and_labels_denied(self):
        row=profile();info={'Name':row.volume,'Driver':'local','Options':None,'Labels':row.labels}
        for change in ({'Driver':'nfs'},{'Options':{'device':'/host'}},{'Labels':{**row.labels,'other':'x'}}):
            with self.assertRaises(AdapterFailure):row.check_volume({**info,**change})

    def test_wrong_binary_image_never_accepted(self):
        row=profile();config={'User':'65534:65534','Labels':{'pao.claude.binary-sha256':row.binary_sha256,'pao.claude.version':VERSION}}
        row.check_image({'Id':row.image_id,'Config':config})
        with self.assertRaises(AdapterFailure):row.check_image({'Id':row.image_id,'Config':{**config,'User':'0'}})
        with self.assertRaises(AdapterFailure):row.check_image({'Id':'sha256:'+'c'*64,'Config':config})

    def test_login_is_original_auth_only_without_prompt_or_console(self):
        row=profile();args=row.command(str(uuid4()),'login')
        self.assertEqual(args[-4:],[row.image_id,'auth','login','--claudeai'])
        self.assertNotIn('--console',args)
        self.assertNotIn('--print',args)
        self.assertNotIn('--bare',args)
        self.assertNotIn('--privileged',args)
        self.assertIn('--network=bridge',args)
        self.assertIn('--read-only',args)
        self.assertIn('type=volume,source='+row.volume+',target=/profile',args)
        self.assertEqual(args[args.index('--user')+1],'65534:65534')

    def test_status_is_offline_without_real_inference(self):
        row=profile();args=row.command(str(uuid4()),'status')
        self.assertEqual(args[-4:],[row.image_id,'auth','status','--json'])
        self.assertIn('--network=none',args)
        self.assertNotIn('--interactive',args)
        self.assertNotIn('--tty',args)

    def test_unknown_actions_and_operation_id_denied(self):
        row=profile()
        for action in ('exec','prompt','logout','setup-token','update','login --console'):
            with self.assertRaises(AdapterFailure):row.command(str(uuid4()),action)
        with self.assertRaises(AdapterFailure):row.command('--help','login')

    def test_auth_summary_omits_identifiers_and_credentials(self):
        raw=json.dumps({'loggedIn':True,'authMethod':'claude.ai','email':'SECRET_SENTINEL',
                        'orgName':'SECRET_SENTINEL','accessToken':'SECRET_SENTINEL','configDirectory':'SECRET_SENTINEL'}).encode()
        summary=auth_summary(raw,0)
        self.assertEqual(summary['state'],'signed_in_personal_candidate')
        self.assertNotIn('SECRET_SENTINEL',json.dumps(summary))
        self.assertFalse(summary['native_connection_enrolled'])
        self.assertFalse(summary['shared_use_allowed'])
        self.assertFalse(summary['provider_inference_verified'])

    def test_no_auth_report_is_not_a_network_failure(self):
        self.assertEqual(auth_summary(b'{"loggedIn":false,"authMethod":"none"}',1)['state'],'not_authenticated')

    def test_api_or_unknown_method_cannot_become_subscription(self):
        for method in ('api_key','api_key_helper','third_party','oauth_token',None,'unknown'):
            summary=auth_summary(json.dumps({'loggedIn':True,'authMethod':method}).encode(),0)
            self.assertEqual(summary['state'],'unsupported_or_unknown_auth')

    def test_malformed_and_wrong_exit_auth_status_denied_or_unknown(self):
        for raw in (b'not json',b'{"loggedIn":1}',b'{"loggedIn":false,"loggedIn":true}',b'{}'):
            with self.assertRaises(AdapterFailure):auth_summary(raw,0)
        for code in (True,None):
            with self.assertRaises(AdapterFailure):auth_summary(b'{"loggedIn":true}',code)
        self.assertEqual(auth_summary(b'{"loggedIn":false}',0)['state'],'unsupported_or_unknown_auth')

if __name__=='__main__':unittest.main()
