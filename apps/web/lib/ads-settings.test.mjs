import test from 'node:test';import assert from 'node:assert/strict';
import {adsStatus,adsOAuthUrl,adsAccounts,adsJobs,adsSettingsError} from './ads-settings.mjs';
const origin='http://127.0.0.1:3201',state='fixture-state-not-real-12345678901234567890';
function oauth(provider){const url=new URL(provider==='meta'?'https://www.facebook.com/v26.0/dialog/oauth':'https://accounts.google.com/o/oauth2/v2/auth');const base='/v1/integrations/'+(provider==='meta'?'meta':'google-ads');for(const [key,value] of Object.entries({client_id:provider==='meta'?'12345':'fixture.apps.googleusercontent.com',state,response_type:'code',redirect_uri:origin+base+'/callback',scope:provider==='meta'?'ads_read':'https://www.googleapis.com/auth/adwords',...(provider==='google'?{access_type:'offline',prompt:'consent'}:{})}))url.searchParams.set(key,value);return url}
for(const provider of ['meta','google']){
 test(provider+' snapshot does not coerce partial/unknown data into connected',()=>{
  const row={configured:true,status:'connected',scopes:[]};assert.equal(adsStatus(provider,row),row);for(const change of [{configured:'yes'},{status:'healthy'},{scopes:{}},{scopes:[12]}])assert.throws(()=>adsStatus(provider,{...row,...change}),/ads_response_invalid/);
 });
 test(provider+' native OAuth host, read profile, callback and state are validated before navigation',()=>{
  assert.equal(adsOAuthUrl(provider,{authorization_url:oauth(provider).href},origin),oauth(provider).href);
  for(const mutate of [u=>{u.hostname='evil.example'},u=>{u.username='user'},u=>{u.protocol='http:'},u=>{u.hash='state'},u=>u.searchParams.set('redirect_uri','https://evil.example/callback'),u=>u.searchParams.set('scope','ads_management'),u=>u.searchParams.set('state','short'),u=>u.searchParams.set('client_secret','fixture-private'),u=>u.searchParams.append('state',state)]){const url=oauth(provider);mutate(url);assert.throws(()=>adsOAuthUrl(provider,{authorization_url:url.href},origin),/ads_oauth_url_invalid/)}
 });
}
test('cached accounts project only native IDs/name/currency, no arbitrary fields',()=>{
 assert.deepEqual(adsAccounts('meta',{rows:[{id:'act_1',name:'Fixture',currency:'USD',secret:'private'}],has_more:false}),[{id:'act_1',name:'Fixture',currency:'USD'}]);assert.deepEqual(adsAccounts('google',[{id:'1234567890',name:null,currency:'USD'}]),[{id:'1234567890',name:'1234567890',currency:'USD'}]);
 assert.throws(()=>adsAccounts('meta',{rows:[],has_more:'false'}));assert.throws(()=>adsAccounts('google',[{id:'act_1'}]));assert.throws(()=>adsAccounts('google',[{id:'1234567890'},{id:'1234567890'}]));
});
test('job metadata bounded and projected; unknown remains unknown not retriable',()=>{
 const row={id:'12345678-1234-1234-1234-123456789abc',kind:'accounts',status:'unknown',row_count:0,error_code:'private-secret'};assert.deepEqual(adsJobs([row]),[{id:row.id,kind:'accounts',status:'unknown',row_count:0}]);assert.throws(()=>adsJobs([{...row,row_count:-1}]));assert.throws(()=>adsJobs(Array(21).fill(row)));
});
test('stable error guidance never renders private provider text',()=>{
 assert.ok(!adsSettingsError('fixture-private').includes('fixture-private'));assert.match(adsSettingsError('ads_popup_blocked'),/chưa gửi OAuth start/);assert.match(adsSettingsError('ads_connection_grant_denied'),/không chuyển dự phòng/);assert.match(adsSettingsError('ads_oauth_url_invalid'),/phạm vi/);
});
