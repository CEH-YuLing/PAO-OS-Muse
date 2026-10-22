const assert=require('node:assert/strict');
const {open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_S22B2A_BROWSER_FIXTURE),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
  await p.goto(f.web+'/settings');await p.getByRole('heading',{name:'Settings & Kết nối',exact:true}).waitFor();
  const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token')),headers={Authorization:'Bearer '+token};
  const route=wid=>f.api+`/v1/workspaces/${wid}/resources/reads`;
  step='metadata';const initial=await p.request.get(route(f.workspace),{headers});assert.equal(initial.status(),200);
  assert.equal(initial.headers()['cache-control'],'no-store');assert.equal((await initial.json()).read_policy.version,0);
  const body={expected_version:0,daily_read_jobs:100,queued_read_jobs:5,concurrent_reads:1};
  step='CAS';const saved=await p.request.put(route(f.workspace),{headers,data:body});assert.equal(saved.status(),200);
  assert.equal((await saved.json()).read_policy.version,1);
  const stale=await p.request.put(route(f.workspace),{headers,data:body});assert.equal(stale.status(),409);
  const marker='fixture-redaction-not-a-secret';const invalid=await p.request.put(route(f.workspace),{headers,data:{secret:marker}});
  assert.equal(invalid.status(),422);assert.equal((await invalid.text()).includes(marker),false);
  step='tenant switch';await p.locator('.pao-topbar-context select').selectOption(f.second);
  await p.getByRole('heading',{name:'Settings & Kết nối',exact:true}).waitFor();
  const second=await p.request.get(route(f.second),{headers});assert.equal(second.status(),200);
  const data=await second.json();assert.equal(data.workspace_id,f.second);assert.equal(data.read_policy.version,0);
  assert.equal(data.provider_remaining_quota,null);assert.equal(data.grants_authorized,false);
  await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,quota_metadata:true,quota_ui:false,tenant_switch:true,provider_calls:false}));
 }finally{await h.close()}
})().catch(e=>{console.error('P6 browser failed at S22b2a '+step+' '+String(e.message).split('\n')[0].slice(0,180));process.exitCode=1});
