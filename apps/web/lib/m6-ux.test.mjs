import test from 'node:test';
import assert from 'node:assert/strict';
import {businessDraftKey as key,saveBusinessDraft as save,readBusinessDraft as read,clearBusinessDrafts,discardBusinessDraft} from './business-drafts.mjs';
import {readSettingsNavigation,settingsNavigationUrl,readBusinessLocation,businessLocationUrl,modelGrantEligible as eligible} from './settings-navigation.mjs';
test('business drafts isolate actor, SME, brand and role; clones never share mutable state',()=>{
 clearBusinessDrafts();const a=key('a','A','','owner'),data={title:'A only'};save(a,data,100);data.title='mutated';
 assert.equal(read(a,101).title,'A only');const copy=read(a,101);copy.title='changed';assert.equal(read(a,102).title,'A only');
 for(const other of [key('b','A','','owner'),key('a','B','','owner'),key('a','A','brand','owner'),key('a','A','','viewer')])assert.equal(read(other,101),null);
 discardBusinessDraft(a);assert.equal(read(a,102),null);
});
test('draft retention bounded to 30 minutes and cleared on logout',()=>{const a=key('a','A','','owner');save(a,{title:'x'},100);assert.equal(read(a,1800100),null);save(a,{});clearBusinessDrafts();assert.equal(read(a),null);});
test('draft cache bounded to 20 scopes',()=>{clearBusinessDrafts();for(let i=0;i<21;i++)save(String(i),{i});assert.equal(read('0'),null);assert.equal(read('20').i,20);clearBusinessDrafts();});
test('settings deep links whitelist tabs/platforms, never execute query text',()=>{
 assert.deepEqual(readSettingsNavigation('?tab=integrations&platform=telegram'),{tab:'integrations',platform:'telegram'});
 assert.deepEqual(readSettingsNavigation('?tab=__proto__&platform=javascript:alert(1)'),{tab:'general',platform:'meta'});
 assert.equal(settingsNavigationUrl('http://localhost/settings?unrelated=1#help',{tab:'ai',platform:'meta'}),'/settings?unrelated=1&tab=ai#help');
});
const ref={id:'ref',workspace_id:'A',kind:'model',status:'staged',revision:2};
test('business deep link belongs to its SME and only carries opaque UUIDs',()=>{
 const plan='11111111-1111-1111-1111-111111111111';
 assert.deepEqual(readBusinessLocation('?sme=A&plan='+plan,'B'),{brand:'',plan:''});
 assert.deepEqual(readBusinessLocation('?sme=A&plan='+plan+'&brand=bad','A'),{brand:'',plan});
 assert.equal(businessLocationUrl('http://local/business-planning?plan=bad#bp-plan','A','',plan),'/business-planning?plan='+plan+'&sme=A#bp-plan');
});
const grant={reference_id:'ref',reference_revision:2,workspace_id:'A',grantee_id:'a',status:'staged',model_consent_recorded:true,brand_id:null,expires_at:'2030-01-01T00:00:00Z'};
test('model dropdown requires explicit consent, actor, SME, scope, expiry and current reference revision',()=>{
 const check=(g,r=ref,b=null)=>eligible(g,r,'a','A',b,0);assert.equal(check(grant),true);
 for(const change of [{model_consent_recorded:false},{grantee_id:'b'},{workspace_id:'B'},{reference_id:'other'},{reference_revision:1},{status:'revoked'},{expires_at:'bad'},{expires_at:'1970-01-01T00:00:00Z'},{brand_id:'private'}])assert.equal(check({...grant,...change}),false);
 assert.equal(check({...grant,brand_id:'brand'},ref,'brand'),true);assert.equal(check(grant,{...ref,status:'revoked'}),false);
 assert.equal(check(grant,ref,'brand'),false);
});
