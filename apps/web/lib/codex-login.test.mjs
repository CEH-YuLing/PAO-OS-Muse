import test from 'node:test';import assert from 'node:assert/strict';
import {codexLoginPath,codexLoginCapability,codexLoginView} from './codex-login.mjs';
const id='11111111-1111-4111-8111-111111111111',other='22222222-2222-4222-8222-222222222222';
const value=()=>({operation_id:other,connection_id:id,version:3,status:'awaiting_user',expires_in:600,user_code:'ABCD-EFGH',verification_url:'https://auth.openai.com/codex/device',provider_inference_verified:false,grant_activated:false});
test('Codex URLs only target scoped native auth actions',()=>{
 assert.equal(codexLoginPath(id,id,'login'),`/v1/workspaces/${id}/cli-connections/${id}/login`);
 for(const args of [['../',id,'login'],[id,'https://evil.test','login'],[id,id,'run'],[id,id,'login-capabilities']])assert.throws(()=>codexLoginPath(...args));
});
test('only a separately enabled local-personal capability opens Codex UI login',()=>{
 const data={provider:'codex_cli',browser_login_enabled:true,scope:'local_personal_self_only',managed_by:'official_codex_app_server',subscription_sharing_enabled:false,tools_enabled:false};
 assert.equal(codexLoginCapability(data),true);assert.equal(codexLoginCapability({...data,browser_login_enabled:false}),false);
 for(const patch of [{tools_enabled:true},{subscription_sharing_enabled:true},{scope:'shared_saas'},{provider:'openai'}])assert.throws(()=>codexLoginCapability({...data,...patch}));
});
test('one-time code only appears in current own awaiting-user state and official URL',()=>{
 assert.equal(codexLoginView(value(),id).user_code,'ABCD-EFGH');
 for(const patch of [{connection_id:other},{verification_url:'https://auth.openai.com.evil.test/codex/device'},{verification_url:'https://auth.openai.com/codex/device?code=ABCD'},{user_code:'secret\nCODE'},{status:'connected'},{expires_in:999},{grant_activated:true}])assert.throws(()=>codexLoginView({...value(),...patch},id));
 assert.equal(codexLoginView({...value(),status:'connected',user_code:null,verification_url:null},id).user_code,null);
 assert.ok(!JSON.stringify(codexLoginView({...value(),token:'not-retained'},id)).includes('not-retained'));
});
