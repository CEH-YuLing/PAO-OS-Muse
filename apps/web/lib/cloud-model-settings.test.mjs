import test from 'node:test';import assert from 'node:assert/strict';
import {cleanModelKey,modelIds,modelRequest,modelSettingsError,modelHelp,modelKeyState,modelSaveConsent} from './cloud-model-settings.mjs';
const nonce='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',key='fixture-model-key-not-real';
test('saved key display distinguishes draft and stored state without retaining credentials',()=>{
 assert.deepEqual(modelKeyState({configured:false,key_hint:null}),{label:'Chưa lưu khóa',masked:''});
 assert.deepEqual(modelKeyState({configured:true,key_hint:'••••abcd'}),{label:'Đã lưu khóa',masked:'••••abcd'});
 const state=modelKeyState({configured:true,key_hint:key},key);assert.deepEqual(state,{label:'Đã nhập · chưa lưu',masked:'••••••••'});assert.ok(!JSON.stringify(state).includes(key));
 for(const hint of ['x'.repeat(200),'Bearer secret','••••ab\nc','••••'])assert.equal(modelKeyState({configured:true,key_hint:hint}).masked,'••••••••');
});
test('saving explicitly consents to provider catalogue, not inference, tools or subscription pooling',()=>{
 const message=modelSaveConsent('OpenAI','Doanh nghiệp A');assert.match(message,/OpenAI/);assert.match(message,/Doanh nghiệp A/);assert.match(message,/gọi nhà cung cấp/);assert.match(message,/Chưa chạy suy luận/);assert.ok(!message.includes(key));
});
test('key normalized but never coerced into shell/headers or prefix guesses',()=>{
 assert.equal(cleanModelKey('  '+key+'  '),key);for(const x of ['short','Bearer '+key,'"'+key+'"',key+'\nextra','x'.repeat(4097)])assert.throws(()=>cleanModelKey(x));
});
for(const provider of Object.keys(modelHelp))test(`${provider} native metadata paths and UUID header; no prompt/inference`,()=>{
 const request=modelRequest(provider,'connect','SME-B',{api_key:key},nonce);assert.equal(request.path,`/v1/model-providers/${provider}/connect`);
 assert.deepEqual(JSON.parse(request.body),{api_key:key,workspace_id:'SME-B'});assert.equal(request.headers['Idempotency-Key'],nonce);
 for(const action of ['catalogue','select'])assert.equal(modelRequest(provider,action,'B',action==='select'?{model:'fixture'}:undefined,nonce).headers['Idempotency-Key'],nonce);
 assert.throws(()=>modelRequest(provider,'catalogue','B',undefined,'old-invalid'));
 assert.throws(()=>modelRequest(provider,'connect','',{},nonce));
});
test('probe/default/disconnect use their existing contracts, not invented idempotency',()=>{
 assert.equal(modelRequest('openai','probe','B').path,'/v1/model-providers/openai/test?workspace_id=B');
 assert.equal(modelRequest('openai','disconnect','B').method,'DELETE');
 assert.equal(modelRequest('openai','default','B').headers['Idempotency-Key'],undefined);
});
test('catalogue shape and credential reflection do not become selectable model IDs',()=>{
 assert.deepEqual(modelIds(['one','one','two']),['one','two']);for(const list of [null,[1],['bad model'],['x'.repeat(161)],Array(501).fill('one')])assert.throws(()=>modelIds(list));
 assert.throws(()=>modelIds([key],key));
});
test('opaque errors never echo a key; registered probe and quota give actionable help',()=>{
 assert.ok(!modelSettingsError(key).includes(key));assert.match(modelSettingsError('model_probe_requires_explicit_grant_run'),/lượt xử lý/);
 assert.match(modelSettingsError('tenant_metadata_daily_exhausted'),/UTC/);assert.match(modelSettingsError('model_metadata_source_changed'),/không ghi đè/);
});
