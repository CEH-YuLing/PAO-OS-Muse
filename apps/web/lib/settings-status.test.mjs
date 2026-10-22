import test from 'node:test';
import assert from 'node:assert/strict';
import {settingsSources,settingsPath,collectSettingsStatus,validateSettingsStatus,evidenceValue,connectionEvidence} from './settings-status.mjs';
const rows={
 meta:{configured:true,status:'connected',scopes:[]},google:{configured:true,status:'disconnected',scopes:[]},
 telegram:{enabled:true,configured:true,mode:'poll',allowed_peers:1,delivery_issues:[]},
 voice:{enabled:true,stt_ready:true,tts_ready:true,stt_device:'cpu',stt_compute_type:'int8',tts_provider:'fixture',max_seconds:60},
 automation:{enabled:true,namespace:'default',task_queue:'fixture'},
 write:{enabled:false,dry_run_default:true,max_budget_change_pct:15},autopilot:{global_enabled:false,meta_enabled:false,phase:13,default_mode:'observer'},
 platform:{features:[],integrations:[],model_providers:[],javis_compatibility:{}},providers:[],
};
const read=async path=>rows[settingsSources.find(([, ,base])=>path.startsWith(base))[0]];
test('all nine GET paths preserve SME vs host ownership without discovery requests',async()=>{
 const paths=[];const result=await collectSettingsStatus('B',async path=>{paths.push(path);return read(path)});
 assert.equal(result.responding,9);assert.deepEqual(result.failed,[]);
 assert.deepEqual(paths.filter(x=>x.includes('workspace_id=')),settingsSources.filter(x=>x[3]==='sme').map(x=>x[2]+'?workspace_id=B'));
 assert.ok(paths.every(x=>!x.includes('/test')&&!x.includes('/models?')&&!x.includes('/oauth')));
 assert.throws(()=>settingsPath('/v1/test','sme',''),/settings_scope_missing/);
});
test('failed refresh cannot retain an older successful record, error payload is never echoed',async()=>{
 const first=await collectSettingsStatus('A',read);assert.equal(first.data.meta.status,'connected');
 const next=await collectSettingsStatus('A',async path=>{if(path.includes('/meta/'))throw new Error('private-marker');return read(path)});
 assert.equal(next.data.meta,undefined);assert.equal(next.responding,8);assert.deepEqual(next.failed,['Meta Ads']);assert.ok(!JSON.stringify(next).includes('private-marker'));
});
for(const [key] of settingsSources)test(`${key}: malformed successful response remains unknown`,()=>{assert.throws(()=>validateSettingsStatus(key,{}),/settings_status_invalid/)});
test('malformed truthy strings never become safe or enabled',()=>{
 assert.throws(()=>validateSettingsStatus('write',{...rows.write,enabled:'false'}));
 assert.throws(()=>validateSettingsStatus('telegram',{...rows.telegram,configured:'yes'}));
 assert.throws(()=>validateSettingsStatus('meta',{...rows.meta,scopes:null}));
});
test('saved OAuth is not health or acceptance; host Telegram is not SME connection',()=>{
 assert.deepEqual(connectionEvidence('meta',rows.meta),{configured:true,connected:true,healthy:null,accepted:null});
 assert.deepEqual(connectionEvidence('telegram',rows.telegram),{configured:true,connected:null,healthy:null,accepted:null});
 assert.deepEqual(connectionEvidence('meta',null),{configured:null,connected:null,healthy:null,accepted:null});
 assert.equal(evidenceValue(null),'Chưa xác minh');assert.equal(evidenceValue(false),'Chưa');
});
test('provider listing requires usable display fields, not partial success records',()=>{
 const row={provider:'openai',name:'Fixture',status:'connected',configured:true,is_default:false,model:'fixture',model_count:2,key_hint:null};
 assert.deepEqual(validateSettingsStatus('providers',[row]),[row]);
 assert.throws(()=>validateSettingsStatus('providers',[{...row,model_count:'2'}]));
 assert.throws(()=>validateSettingsStatus('providers',[{...row,key_hint:undefined}]));
});
