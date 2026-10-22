import json,os
import unittest
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pao_client_adapters import AdapterFailure,external_dispatch
from pao_client_adapters.claude_plan import NativeScope,REQUIRED_FLAGS,SETTINGS,VERSION,metadata_environment,prepare

def scope():return NativeScope(*(str(uuid4()) for _ in range(6)))
def build(**overrides):
    return prepare(**{'scope':scope(),'model':'claude-synthetic-1','messages':[{'role':'user','content':'Tiếng Việt 🐾'}],
                     'binary_version':VERSION,'flags':REQUIRED_FLAGS,**overrides})

class ClaudePlanTests(unittest.TestCase):
    def test_prompt_never_goes_into_argv_or_repr(self):
        text='SECRET_SENTINEL & powershell.exe --dangerously-skip-permissions'
        plan=build(messages=[{'role':'user','content':text}])
        self.assertEqual(json.loads(plan.stdin)['messages'][0]['content'],text)
        self.assertNotIn('SECRET_SENTINEL',' '.join(plan.argv))
        self.assertNotIn('SECRET_SENTINEL',repr(plan))

    def test_native_plan_never_launches_or_grants(self):
        plan=build()
        self.assertFalse(plan.live_dispatch_allowed)
        self.assertFalse(hasattr(plan,'run'))
        self.assertFalse(hasattr(plan,'token'))
        with self.assertRaisesRegex(AdapterFailure,'^adapter_live_disabled$'):external_dispatch(plan,enabled=True)

    def test_no_resume_fallback_or_bare_subscription_breakage(self):
        args=build().argv
        for flag in ('--continue','--resume','--fork-session','--fallback-model','--bare','--dangerously-skip-permissions',
                     '--allow-dangerously-skip-permissions','--add-dir','--plugin-dir','--chrome','--ide'):
            self.assertNotIn(flag,args)

    def test_tools_mcp_hooks_and_memory_explicitly_disabled(self):
        args=build().argv
        self.assertEqual(args[args.index('--tools')+1],'')
        self.assertEqual(args[args.index('--permission-mode')+1],'dontAsk')
        self.assertEqual(json.loads(args[args.index('--mcp-config')+1]),{'mcpServers':{}})
        self.assertIn('--strict-mcp-config',args)
        settings=json.loads(args[args.index('--settings')+1])
        self.assertEqual(settings,SETTINGS)
        self.assertTrue(settings['disableAllHooks'])
        self.assertFalse(settings['autoMemoryEnabled'])
        self.assertIn('--no-session-persistence',args)

    def test_identity_and_attempt_are_explicit(self):
        identity=scope();plan=build(scope=identity)
        self.assertEqual(plan.scope,identity)
        self.assertEqual(plan.argv[plan.argv.index('--session-id')+1],identity.attempt_id)
        self.assertNotEqual(build(scope=replace(identity,attempt_id=str(uuid4()))).argv,plan.argv)

    def test_scope_rejects_noncanonical_ids(self):
        original=scope()
        for field in vars(original):
            for value in ('bad','',None,str(uuid4()).upper()):
                with self.subTest(field=field),self.assertRaises(AdapterFailure):replace(original,**{field:value})

    def test_wrong_scope_object_not_accepted(self):
        with self.assertRaises(AdapterFailure):build(scope=vars(scope()))

    def test_version_change_requires_review(self):
        for version in ('2.1.221','latest',None,True):
            with self.assertRaises(AdapterFailure):build(binary_version=version)

    def test_missing_measured_flags_rejected(self):
        for flag in REQUIRED_FLAGS:
            with self.subTest(flag=flag),self.assertRaises(AdapterFailure):build(flags=REQUIRED_FLAGS-{flag})
        with self.assertRaises(AdapterFailure):build(flags=list(REQUIRED_FLAGS))

    def test_explicit_model_not_alias_or_shell(self):
        for model in ('sonnet','default','--model','claude-test;evil','claude-test bad','claude-'+('x'*120),None):
            with self.assertRaises(AdapterFailure):build(model=model)

    def test_message_contract_strict(self):
        for messages in ([],None,'text',[{'role':'tool','content':'x'}],[{'role':'user','content':1}],
                         [{'role':'user','content':'x','command':'x'}],[{'role':'user','content':'x\x00'}],
                         [{'role':'user','content':'\ud800'}],[{'role':'user','content':'x'}]*129):
            with self.assertRaises(AdapterFailure):build(messages=messages)

    def test_input_size_bounded(self):
        with self.assertRaises(AdapterFailure):build(messages=[{'role':'user','content':'🐾'*65536}])

    def test_environment_does_not_inherit_keys_or_parent_profile(self):
        original=dict(os.environ)
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'SECRET_SENTINEL','CLAUDE_CODE_OAUTH_TOKEN':'SECRET_SENTINEL',
                                   'HTTP_PROXY':'http://sentinel','HOME':'secret-home','PATH':'secret-path'}):
            child=metadata_environment()
            self.assertFalse(any('SECRET_SENTINEL' in v or 'secret-' in v for v in child.values()))
            self.assertNotIn('ANTHROPIC_API_KEY',child)
            self.assertNotIn('HTTP_PROXY',child)
            self.assertEqual(child['CLAUDE_CONFIG_DIR'],'/profile/.claude')
        self.assertEqual(dict(os.environ),original)

if __name__=='__main__':unittest.main()
