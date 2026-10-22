import test from 'node:test';
import assert from 'node:assert/strict';
import {personalCodexPath,personalCodexView,personalCodexSave,connectPersonalCodex} from './personal-codex-setup.mjs';
const wid='11111111-1111-4111-8111-111111111111',uid='22222222-2222-4222-8222-222222222222',cid='33333333-3333-4333-8333-333333333333',key='44444444-4444-4444-8444-444444444444';
const raw=()=>({workspace_id:wid,actor_id:uid,revision:0,enabled:false,make_default:false,ready:false,connection_id:null,connections:[{id:cid,model:'synthetic-model',status:'connected',authentication_ready:true,operation_pending:false}],scope:'local_personal_self_only',tools_enabled:false,provider_calls:false,expires_at:null});
const view=()=>personalCodexView(raw(),wid,uid);
test('own-profile path accepts only canonical workspace UUID',()=>{assert.equal(personalCodexPath(wid),`/v1/workspaces/${wid}/personal-cli`);for(const value of ['',null,'../other'])assert.throws(()=>personalCodexPath(value))});
test('metadata is not activation and does not retain secrets/profile/cache paths',()=>{const value=personalCodexView({...raw(),token:'not-kept',connections:[{...raw().connections[0],profile_id:'not-kept'}]},wid,uid);assert.equal(value.token,undefined);assert.equal(value.connections[0].profile_id,undefined);assert.equal(value.enabled,false)});
test('own consent creates a setting, no grantee or TTL or tools',()=>{const result=personalCodexSave(view(),{enabled:true,makeDefault:true,connection:cid},key,true);assert.deepEqual(result,{request_key:key,expected_revision:0,connection_id:cid,enabled:true,make_default:true,allow_personal_inference_ack:true});assert.equal(result.ttl_minutes,undefined);assert.equal(result.grantee_id,undefined)});
test('explicit consent and completed login required',()=>{const draft={enabled:true,makeDefault:true,connection:cid};assert.throws(()=>personalCodexSave(view(),draft,key,false));for(const patch of [{authentication_ready:false},{operation_pending:true}]){const value=personalCodexView({...raw(),connections:[{...raw().connections[0],...patch}]},wid,uid);assert.throws(()=>personalCodexSave(value,draft,key,true))}});
test('disable works with stale/deleted source without reauthentication',()=>{const result=personalCodexSave({...view(),connections:[]},{enabled:false,makeDefault:true,connection:cid},key,false);assert.equal(result.connection_id,null);assert.equal(result.make_default,false)});
test('wrong owner/SME, shared scope, tools or expiry cannot enter own setup UI',()=>{for(const patch of [{workspace_id:cid},{actor_id:cid},{scope:'shared'},{tools_enabled:true},{expires_at:'tomorrow'},{provider_calls:true},{revision:-1},{ready:'true'},{connection_id:'../'}])assert.throws(()=>personalCodexView({...raw(),...patch},wid,uid))});
test('invalid profile rows and duplicates are rejected',()=>{for(const patch of [{id:'../'},{model:'bad model'},{status:'healthy'},{operation_pending:null},{status:'pending',authentication_ready:true}])assert.throws(()=>personalCodexView({...raw(),connections:[{...raw().connections[0],...patch}]},wid,uid));assert.throws(()=>personalCodexView({...raw(),connections:[raw().connections[0],raw().connections[0]]},wid,uid))});
test('save retains revision, rejects forged source and wrong types',()=>{const value={...view(),revision:9},draft={enabled:true,makeDefault:true,connection:cid};assert.equal(personalCodexSave(value,draft,key,true).expected_revision,9);assert.throws(()=>personalCodexSave(value,{...draft,connection:uid},key,true));assert.throws(()=>personalCodexSave(value,draft,'../',true));assert.throws(()=>personalCodexSave(value,{...draft,enabled:'true'},key,true))});

test('explicit Connect binds the current own profile without changing default or granting tools',async()=>{
 const calls=[];const request=async(path,method='GET',body)=>{calls.push({path,method,body});return method==='GET'?raw():{...raw(),revision:1,enabled:true,ready:true,connection_id:cid}};
 const result=await connectPersonalCodex(request,wid,uid,cid,key,()=>true);
 assert.ok(result.ready);assert.equal(calls.length,2);assert.equal(calls[1].method,'PUT');
 assert.equal(calls[1].body.make_default,false);assert.equal(calls[1].body.allow_personal_inference_ack,true);
 assert.equal(calls[1].body.connection_id,cid);assert.equal(calls[1].body.grantee_id,undefined);
});

test('reconnect keeps prior default preference and exact policy revision',async()=>{
 let body;const request=async(path,method='GET',data)=>{if(method==='PUT')body=data;return {...raw(),revision:7,enabled:true,make_default:true,ready:method==='PUT',connection_id:cid}};
 await connectPersonalCodex(request,wid,uid,cid,key,()=>true);
 assert.equal(body.expected_revision,7);assert.equal(body.make_default,true);
});

test('a ready profile is reused without another activation or provider request',async()=>{
 let calls=0;await connectPersonalCodex(async()=>{calls++;return {...raw(),enabled:true,ready:true,connection_id:cid}},wid,uid,cid,key,()=>true);
 assert.equal(calls,1);
});

test('scope change before save or wrong owner response never activates a source',async()=>{
 let current=true,calls=0;
 await assert.rejects(()=>connectPersonalCodex(async()=>{calls++;current=false;return raw()},wid,uid,cid,key,()=>current));assert.equal(calls,1);
 await assert.rejects(()=>connectPersonalCodex(async()=>({...raw(),actor_id:cid}),wid,uid,cid,key,()=>true));
});

test('lost save acknowledgement is not retried automatically',async()=>{
 let writes=0;await assert.rejects(()=>connectPersonalCodex(async(path,method='GET')=>{if(method==='GET')return raw();writes++;throw new Error('lost ACK')},wid,uid,cid,key,()=>true));
 assert.equal(writes,1);
});
