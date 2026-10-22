import test from 'node:test';import assert from 'node:assert/strict';
import {metaAppCallback,metaAppStatus,metaAppPayload,metaAppError} from './meta-app-settings.mjs';
const status=()=>({app_id:'123',api_version:'v26.0',redirect_uri:'http://127.0.0.1:3201/v1/integrations/meta/callback',secret_present:true,revision:'a'.repeat(64),restart_required:true,write_enabled:false,autopilot_enabled:false,scope:'installation_local'});
const draft=()=>({appId:'123',version:'v26.0',callback:status().redirect_uri,secret:''});
test('strict host status rejects tenant scope, missing flags, raw secret and coercion',()=>{
 assert.equal(metaAppStatus(status()).scope,'installation_local');assert.equal(metaAppStatus({...status(),app_id:'',api_version:'',secret_present:false}).app_id,'');
 for(const change of [{scope:'workspace'},{write_enabled:'false'},{autopilot_enabled:undefined},{restart_required:'yes'},{app_secret:'fixture-private-secret'},{app_id:'not-numeric'},{api_version:'latest'},{revision:'bad'},{redirect_uri:'http://evil.example/callback'}])assert.throws(()=>metaAppStatus({...status(),...change}),/meta_app_response_invalid/);
});
test('callback native HTTPS/loopback exact path with no secret query or normalization',()=>{
 for(const uri of [status().redirect_uri,'https://pao.example/v1/integrations/meta/callback'])assert.equal(metaAppCallback(uri),uri);
 for(const uri of ['http://pao.example/v1/integrations/meta/callback','https://user:password@pao.example/v1/integrations/meta/callback',status().redirect_uri+'?token=x',status().redirect_uri+'#x','https://pao.example/x/../v1/integrations/meta/callback','https://pao.example/%76%31/integrations/meta/callback',status().redirect_uri+'\n'])assert.throws(()=>metaAppCallback(uri));
});
test('native revision used, empty password preserves same app key, no other flags',()=>{
 assert.deepEqual(metaAppPayload(status(),draft()),{app_id:'123',api_version:'v26.0',redirect_uri:status().redirect_uri,revision:'a'.repeat(64)});
 const body=metaAppPayload(status(),{...draft(),appId:'456',secret:'fixture-private-secret'});assert.equal(body.app_secret,'fixture-private-secret');assert.deepEqual(Object.keys(body).sort(),['api_version','app_id','app_secret','redirect_uri','revision']);
});
test('new/different app requires new secret; invalid key never silently trimmed',()=>{
 assert.throws(()=>metaAppPayload(status(),{...draft(),appId:'456'}),/meta_app_secret_required/);assert.throws(()=>metaAppPayload({...status(),secret_present:false},draft()),/meta_app_secret_required/);
 for(const change of [{secret:'short'},{secret:'fixture-private-secret '},{secret:'fixture-private-secret\n'},{appId:' 123'},{version:'vLatest'},{callback:status().redirect_uri+'?token=x'}])assert.throws(()=>metaAppPayload(status(),{...draft(),...change}),/meta_app_config_invalid_input/);
});
test('effective write/autopilot flags block save, not reset from UI',()=>{
 for(const change of [{write_enabled:true},{autopilot_enabled:true}])assert.throws(()=>metaAppPayload({...status(),...change},draft()),/meta_app_requires_readonly_mode/);
});
test('known scope/CAS/readonly errors actionable, unknown never echoed',()=>{
 assert.match(metaAppError('meta_app_config_requires_single_owner_workspace'),/S4/);assert.match(metaAppError('meta_app_config_stale'),/không ghi đè/);assert.match(metaAppError('meta_app_existing_encryption_key_invalid'),/không thay khóa tự động/);assert.ok(!metaAppError('fixture-private-secret').includes('fixture-private-secret'));
});
