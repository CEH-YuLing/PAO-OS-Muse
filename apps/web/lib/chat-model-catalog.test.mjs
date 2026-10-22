import test from 'node:test';
import assert from 'node:assert/strict';
import {chatModelTabs,chatModelProviders,chatModelKey,chatProviderName,chatModelSummary,chatModelOptions,filterChatModels} from './chat-model-catalog.mjs';
const engine=(provider='codex_cli',resource='first')=>({provider,installation_resource_id:resource,models:['model-a','model-b'],local:false,error:null,
 model_details:[{model:'model-a',display_name:'Model A',reasoning_efforts:['low','high'],default_effort:'low'},{model:'model-b',display_name:'Model B',reasoning_efforts:[],default_effort:null}]});

test('two connection tabs preserve Client first and four requested provider cards each',()=>{
 assert.deepEqual(chatModelTabs.map(row=>row.id),['client','api']);
 assert.deepEqual(chatModelProviders.filter(row=>row.tab==='client').map(row=>row.name),['Codex','Claude','Antigravity','Muse']);
 assert.deepEqual(chatModelProviders.filter(row=>row.tab==='api').map(row=>row.name),['OpenAI','Claude','Google Gemini','OpenRouter']);
 assert.notEqual(chatModelProviders.find(row=>row.id==='muse').planned,true);
});
test('catalogue never invents models for an unconnected provider',()=>{
 const options=chatModelOptions({scope:'installation',engines:[engine()]},null,null);
 assert.deepEqual(options.map(row=>row.selection.model),['model-a','model-b']);
 for(const id of ['claude_code','antigravity','muse','openai'])assert.equal(options.filter(row=>row.selection.provider===id).length,0);
 assert.deepEqual(chatModelOptions(null,null,null),[]);
});
test('Muse models and effort reuse the installation resource without personal grants',()=>{
 const row=engine('muse','muse-resource'),options=chatModelOptions({scope:'installation',engines:[row]},null,null);
 assert.equal(options.length,2);assert.equal(options[0].available,true);
 assert.equal(options[0].selection.installation_resource_id,'muse-resource');
 assert.equal(options[0].selection.grant_id,undefined);
 assert.deepEqual(options[0].detail.reasoning_efforts,['low','high']);
 assert.equal(chatModelSummary(options[0].selection),'Muse — model-a');
});
test('provider names distinguish subscription clients from API, retaining raw model ids',()=>{
 assert.equal(chatModelSummary({provider:'codex_cli',model:'gpt-example'}),'Codex — gpt-example');
 assert.equal(chatModelSummary({provider:'antigravity',model:'gemini-example'}),'Antigravity — gemini-example');
 assert.equal(chatModelSummary({provider:'openai',model:'gpt-example'}),'API-OpenAI — gpt-example');
 assert.equal(chatModelSummary({provider:'anthropic',model:'claude-example'}),'API-Claude — claude-example');
 assert.equal(chatProviderName('claude_code'),'Claude');assert.equal(chatProviderName('muse'),'Muse');
 assert.equal(chatProviderName('ollama'),'Ollama');assert.equal(chatProviderName('future_source'),'future_source');
 assert.equal(chatModelSummary(null),'Chưa chọn mô hình');
});
test('resource identity is preserved when different sources expose the same model',()=>{
 const options=chatModelOptions({engines:[engine('openai','first'),engine('openai','second')]},null,null);
 assert.equal(options.length,4);assert.equal(new Set(options.map(row=>row.key)).size,4);
 assert.deepEqual(options.map(row=>JSON.parse(row.key)[5]),['first','first','second','second']);
});
test('effort metadata belongs to exact selected resource, not merely vendor/model',()=>{
 const first=engine('openai','first'),second=engine('openai','second');
 second.model_details[0].reasoning_efforts=['medium'];second.model_details[0].default_effort='medium';
 const options=chatModelOptions({engines:[first,second]},null,null);
 assert.deepEqual(options.find(row=>row.selection.installation_resource_id==='first').detail.reasoning_efforts,['low','high']);
 assert.deepEqual(options.find(row=>row.selection.installation_resource_id==='second').detail.reasoning_efforts,['medium']);
 assert.deepEqual(options.find(row=>row.selection.model==='model-b').detail.reasoning_efforts,[]);
});
test('unavailable current selection remains visible but cannot be applied as an available source',()=>{
 const current={provider:'codex_cli',model:'old-model',installation_resource_id:'removed',reasoning_effort:'high'};
 const options=chatModelOptions({engines:[{...engine(),error:'unavailable'}]},null,current);
 assert.equal(options.length,1);assert.equal(options[0].key,chatModelKey(current));assert.equal(options[0].available,false);
 assert.match(options[0].origin,/kiểm tra lại/);
});
test('known current selection is not duplicated and catalogue errors never become options',()=>{
 const source=engine(),current={provider:'codex_cli',model:'model-a',installation_resource_id:'first',reasoning_effort:'high'};
 const options=chatModelOptions({engines:[source,{...engine('openai'),error:'failed'}]},null,current);
 assert.equal(options.length,2);assert.ok(options.every(row=>row.available));
 assert.equal(options.filter(row=>row.key===chatModelKey(current)).length,1);
});
test('legacy personal, enterprise, grant and local identities remain distinct',()=>{
 const base={provider:'codex_cli',model:'model-a'};
 const variants=[base,{...base,personal_cli_source_id:'personal'},{...base,enterprise_source_id:'business'},
  {...base,grant_id:'grant'},{...base,enterprise_source_id:'business',grant_id:'grant'},
  {...base,installation_resource_id:'installation'}];
 assert.equal(new Set(variants.map(chatModelKey)).size,6);
 const options=chatModelOptions({engines:[{provider:'ollama',models:['local-one'],local:true,error:null}]},{items:[{provider:'openai',model:'api-one',grant_id:'grant'}]},null);
 assert.equal(options.length,2);assert.equal(options[0].origin,'Trên máy');assert.equal(options[1].selection.grant_id,'grant');
 assert.equal(chatModelOptions({scope:'installation',engines:[]},{items:[{provider:'openai',model:'api-one',grant_id:'grant'}]},null).length,0);
});
test('search filters by display name, exact model id and provider without changing selection',()=>{
 const options=chatModelOptions({engines:[engine(),engine('openai','api')]},null,null);
 assert.equal(filterChatModels(options,'codex').length,2);
 assert.equal(filterChatModels(options,' API-OPENAI ').length,2);
 assert.equal(filterChatModels(options,'Model A').length,2);
 assert.equal(filterChatModels(options,'model-b').length,2);
 assert.equal(filterChatModels(options,'missing').length,0);
 assert.equal(filterChatModels(options,'').length,4);
});
test('presentation does not mutate catalogue or current selection',()=>{
 const input={scope:'installation',engines:[engine()]},current={provider:'codex_cli',model:'model-a',installation_resource_id:'first'};
 const before=structuredClone({input,current});chatModelOptions(input,null,current);
 assert.deepEqual({input,current},before);
});

test('all personal Codex models preserve the same source without becoming installation resources',()=>{
 const models=['first-codex','second-codex','third-codex'];
 const options=chatModelOptions({scope:'installation',engines:[{provider:'codex_cli',models,local:false,error:null,
  personal_cli_source_id:'personal-source',model_details:models.map(model=>({model,display_name:'Tên '+model,reasoning_efforts:[],default_effort:null}))}]},null,null);
 assert.deepEqual(options.map(row=>row.selection.model),models);
 assert.ok(options.every(row=>row.available&&row.selection.personal_cli_source_id==='personal-source'&&!row.selection.installation_resource_id));
 assert.equal(new Set(options.map(row=>row.key)).size,3);
 assert.equal(filterChatModels(options,'second-codex')[0].label,'Tên second-codex');
});

test('installation API and existing personal Codex coexist without legacy grants or invented models',()=>{
 const input={scope:'installation',engines:[engine('openai','api'),
  {provider:'codex_cli',models:['personal-model'],local:false,error:null,personal_cli_source_id:'own-source'}]};
 const options=chatModelOptions(input,{items:[{provider:'codex_cli',model:'forbidden',grant_id:'old-grant'}]},null);
 const codex=options.filter(row=>row.selection.provider==='codex_cli');
 assert.equal(codex.length,1);assert.ok(codex[0].available);
 assert.equal(codex[0].selection.personal_cli_source_id,'own-source');
 assert.equal(codex[0].selection.model,'personal-model');
 assert.equal(codex[0].selection.installation_resource_id,undefined);
 assert.ok(options.some(row=>row.selection.installation_resource_id==='api'));
 assert.ok(options.every(row=>row.selection.model!=='forbidden'));
});
