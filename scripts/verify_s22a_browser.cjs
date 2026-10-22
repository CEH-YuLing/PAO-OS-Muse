const assert=require('node:assert/strict'),fs=require('node:fs');
const {open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_S22A_BROWSER_FIXTURE),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
  await p.goto(f.web+'/settings');await p.getByTestId('settings-tab-ai').click();await p.getByTestId('settings-section-tab-access').click();
  const access=p.locator('section[aria-label="Quyền dùng model"]');
  async function form(){await access.getByLabel('Kết nối cấp quyền').selectOption(f.source);await access.getByLabel('Nhân viên được cấp mô hình').selectOption(f.actor);
   await access.getByText('Tôi xác nhận doanh nghiệp, kết nối, thành viên, nhãn hàng và thời hạn; chỉ lưu mapping.',{exact:true}).click()}
  step='initial consent';await form();
  const stage=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/connection-inventory/references')&&r.request().method()==='POST');
  await access.getByRole('button',{name:'Lưu quyền chờ kích hoạt',exact:true}).click();const first=await stage;assert.equal(first.status(),201);const old=await first.json();
  await access.getByLabel('Đồng ý kích hoạt mô hình suy luận AI').check();
  const activated=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/activate-model'));
  await access.getByRole('button',{name:'Kích hoạt quyền này',exact:true}).click();assert.equal((await activated).status(),201);
  const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token')),headers={Authorization:'Bearer '+token};
  const denied=await p.request.post(f.api+`/v1/model-providers/openai/test?workspace_id=${f.workspace}`,{headers});assert.equal(denied.status(),403);
  step='fixture rotation';fs.writeFileSync(f.marker,'rotate');
  for(let i=0;i<100&&!fs.existsSync(f.done);i++)await p.waitForTimeout(50);assert.equal(fs.existsSync(f.done),true);
  await p.reload();await p.getByTestId('settings-tab-ai').click();await p.getByTestId('settings-section-tab-access').click();await form();
  const oldGroup=access.locator(`[aria-label="model reference ${old.reference.id}"]`);
  const reapply=oldGroup.getByRole('button',{name:'Cấp lại bằng phiên bản mới',exact:true});assert.equal(await reapply.isDisabled(),true);
  step='explicit supersede';await access.getByLabel('Đồng ý cấp lại phiên bản mô hình').check();
  const saved=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/reapply'));
  await reapply.click();const response=await saved;assert.equal(response.status(),201);const fresh=await response.json();
  assert.equal(fresh.reference.generation,2);assert.equal(fresh.reference.supersedes_id,old.reference.id);
  const current=access.locator(`[aria-label="Quyền model ${fresh.grant.id}"]`);
  await current.getByText('Chưa kích hoạt',{exact:true}).waitFor();assert.equal(await current.getByRole('button',{name:'Kích hoạt quyền này',exact:true}).isDisabled(),true);
  step='new separate consent';await access.getByLabel('Đồng ý kích hoạt mô hình suy luận AI').check();
  const newConsent=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/activate-model'));
  await current.getByRole('button',{name:'Kích hoạt quyền này',exact:true}).click();assert.equal((await newConsent).status(),201);
  await current.getByText('Đã ghi nhận đồng ý kích hoạt; quyền vẫn cần kiểm tra ở mỗi tác vụ',{exact:true}).waitFor();
  step='tenant switch/reset';await p.locator('.pao-topbar-context select').selectOption(f.second);await p.getByTestId('settings-tab-ai').click();await p.getByTestId('settings-section-tab-access').click();
  await access.getByLabel('Kết nối cấp quyền').waitFor();assert.equal(await access.getByLabel('Đồng ý cấp lại phiên bản mô hình').isChecked(),false);
  assert.equal(await access.locator(`[aria-label="Quyền model ${fresh.grant.id}"]`).count(),0);
  await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,new_consent_required:true,native_probe_denied:true,tenant_switch:true,provider_calls:false}));
 }finally{await h.close()}
})().catch(error=>{console.error('P6 browser failed at S22a '+step+' '+String(error.message).split('\n')[0].slice(0,180));process.exitCode=1});
