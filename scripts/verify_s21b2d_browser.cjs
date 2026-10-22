const assert=require('node:assert/strict');
const {open}=require('./p6_browser_harness.cjs');
let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_S21B2D_BROWSER_FIXTURE),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
  step='mapping';await p.goto(f.web+'/settings');await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  const access=p.locator('section[aria-label="Quyền dùng Meta Ads"]');
  await access.getByLabel('Kết nối cấp quyền').selectOption(f.source);
  await access.getByLabel('Tài khoản cấp Meta Ads').selectOption('act_123');
  await access.getByLabel('Nhân viên được cấp Meta Ads').selectOption(f.actor);
  await access.getByText('Tôi xác nhận doanh nghiệp, kết nối, thành viên, nhãn hàng và thời hạn; chỉ lưu mapping.',{exact:true}).click();
  const saved=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/connection-inventory/references')&&r.request().method()==='POST');
  await access.getByRole('button',{name:'Lưu quyền chờ kích hoạt',exact:true}).click();const response=await saved;assert.equal(response.status(),201);const mapped=await response.json();
  step='separate read consent';const activate=access.getByRole('button',{name:'Kích hoạt quyền này',exact:true});await activate.waitFor();assert.equal(await activate.isDisabled(),true);
  await access.getByLabel('Đồng ý kích hoạt Meta Ads chỉ đọc').check();
  const consent=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/activate-ads'));await activate.click();assert.equal((await consent).status(),201);
  await access.getByText('Đã ghi nhận đồng ý kích hoạt; quyền vẫn cần kiểm tra ở mỗi tác vụ',{exact:true}).waitFor();
  step='selected account sync';const reads=p.locator('section[aria-label="Đọc Ads bằng quyền đã cấp"]');
  await reads.getByRole('button',{name:'Tải quyền đọc Ads',exact:true}).click();
  await reads.getByLabel('Quyền Ads đã cấp').selectOption(mapped.grant.id);
  await reads.getByLabel('Ads từ ngày').fill(f.day);await reads.getByLabel('Ads đến ngày').fill(f.day);
  const sync=reads.getByRole('button',{name:'Xếp hàng đồng bộ Ads chỉ đọc',exact:true});assert.equal(await sync.isDisabled(),true);
  await reads.getByLabel('Đồng ý đồng bộ Ads chỉ đọc').check();
  const queued=p.waitForResponse(r=>new URL(r.url()).pathname==='/v1/integrations/meta/sync'&&r.request().method()==='POST');
  await sync.click();const job=await queued;assert.equal(job.status(),202,'Ads sync admission HTTP '+job.status());const jobId=(await job.json()).id;
  step='actual worker result';const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token'));
  for(let i=0;i<80;i++){
   const jobs=await p.request.get(f.api+`/v1/integrations/meta/jobs?workspace_id=${f.workspace}`,{headers:{Authorization:'Bearer '+token}});
   assert.equal(jobs.status(),200,'Ads jobs metadata HTTP '+jobs.status());if((await jobs.json()).find(j=>j.id===jobId)?.status==='completed')break;
   if(i===79)assert.fail('Fixture sync did not complete');await p.waitForTimeout(100);
  }
  const repeated=p.waitForResponse(r=>new URL(r.url()).pathname==='/v1/integrations/meta/sync'&&r.request().method()==='POST');
  await sync.click();const replay=await repeated;assert.equal(replay.status(),202,'Ads replay admission HTTP '+replay.status());assert.equal((await replay.json()).id,jobId);
  await reads.getByRole('button',{name:'Đọc báo cáo đã đồng bộ',exact:true}).click();
  await reads.getByLabel('Báo cáo Ads được cấp').getByText('chi phí chưa có dữ liệu',{exact:false}).waitFor();
  step='revoke';const revoked=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/grants/${mapped.grant.id}/revoke`));
  await access.getByRole('button',{name:'Thu hồi quyền này',exact:true}).click();assert.equal((await revoked).status(),200);
  await reads.getByRole('button',{name:'Tải quyền đọc Ads',exact:true}).click();await reads.getByText('Không có quyền Ads hợp lệ trong phạm vi này.',{exact:true}).waitFor();
  step='switch/reload/mobile';await p.locator('.pao-topbar-context select').selectOption(f.second);await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  await access.getByText('Chưa có kết nối Meta Ads trong doanh nghiệp này.',{exact:true}).waitFor();assert.equal(await reads.getByLabel('Quyền Ads đã cấp').inputValue(),'');
  await p.reload();await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  await access.getByText('Chưa có kết nối Meta Ads trong doanh nghiệp này.',{exact:true}).waitFor();
  await reads.getByLabel('Quyền Ads đã cấp').waitFor();await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,actual_fixture_sync:true,tenant_switch:true,read_only:true,live_ads_accepted:false}));
 }finally{await h.close()}
})().catch(error=>{console.error('P6 browser failed at S21B2d '+step+' '+String(error.message).split('\n')[0].slice(0,180));process.exitCode=1});
