// Real local HTTP/DB draft/revoke UI, deliberately no discovery or external calls.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',dialog=>dialog.accept());
  await page.route('**/v1/**',async route=>{const u=new URL(route.request().url());try{await route.fulfill({response:await route.fetch({url:api+u.pathname+u.search})})}catch{await route.abort().catch(()=>{})}});
  await page.goto(process.env.PAO_FRONTEND_URL);await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');
  await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));await page.goto(new URL('/settings',process.env.PAO_FRONTEND_URL).href);
  await page.getByRole('button',{name:'Kết nối',exact:true}).click();
  const panel=page.getByRole('region',{name:'Kết nối công cụ chỉ đọc'});await panel.waitFor();
  await panel.getByLabel('Địa chỉ HTTPS máy chủ MCP',{exact:true}).fill('https://fixture.example/mcp');
  await panel.getByLabel('Khóa truy cập MCP',{exact:true}).fill('synthetic-p5-browser-marker');
  await panel.getByRole('checkbox').first().check();await panel.getByRole('button',{name:'Tạo kết nối bản nháp',exact:true}).click();
  await Promise.race([panel.getByLabel('Kết quả thao tác MCP').filter({hasText:'bản nháp đã tạo'}).waitFor(),panel.getByRole('alert').waitFor().then(async()=>{throw new Error(await panel.getByRole('alert').innerText())})]);
  assert.equal(await panel.getByLabel('Khóa truy cập MCP').inputValue(),'');
  const headers={Authorization:`Bearer ${await page.evaluate(()=>sessionStorage.getItem('pao.access_token'))}`};
  const me=await(await page.request.get(api+'/v1/me',{headers})).json(),wid=me.workspaces[0].id;
  const read=async()=>await(await page.request.get(api+'/v1/connectors/connections?workspace_id='+wid,{headers})).json();
  let rows=await read();assert.equal(rows.length,1);assert.equal(rows[0].status,'draft');assert.equal(rows[0].secret_present,true);assert.deepEqual(rows[0].tools,[]);assert.deepEqual(rows[0].permissions,[]);
  assert.equal(await panel.getByRole('button',{name:'Ngắt kết nối và xóa khóa',exact:true}).isDisabled(),true);
  await panel.getByLabel('Đồng ý ngắt MCP',{exact:true}).check();
  await panel.getByRole('button',{name:'Ngắt kết nối và xóa khóa',exact:true}).click();
  await panel.getByLabel('Kết quả thao tác MCP').filter({hasText:'Đã ngắt bản lưu PAO'}).waitFor();
  rows=await read();assert.equal(rows[0].status,'revoked');assert.equal(rows[0].secret_present,false);
  await panel.getByRole('button',{name:'Xem nhật ký cấu hình',exact:true}).click();await panel.getByLabel('Kết quả thao tác MCP').filter({hasText:'revoked'}).waitFor();
  assert(!await panel.innerText().then(t=>t.includes('synthetic-p5-browser-marker')));
  assert.deepEqual(errors,[]);await page.screenshot({path:'.runtime/p5-live-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_http_db_ui:true,draft_revoke_purge_audit:true,external_provider_calls:0,discovery_calls:0,screenshot:'.runtime/p5-live-ui.png'}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
