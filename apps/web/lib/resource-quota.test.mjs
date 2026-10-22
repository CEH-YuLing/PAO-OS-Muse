import test from 'node:test';
import assert from 'node:assert/strict';
import {resourcePools,resourceDraft,resourcePayload,validateResourceSnapshot,resourceErrorHelp} from './resource-quota.mjs';
const fixture=pool=>{
  const spec=resourcePools[pool],limits=Object.fromEntries(Object.entries(spec.fields).map(([key,[,max]])=>[key,max]));
  return {workspace_id:'A',[spec.policy]:{version:0,...limits},host_ceilings:limits,usage:Object.fromEntries(Object.keys(spec.usage).map(key=>[key,0])),grants_authorized:false};
};
for(const pool of Object.keys(resourcePools)){
  test(`${pool}: exact CAS version and only numeric limits, no credentials`,()=>{
    const data=validateResourceSnapshot(pool,fixture(pool),'A'),draft=resourceDraft(pool,data),body=resourcePayload(pool,data,draft);
    assert.equal(body.expected_version,0);assert.deepEqual(Object.keys(body).sort(),['expected_version',...Object.keys(resourcePools[pool].fields)].sort());
    data[resourcePools[pool].policy].version=7;assert.equal(resourcePayload(pool,data,draft).expected_version,7);
  });
  test(`${pool}: reject unsafe input without coercion`,()=>{
    const data=fixture(pool),key=Object.keys(resourcePools[pool].fields)[0];
    for(const value of ['', '0', '-1', '1.2','1e3',' 3','Infinity','9007199254740993',String(data.host_ceilings[key]+1),true,null]){
      assert.throws(()=>resourcePayload(pool,data,{...resourceDraft(pool,data),[key]:value}),/quota_form_invalid/);
    }
  });
  test(`${pool}: missing or unknown accounting must not become zero`,()=>{
    const key=Object.keys(resourcePools[pool].usage)[0];
    for(const value of [null,undefined,-1,'0',NaN]){const data=fixture(pool);data.usage[key]=value;assert.throws(()=>validateResourceSnapshot(pool,data,'A'),/quota_snapshot_invalid/)}
    const data=fixture(pool);data.grants_authorized=true;assert.throws(()=>validateResourceSnapshot(pool,data,'A'));
    if(pool!=='models')assert.throws(()=>validateResourceSnapshot(pool,fixture(pool),'B'));
  });
}
test('version conflicts and quota denials give explicit manual recovery, never auto retry',()=>{
  for(const code of ['tenant_resource_policy_version_conflict','tenant_read_policy_version_conflict','tenant_metadata_policy_version_conflict'])assert.match(resourceErrorHelp(code),/phiên khác/);
  for(const code of ['tenant_model_daily_calls_exhausted','tenant_model_daily_tokens_exhausted','tenant_read_daily_jobs_exhausted','tenant_metadata_daily_exhausted'])assert.match(resourceErrorHelp(code),/UTC/);
  assert.match(resourceErrorHelp('tenant_read_queue_exhausted'),/Hàng đợi/);
  assert.match(resourceErrorHelp('TypeError: failed to fetch'),/có thể máy chủ đã nhận/);
});
