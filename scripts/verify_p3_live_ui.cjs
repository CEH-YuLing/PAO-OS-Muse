const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/v1/**',async route=>{const u=new URL(route.request().url());try{await route.fulfill({response:await route.fetch({url:api+u.pathname+u.search})})}catch{await route.abort().catch(()=>{})}});
  await page.goto(process.env.PAO_FRONTEND_URL);await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');
  await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));await page.goto(new URL('/pao-ai',process.env.PAO_FRONTEND_URL).href);
  await page.getByRole('button',{name:'Hội thoại mới',exact:true}).last().click();
  const panel=page.locator('details[aria-label="Quản lý hội thoại P3"]');await panel.waitFor();await panel.locator('summary').click();
  await panel.getByLabel('Ghim hội thoại',{exact:true}).check();await panel.getByLabel('Nhóm hội thoại',{exact:true}).fill('Synthetic Marketing');
  await panel.getByRole('button',{name:'Lưu cấu hình chat',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('input[aria-label="Nhóm hội thoại"]').disabled);
  const headers={Authorization:`Bearer ${await page.evaluate(()=>sessionStorage.getItem('pao.access_token'))}`};
  const me=await(await page.request.get(api+'/v1/me',{headers})).json();
  const sessions=await(await page.request.get(api+'/v1/sessions?workspace_id='+me.workspaces[0].id,{headers})).json();const sid=sessions[0].id;
  const p=await(await page.request.get(`${api}/v1/sessions/${sid}/chat`,{headers})).json();assert.equal(p.pinned,true);assert.equal(p.group,'Synthetic Marketing');assert.equal(p.policy.privacy,'local_only');
  for(let n=0;n<4;n++){
   await page.getByLabel('Nội dung yêu cầu PAO').fill('P3 fixture: marker'+n+' budget 250');await page.getByRole('button',{name:'Gửi yêu cầu',exact:true}).click();
   await page.getByText('P3 synthetic response',{exact:true}).last().waitFor();
   for(let i=0;i<60;i++){const d=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();if(!d.active_run&&d.messages.length===(n+1)*2)break;await new Promise(r=>setTimeout(r,200))}
   await page.waitForFunction(()=>!document.querySelector('button[aria-label="Gửi yêu cầu"]').disabled||!document.querySelector('textarea[aria-label="Nội dung yêu cầu PAO"]').disabled);
  }
  await panel.getByRole('button',{name:'Compact hội thoại',exact:true}).click();await panel.getByLabel('Kết quả quản lý chat').filter({hasText:'extractive-v1'}).waitFor();
  await panel.getByLabel('Tìm hội thoại',{exact:true}).fill('marker0');await panel.getByRole('button',{name:'Tìm hội thoại',exact:true}).click();
  await panel.getByRole('button',{name:/Synthetic Marketing ·/}).waitFor();
  const downloadEvent=page.waitForEvent('download');await panel.getByRole('button',{name:'Xuất Markdown',exact:true}).click();assert.match((await downloadEvent).suggestedFilename(),/\.md$/);
  await panel.getByRole('button',{name:'Xem usage',exact:true}).click();await panel.getByLabel('Kết quả quản lý chat').filter({hasText:'reported'}).waitFor();
  await page.getByLabel('Nội dung yêu cầu PAO').fill('/help');await page.getByRole('button',{name:'Gửi yêu cầu',exact:true}).click();await page.getByLabel('Kết quả lệnh chat').filter({hasText:'/compact'}).waitFor();
  const before=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();assert.equal(before.messages.length,8);
  await panel.getByRole('button',{name:'Thử lại bằng run mới',exact:true}).click();
  for(let i=0;i<60;i++){const d=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();if(!d.active_run&&d.messages.length===10)break;await new Promise(r=>setTimeout(r,200))}
  const done=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();assert.equal(done.messages.length,10);
  await page.getByRole('button',{name:'Dừng',exact:true}).waitFor({state:'hidden'});
  await page.getByText('P3 synthetic response',{exact:true}).last().waitFor();
  if(await panel.getAttribute('open')===null)await panel.locator('summary').click();
  assert.deepEqual(errors,[]);await page.screenshot({path:'.runtime/p3-live-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_api_db_arq_sse:true,pin_group_privacy_search_export_compaction_commands_retry_usage:true,provider_calls:0,screenshot:'.runtime/p3-live-ui.png'}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
