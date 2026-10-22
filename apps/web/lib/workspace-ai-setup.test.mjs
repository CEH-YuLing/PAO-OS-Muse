import test from 'node:test';
import assert from 'node:assert/strict';
import {workspaceAiPolicy,workspaceAiDraft,workspaceAiSave,workspaceAiSettingsUrl} from './workspace-ai-setup.mjs';
const workspace='11111111-1111-4111-8111-111111111111',one='22222222-2222-4222-8222-222222222222',two='33333333-3333-4333-8333-333333333333',key='44444444-4444-4444-8444-444444444444';
const connection=(id=one)=>({id,provider:'openai',model:'synthetic-model',status:'connected',selected:false,available:false,is_default:false});
const raw=()=>({workspace_id:workspace,revision:0,enabled:false,can_manage:true,connections:[connection()],default_connection_id:null});
const policy=()=>workspaceAiPolicy(raw(),workspace);
test('one owner needs no staff or service identity in setup; sole source is only an unsaved suggestion',()=>{
 const value=policy(),before=structuredClone(value),draft=workspaceAiDraft(value);
 assert.deepEqual(draft,{selected:[one],defaultId:one,enabled:false,suggested:true});
 assert.deepEqual(value,before);assert.equal(value.enabled,false);assert.equal(value.default_connection_id,null);
});
test('multiple sources are not silently selected or enabled',()=>{
 const value=workspaceAiPolicy({...raw(),connections:[connection(),connection(two)]},workspace);
 assert.deepEqual(workspaceAiDraft(value),{selected:[],defaultId:'',enabled:false,suggested:false});
});
test('existing additional sources and default remain selected without dropping an old connection',()=>{
 const value=workspaceAiPolicy({...raw(),enabled:true,revision:4,default_connection_id:one,connections:[{...connection(),selected:true,available:true,is_default:true},{...connection(two),selected:true,available:true}]},workspace);
 assert.deepEqual(workspaceAiDraft(value),{selected:[one,two],defaultId:one,enabled:true,suggested:false});
});
test('deleted default does not select a different provider implicitly and can still be disabled',()=>{
 const value=workspaceAiPolicy({...raw(),enabled:true,revision:2,default_connection_id:two,connections:[]},workspace);
 const draft=workspaceAiDraft(value);assert.equal(draft.defaultId,'');
 assert.deepEqual(workspaceAiSave(value,{...draft,enabled:false},key,false).connection_ids,[]);
});
test('enable requires explicit consent and valid default, even for an owner',()=>{
 const value=policy(),draft={...workspaceAiDraft(value),enabled:true};
 assert.throws(()=>workspaceAiSave(value,draft,key,false));
 assert.throws(()=>workspaceAiSave(value,{...draft,defaultId:''},key,true));
 assert.throws(()=>workspaceAiSave(value,{...draft,selected:[]},key,true));
 assert.deepEqual(workspaceAiSave(value,draft,key,true),{request_key:key,expected_revision:0,enabled:true,connection_ids:[one],default_connection_id:one,allow_enterprise_inference_ack:true});
});
test('save uses existing policy revision and does not invent grants, tools or paid fallback',()=>{
 const value=policy();value.revision=9;
 const body=workspaceAiSave(value,{...workspaceAiDraft(value),enabled:true},key,true);
 assert.equal(body.expected_revision,9);assert.equal(body.grantee_id,undefined);assert.equal(body.tools_enabled,undefined);assert.equal(body.fallback,undefined);
});
test('read-only member cannot construct a settings write',()=>{
 const value=workspaceAiPolicy({...raw(),can_manage:false},workspace);
 assert.throws(()=>workspaceAiSave(value,workspaceAiDraft(value),key,true));
});
test('rotation/error source cannot enable, but disabling remains possible',()=>{
 const value=workspaceAiPolicy({...raw(),enabled:true,revision:2,default_connection_id:one,connections:[{...connection(),selected:true,is_default:true,status:'error'}]},workspace);
 assert.throws(()=>workspaceAiSave(value,workspaceAiDraft(value),key,true));
 assert.equal(workspaceAiSave(value,{...workspaceAiDraft(value),enabled:false},key,false).default_connection_id,null);
});
test('save rejects unknown or duplicate selections, wrong types and malformed request IDs',()=>{
 const value=policy(),draft=workspaceAiDraft(value);
 for(const patch of [{selected:[two]},{selected:[one,one]},{defaultId:two},{selected:null},{enabled:'true'}])assert.throws(()=>workspaceAiSave(value,{...draft,...patch},key,true));
 for(const bad of ['',null,'../../secret'])assert.throws(()=>workspaceAiSave(value,draft,bad,true));
 assert.throws(()=>workspaceAiSave(value,draft,key,'true'));
});
test('policy DTO is whitelisted, never keeps raw credentials or unrelated server fields',()=>{
 const value=workspaceAiPolicy({...raw(),secret:'not-retained',connections:[{...connection(),api_key:'not-retained'}]},workspace);
 assert.equal(value.secret,undefined);assert.equal(value.connections[0].api_key,undefined);
});
test('reject wrong SME, invalid shape, inconsistent availability and duplicate sources',()=>{
 for(const patch of [{workspace_id:two},{revision:-1},{revision:0.5},{enabled:'true'},{can_manage:1},{connections:null},{default_connection_id:'../../'},
  {connections:[connection(),connection()]},{connections:[{...connection(),available:true}]},{connections:[{...connection(),provider:'codex_cli'}]},
  {connections:[{...connection(),model:'bad model'}]},{connections:[{...connection(),is_default:true}]},{connections:[{...connection(),status:'healthy'}]}])assert.throws(()=>workspaceAiPolicy({...raw(),...patch},workspace));
 for(const value of [null,[],{},true])assert.throws(()=>workspaceAiPolicy(value,workspace));
});
test('settings links retain exact workspace boundary and only permit known settings destinations',()=>{
 assert.equal(workspaceAiSettingsUrl(workspace),`/settings?sme=${workspace}&tab=ai&section=access`);
 assert.equal(workspaceAiSettingsUrl(workspace,'providers','api'),`/settings?sme=${workspace}&tab=ai&section=providers&model_connection=api`);
 assert.equal(workspaceAiSettingsUrl(workspace,'members'),`/settings?sme=${workspace}&tab=team&section=members`);
 for(const args of [[workspace,'https://invalid'],['../other'],[workspace,'providers','paid-fallback']])assert.throws(()=>workspaceAiSettingsUrl(...args));
});
