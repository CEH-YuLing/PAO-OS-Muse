// Real HTTP settings write into an isolated API's temporary .env; fake secret only.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/v1/**',async route=>{const u=new URL(route.request().url());await route.fulfill({response:await route.fetch({url:api+u.pathname+u.search})})});
  await page.goto(process.env.PAO_FRONTEND_URL);await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');
  await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
  await page.goto(new URL('/settings',process.env.PAO_FRONTEND_URL).href);
  await page.getByRole('button',{name:'Kết nối',exact:true}).click();
  const panel=page.getByRole('region',{name:'Cấu hình Meta App'});await panel.waitFor();
  const submit=panel.getByRole('button',{name:'Lưu Meta App chỉ đọc',exact:true});await panel.getByLabel('Meta App ID',{exact:true}).waitFor();
  assert.equal(await panel.getByLabel('Meta App ID',{exact:true}).inputValue(),'123');
  assert(await submit.isDisabled());assert.equal(await panel.getByLabel('Meta App Secret',{exact:true}).getAttribute('type'),'password');
  await panel.getByLabel('Meta App Secret',{exact:true}).fill('synthetic-browser-meta-secret');
  await panel.getByRole('checkbox').check();await submit.click();
  await panel.getByRole('status').filter({hasText:'Đã lưu trên máy chủ'}).waitFor();
  assert.equal(await panel.getByLabel('Meta App Secret',{exact:true}).inputValue(),'');assert(await submit.isDisabled());
  const headers={Authorization:`Bearer ${await page.evaluate(()=>sessionStorage.getItem('pao.access_token'))}`};
  const me=await(await page.request.get(api+'/v1/me',{headers})).json();const query='?workspace_id='+me.workspaces[0].id;
  const response=await page.request.get(api+'/v1/integrations/meta/app-config'+query,{headers});
  assert.equal(response.status(),200);const state=await response.json();assert(state.secret_present&&state.restart_required);
  assert(!state.write_enabled&&!state.autopilot_enabled);assert(!JSON.stringify(state).includes('synthetic-browser-meta-secret'));
  assert.equal((await page.request.post(api+'/v1/integrations/meta/oauth/start'+query,{headers})).status(),409);
  await panel.getByRole('button',{name:'Tải lại cấu hình',exact:true}).click();
  await panel.getByLabel('Meta App Secret',{exact:true}).waitFor();assert.equal(await panel.getByLabel('Meta App Secret',{exact:true}).inputValue(),'');
  assert(!await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage})).then(v=>v.includes('synthetic-browser-meta-secret')));
  assert.deepEqual(errors,[]);await page.screenshot({path:'.runtime/meta-app-settings-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_http_temp_config:true,masked_secret:true,no_secret_response_or_storage:true,restart_gate:true,provider_calls:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
