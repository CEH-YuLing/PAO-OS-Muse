// Real test API/DB completion via existing Tasks UI, no mocks/provider calls.
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
  const headers={Authorization:`Bearer ${await page.evaluate(()=>sessionStorage.getItem('pao.access_token'))}`};
  const me=await(await page.request.get(api+'/v1/me',{headers})).json(),wid=me.workspaces[0].id;
  const create=async(status,title)=>{const r=await page.request.post(api+'/v1/tasks',{headers,data:{workspace_id:wid,title,status,success_criteria:['Synthetic criteria'],evidence:[{text:'Synthetic M4 browser evidence'}]}});assert.equal(r.status(),201);return r.json()};
  const task=await create('ready','Synthetic M4 browser');await create('completed','Synthetic M4 create completed');
  await page.goto(new URL('/tasks',process.env.PAO_FRONTEND_URL).href);
  await page.getByRole('heading',{name:'Synthetic M4 browser',exact:true}).waitFor();
  for(const status of ['Running','Approval','Completed'])await page.getByRole('button',{name:'Chuyển Synthetic M4 browser sang '+status,exact:true}).click();
  const done=page.locator('.tasks-column').filter({has:page.locator('header strong',{hasText:'Completed'})});
  await done.getByRole('heading',{name:'Synthetic M4 browser',exact:true}).waitFor();
  const snapshot=await(await page.request.get(api+'/v1/tasks/'+task.id,{headers})).json();assert.equal(snapshot.status,'completed');assert.equal(snapshot.progress,100);
  const history=await(await page.request.get(api+'/v1/tasks/'+task.id+'/activity',{headers})).json();assert.equal(history.length,4);
  const stale=await page.request.patch(api+'/v1/tasks/'+task.id,{headers,data:{version:task.version,status:'completed'}});assert.equal(stale.status(),409);
  assert.deepEqual(errors,[]);await page.screenshot({path:'.runtime/m41-task-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_http_db_ui:true,create_and_transition_completed:true,stale_completion_denied:true,provider_calls:0,screenshot:'.runtime/m41-task-ui.png'}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
