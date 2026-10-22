import test from 'node:test';
import assert from 'node:assert/strict';
import {agyPath,agyView,agyError,agySmoke} from './antigravity-native.mjs';
const w='11111111-1111-4111-8111-111111111111',a='22222222-2222-4222-8222-222222222222';
const row=()=>({workspace_id:w,actor_id:a,provider:'antigravity_native',scope:'local_personal_machine_session',credentials_stored_in_PAO:false,inference_enabled:false,inference_called:false,provider_support_confirmed:false,status:'catalog_available',models:['gemini-fixture'],busy:false});
test('native Antigravity routes fixed by current workspace',()=>{
 assert.equal(agyPath(w,'connect'),`/v1/workspaces/${w}/antigravity-native/connect`);
 for(const v of ['','../other',null])assert.throws(()=>agyPath(v));
 for(const v of ['logout','run','https://evil.test'])assert.throws(()=>agyPath(w,v));
});
test('native smoke messages are actionable and never expose arbitrary details',()=>{
 assert.match(agyError('antigravity_native_tools_not_disabled'),/trước khi gửi/);
 assert.match(agyError('antigravity_native_binary_changed'),/xác minh chữ ký/);
 assert.ok(!agyError('PRIVATE-TOKEN').includes('PRIVATE-TOKEN'));
 assert.equal(agyPath(w,'test'),`/v1/workspaces/${w}/antigravity-native/test`);
 const value={workspace_id:w,actor_id:a,attempt_id:w,status:'passed',model:'gemini-3.8-flash-low',response:'PAO_ANTIGRAVITY_OK',inference_verified:true,prompt_sent:true,tools_enabled:false,general_chat_enabled:false,provider_support_confirmed:false};
 assert.equal(agySmoke(value,w,a),'PAO_ANTIGRAVITY_OK');
 for(const patch of [{workspace_id:a},{actor_id:w},{tools_enabled:true},{general_chat_enabled:true},{status:'blocked'},{response:'unverified'}])assert.throws(()=>agySmoke({...value,...patch},w,a));
});
test('native observed catalog does not imply inference or provider approval',()=>{
 assert.deepEqual(agyView({...row(),secret:'not retained'},w,a),{status:'catalog_available',models:['gemini-fixture'],busy:false});
 for(const patch of [{workspace_id:a},{actor_id:w},{inference_called:true},{inference_enabled:true},{provider_support_confirmed:true},{credentials_stored_in_PAO:true},{models:[]},{models:['unsafe value']},{models:['gemini-a','gemini-a']},{status:'connected'}])assert.throws(()=>agyView({...row(),...patch},w,a));
 assert.deepEqual(agyView({...row(),status:'not_checked',models:[]},w,a),{status:'not_checked',models:[],busy:false});
});
