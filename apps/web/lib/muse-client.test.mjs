import test from 'node:test';
import assert from 'node:assert/strict';
import {museStatus,museError,museLogin} from './muse-client.mjs';
const base={revision:0,connected:false,can_manage:false,models:[],inference_enabled:false,inference_verified:false,connection_mode:'catalog_only',scope:'installation',credentials_stored_in_PAO:false};
test('Muse metadata connection is not inference admission',()=>{
 assert.equal(museStatus(base).inference_enabled,false);
 for(const patch of [{inference_enabled:true},{inference_verified:true},{scope:'personal'},{credentials_stored_in_PAO:true},{revision:-1},{models:[{}]}])assert.throws(()=>museStatus({...base,...patch}));
});
test('Muse text adapter status requires explicit matching server admission',()=>{
 assert.equal(museStatus({...base,inference_enabled:true,connection_mode:'text_adapter'}).inference_enabled,true);
 assert.throws(()=>museStatus({...base,inference_enabled:false,connection_mode:'text_adapter'}));
});
test('Muse errors explain recovery without reflecting provider secrets',()=>{
 assert.match(museError('muse_schema_changed'),/tương thích/);
 assert.match(museError('muse_revision_conflict'),/Đọc lại/);
 assert.ok(!museError('provider says private-value').includes('private-value'));
});
test('Muse login accepts official URLs and keeps the key lane out of the UI',()=>{
 const value={status:'pending',profile:'pao_isolated',verification_url:'https://auth.meta.com/device',user_code:'FIXTURE'};
 assert.equal(museLogin(value).user_code,'FIXTURE');
 assert.deepEqual(museLogin({status:'granted',profile:'pao_isolated',token:'must-not-retain'}),{status:'granted'});
 for(const url of ['http://auth.meta.com/device','https://external.invalid/device','https://u:p@auth.meta.com/device'])assert.throws(()=>museLogin({...value,verification_url:url}));
});
