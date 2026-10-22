import test from 'node:test';
import assert from 'node:assert/strict';
import {modelConnectionTabs,clientProviders,readModelConnection,cliProfilesPath,cliProfileRows,cliProfileLabel} from './model-provider-tabs.mjs';
import {settingsNavigationUrl,readSettingsNavigation} from './settings-navigation.mjs';
const workspace='11111111-1111-4111-8111-111111111111',actor='22222222-2222-4222-8222-222222222222',other='33333333-3333-4333-8333-333333333333';
const row=()=>({id:other,workspace_id:workspace,owner_id:actor,provider:'codex_cli',model:'fixture-model',version:2,status:'pending',authentication_ready:false,profile_operation_pending:false,credentials_stored_in_PAO:false,scope:'local_personal_self_only',tools_enabled:false,activation_required:true});
const parse=items=>cliProfileRows({items,external_calls:false},workspace,actor);
test('Client is first/default; API is an explicit secondary connection method',()=>{
 assert.deepEqual(modelConnectionTabs.map(x=>x.id),['client','api']);
 assert.deepEqual(clientProviders.map(x=>x.name),['Codex','Claude Code','Antigravity','Muse']);
 for(const query of ['', '?model_connection=client','?model_connection=constructor','?model_connection=https://external.invalid','?model_connection=API'])assert.equal(readModelConnection(query),'client');
 assert.equal(readModelConnection('?tab=ai&model_connection=api'),'api');
});
test('model deep links preserve SME, brand and hash without changing legacy navigation shape',()=>{
 const url=settingsNavigationUrl('http://localhost/settings?sme='+workspace+'&brand='+other+'#help',{tab:'ai',platform:'meta',section:'providers',modelConnection:'api'});
 assert.equal(url,'/settings?sme='+workspace+'&brand='+other+'&tab=ai&section=providers&model_connection=api#help');
 assert.deepEqual(readSettingsNavigation(new URL(url,'http://localhost').search),{tab:'ai',platform:'meta'});
 for(const selection of [{tab:'team',section:'members'},{tab:'ai',section:'voice'},{tab:'integrations',section:'',platform:'meta'}])assert.ok(!settingsNavigationUrl('http://localhost/settings?model_connection=api', {...selection,modelConnection:'api'}).includes('model_connection'));
 assert.equal(settingsNavigationUrl('http://localhost/settings',{tab:'ai',platform:'meta'}),'/settings?tab=ai');
});
test('CLI metadata path only accepts a workspace UUID',()=>{
 assert.equal(cliProfilesPath(workspace),'/v1/workspaces/'+workspace+'/cli-connections');
 for(const value of ['','../other','workspace?actor=other',null,undefined])assert.throws(()=>cliProfilesPath(value));
});
test('saved CLI metadata is minimal, private and never retained as raw response',()=>{
 const value={...row(),profile_id:'not-retained',device_id:'not-retained',setup_help:'not-retained',unknown:'not-retained'};
 assert.deepEqual(parse([value]),[{id:other,model:'fixture-model',version:2,status:'pending',authentication_ready:false,profile_operation_pending:false}]);
 assert.deepEqual(parse([]),[]);
 assert.equal(cliProfileLabel(parse([value])[0]),'Chờ đăng nhập Codex');
 assert.equal(cliProfileLabel({...value,status:'connected',authentication_ready:true}),'Đã ghi nhận đăng nhập');
 assert.equal(cliProfileLabel({...value,profile_operation_pending:true}),'Đang chuẩn bị hồ sơ');
 assert.equal(cliProfileLabel({...value,status:'disconnected'}),'Đã ngắt trong PAO');
 assert.equal(cliProfileLabel({...value,status:'error'}),'Cần kiểm tra đăng nhập');
});
test('CLI metadata rejects foreign scope, duplicate IDs and inconsistent authority/status fields',()=>{
 for(const patch of [{workspace_id:other},{owner_id:other},{provider:'claude_code'},{version:0},{version:1.5},{status:'healthy'},{status:'pending',authentication_ready:true},{tools_enabled:true},{activation_required:false},{credentials_stored_in_PAO:true},{scope:'shared'},{model:''},{model:'a'.repeat(121)},{profile_operation_pending:null},{id:'../../'}])assert.throws(()=>parse([{...row(),...patch}]));
 assert.throws(()=>parse([row(),row()]));
 for(const value of [null,{},[],{items:[],external_calls:true},{items:null,external_calls:false},{items:Array(101).fill(row()),external_calls:false}])assert.throws(()=>cliProfileRows(value,workspace,actor));
 assert.throws(()=>cliProfileRows({items:[],external_calls:false},'foreign',actor));
});
