const assert=require('node:assert/strict');
const {open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_S22B2B_METADATA_BROWSER_FIXTURE),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
  await p.goto(f.web+'/settings');await p.getByRole('heading',{name:'Settings & Kết nối',exact:true}).waitFor();
  await p.getByTestId('settings-tab-ai').click();await p.getByTestId('settings-section-tab-access').click();
  const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token')),headers={Authorization:'Bearer '+token};
  const resource=wid=>f.api+`/v1/workspaces/${wid}/resources/metadata`;
  step='metadata policy';const policy={expected_version:0,daily_metadata_requests:3,concurrent_metadata:1};
  const saved=await p.request.put(resource(f.workspace),{headers,data:policy});assert.equal(saved.status(),200);
  const stale=await p.request.put(resource(f.workspace),{headers,data:policy});assert.equal(stale.status(),409);
  assert.equal(stale.headers()['cache-control'],'no-store');
  const panel=()=>p.getByLabel('Cài đặt mô hình đám mây',{exact:true});
  const article=()=>panel().getByLabel('mô hình openai',{exact:true});
  const ack=()=>article().getByLabel('Đồng ý thông tin mô tả OpenAI',{exact:true}).check();
  step='fixture connect';await article().getByLabel('Khóa API OpenAI',{exact:true}).fill(f.fixtureKey);await ack();
  const connected=p.waitForResponse(r=>new URL(r.url()).pathname==='/v1/model-providers/openai/connect'&&r.request().method()==='POST');
  await article().getByRole('button',{name:'Lưu khóa và tải danh mục',exact:true}).click();const response=await connected;
  assert.equal(response.status(),200);assert.equal(response.headers()['cache-control'],'no-store');
  assert.equal((await response.text()).includes(f.fixtureKey),false);
  await article().getByRole('button',{name:'Đổi khóa và tải danh mục',exact:true}).waitFor();
  assert.equal(await article().locator('input[type=password]').inputValue(),'');
  step='catalogue';const listed=p.waitForResponse(r=>new URL(r.url()).pathname==='/v1/model-providers/openai/models');
  await ack();await article().getByRole('button',{name:'Tải danh mục mô hình',exact:true}).click();assert.equal((await listed).status(),200);
  await panel().getByRole('status').waitFor();
  step='select model';const selected=p.waitForResponse(r=>new URL(r.url()).pathname==='/v1/model-providers/openai/model'&&r.request().method()==='PUT');
  await article().getByLabel('Mô hình lựa chọn OpenAI',{exact:true}).selectOption('fixture-new');
  await ack();await article().getByRole('button',{name:'Lưu mô hình đã chọn',exact:true}).click();assert.equal((await selected).status(),200);
  // reload() remounts CloudModels: its old success toast is not durable. Verify
  // the actual selected model rendered from the saved source, not that toast.
  await panel().getByRole('status').waitFor();
  assert.equal(await article().getByLabel('Mô hình lựa chọn OpenAI',{exact:true}).inputValue(),'fixture-new');
  step='reload';await p.reload();await p.getByTestId('settings-tab-ai').click();await p.getByTestId('settings-section-tab-access').click();
  await article().locator('select').waitFor();assert.equal(await article().locator('select').inputValue(),'fixture-new');
  step='quota denial';const denied=p.waitForResponse(r=>new URL(r.url()).pathname==='/v1/model-providers/openai/models');
  await ack();await article().getByRole('button',{name:'Tải danh mục mô hình',exact:true}).click();const capped=await denied;
  assert.equal(capped.status(),429);assert.equal((await capped.json()).detail,'tenant_metadata_daily_exhausted');
  await panel().getByRole('alert').filter({hasText:'Đã hết hạn mức ngày UTC'}).waitFor();
  assert.equal(await article().count(),0);
  const usage=await p.request.get(resource(f.workspace),{headers});const data=await usage.json();
  assert.equal(data.usage.daily_requests,3);assert.equal(data.usage.active_requests,0);
  assert.equal(data.usage.provider_remaining_quota,null);assert.equal(data.grants_authorized,false);
  step='tenant switch';await p.locator('.pao-topbar-context select').selectOption(f.second);
  await p.getByTestId('settings-tab-ai').click();await p.getByTestId('settings-section-tab-access').click();
  await article().getByRole('button',{name:'Lưu khóa và tải danh mục',exact:true}).waitFor();
  assert.equal(await article().getByLabel('Khóa API OpenAI',{exact:true}).inputValue(),'');
  assert.equal(await article().locator('select').count(),0);
  const other=await p.request.get(resource(f.second),{headers});const independent=await other.json();
  assert.equal(independent.metadata_policy.version,0);assert.equal(independent.usage.daily_requests,0);
  await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,fixture_connect:true,model_selection:true,reload:true,tenant_switch:true,
   native_metadata_hardening:true,metadata_quota:true,quota_form_ui:false,provider_calls:false}));
 }finally{await h.close()}
})().catch(e=>{console.error('P6 browser failed at S22b2b metadata '+step+' '+String(e.message).split('\n')[0].slice(0,180));process.exitCode=1});
