const assert=require('node:assert/strict');
const {open}=require('./p6_browser_harness.cjs');
let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_S21B2C_BROWSER_FIXTURE),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
  step='MCP mapping';await p.goto(f.web+'/settings');await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  const access=p.locator('section[aria-label="Quyền dùng MCP"]');
  await access.getByLabel('Kết nối cấp quyền').selectOption(f.source);
  await access.getByLabel('Nhân viên được cấp MCP').selectOption(f.actor);
  const stage=access.getByRole('button',{name:'Lưu quyền chờ kích hoạt',exact:true});assert.equal(await stage.isDisabled(),true);
  await access.getByText('Tôi xác nhận doanh nghiệp, kết nối, thành viên, nhãn hàng và thời hạn; chỉ lưu mapping.',{exact:true}).click();
  const savedResponse=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/connection-inventory/references')&&r.request().method()==='POST');
  await stage.click();const saved=await savedResponse;assert.equal(saved.status(),201);const mapped=await saved.json();
  step='explicit MCP consent';const activate=access.getByRole('button',{name:'Kích hoạt quyền này',exact:true});
  await activate.waitFor();assert.equal(await activate.isDisabled(),true);await access.getByLabel('Đồng ý kích hoạt MCP chỉ đọc').check();
  const consent=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/activate-mcp'));
  await activate.click();assert.equal((await consent).status(),201);
  await access.getByText('Đã ghi nhận đồng ý kích hoạt; quyền vẫn cần kiểm tra ở mỗi tác vụ',{exact:true}).waitFor();
  step='scope from owned Run';const calls=p.locator('section[aria-label="Chạy MCP bằng quyền đã cấp"]');
  await calls.getByLabel('MCP granted lượt xử lý ID').fill(f.run);
  await calls.getByRole('button',{name:'Tải quyền MCP của lượt xử lý',exact:true}).click();
  const chooser=calls.getByLabel('Quyền MCP đã cấp');
  await chooser.locator('option').filter({hasText:'read_report'}).waitFor({state:'attached'});
  const value=JSON.stringify([mapped.grant.id,'mcp.'+f.source.replaceAll('-','')+'.read_report']);await chooser.selectOption(value);
  const queue=calls.getByRole('button',{name:'Xếp hàng MCP chỉ đọc bằng quyền này',exact:true});assert.equal(await queue.isDisabled(),true);
  await calls.getByLabel('Đồng ý chạy MCP chỉ đọc đã cấp').check();
  const queuedResponse=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/calls')&&r.request().method()==='POST');
  await queue.click();const queued=await queuedResponse;assert.equal(queued.status(),202);const call=await queued.json();
  const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token')),headers={Authorization:'Bearer '+token};
  step='actual fixture result';let tool;
  for(let i=0;i<80;i++){
   const response=await p.request.get(f.api+`/v1/runs/${f.run}/tools`,{headers});assert.equal(response.status(),200);
   const body=await response.json();tool=body.calls.find(row=>row.id===call.id);if(tool?.status==='completed')break;await p.waitForTimeout(100);
  }
  assert.equal(tool?.status,'completed');assert.deepEqual(tool.result,{text:'Synthetic read result'});
  step='idempotent UI repeat';const repeated=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/calls')&&r.request().method()==='POST');
  await queue.click();const replay=await repeated;assert.equal(replay.status(),202);assert.equal((await replay.json()).id,call.id);
  step='reload';await p.reload();await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  await access.getByText('Đã ghi nhận đồng ý kích hoạt; quyền vẫn cần kiểm tra ở mỗi tác vụ',{exact:true}).waitFor();
  step='revoke';const revoked=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/grants/${mapped.grant.id}/revoke`));
  await access.getByRole('button',{name:'Thu hồi quyền này',exact:true}).click();assert.equal((await revoked).status(),200);
  const discovery=await p.request.get(f.api+`/v1/connectors/grants?workspace_id=${f.workspace}&run_id=${f.run}`,{headers});
  assert.equal(discovery.status(),200);assert.deepEqual((await discovery.json()).items,[]);
  step='tenant switch';await p.locator('.pao-topbar-context select').selectOption(f.second);
  await p.getByRole('button',{name:'Kết nối',exact:true}).click();await access.getByText('Chưa có kết nối MCP trong doanh nghiệp này.',{exact:true}).waitFor();
  assert.equal(await calls.getByLabel('MCP granted lượt xử lý ID').inputValue(),'');
  await p.locator('.pao-topbar-context select').selectOption(f.workspace);await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  await access.getByRole('button',{name:'Thu hồi quyền này',exact:true}).waitFor();
  step='mobile';await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,explicit_consent:true,actual_fixture_tool_result:true,idempotent_call:true,
   tenant_switch:true,revoke_disappears:true,external_server_accepted:false}));
 }finally{await h.close()}
})().catch(error=>{console.error('P6 browser failed at S21B2c '+step+' '+String(error.message).split('\n')[0].slice(0,180));process.exitCode=1});
