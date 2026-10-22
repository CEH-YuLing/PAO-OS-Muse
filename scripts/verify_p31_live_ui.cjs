// Real API/DB/ARQ/SSE with synthetic gateway; no user data or cloud/inference.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
  const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
  const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
  let closing=false;
  try{
    const page=await browser.newPage();const errors=[],routeErrors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/v1/**',async route=>{const url=new URL(route.request().url());try{const response=await route.fetch({url:api+url.pathname+url.search});await route.fulfill({response})}catch(error){if(!closing&&!page.isClosed()&&!/aborted|closed/i.test(error.message))routeErrors.push(url.pathname);await route.abort().catch(()=>{})}});
    await page.goto(process.env.PAO_FRONTEND_URL);
    await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);
    await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
    await page.goto(new URL('/pao-ai',process.env.PAO_FRONTEND_URL).href);
    await page.getByRole('button',{name:'Hội thoại mới',exact:true}).last().click();
    const picker=page.locator('details[aria-label="Model hội thoại"]');await picker.waitFor();await picker.locator('summary').click();
    const select=picker.getByLabel('Model hội thoại',{exact:true});await select.waitFor();await page.waitForFunction(()=>{const s=document.querySelector('select[aria-label="Model hội thoại"]');return s&&!s.disabled&&s.options.length>0});
    const selection=JSON.parse(await select.inputValue());assert.equal(selection[0],'ollama');
    await picker.getByRole('button',{name:'Áp dụng model'}).click();await picker.getByText('Model đã ghim cho hội thoại',{exact:false}).waitFor();
    const token=await page.evaluate(()=>sessionStorage.getItem('pao.access_token'));const headers={Authorization:`Bearer ${token}`};
    const me=await (await page.request.get(`${api}/v1/me`,{headers})).json();
    const sessions=await (await page.request.get(`${api}/v1/sessions?workspace_id=${me.workspaces[0].id}`,{headers})).json();assert.equal(sessions.length,1);const sid=sessions[0].id;
    const config=await (await page.request.get(`${api}/v1/sessions/${sid}/engine`,{headers})).json();assert.equal(config.version,2);
    await page.getByLabel('Nội dung yêu cầu PAO').fill('P31 fixture: first run');await page.getByRole('button',{name:'Gửi yêu cầu',exact:true}).click();
    const fetchRun=async()=>{const detail=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();return detail.active_run?.id||detail.messages.at(-1)?.run_id};
    let rid;for(let n=0;n<40&&!rid;n++){rid=await fetchRun();if(!rid)await new Promise(r=>setTimeout(r,250))}assert.ok(rid);
    const pin=await(await page.request.get(`${api}/v1/runs/${rid}/engine`,{headers})).json();assert.equal(pin.snapshot.model,selection[1]);assert.equal(pin.snapshot.provider,'ollama');assert.ok(!JSON.stringify(pin).includes('local_url'));
    const conflict=await page.request.put(`${api}/v1/sessions/${sid}/engine`,{headers,data:{provider:selection[0],model:selection[1],version:2}});assert.equal(conflict.status(),409);
    await page.getByText('P3.1 fixture response · synthetic, no provider call',{exact:true}).waitFor();
    await page.waitForFunction(()=>{const s=document.querySelector('select[aria-label="Model hội thoại"]');return s&&!s.disabled});
    await picker.getByLabel('Model đã chốt run').filter({hasText:selection[1]}).waitFor();
    await page.getByLabel('Nội dung yêu cầu PAO').fill('P31 fixture: cancelled run');await page.getByRole('button',{name:'Gửi yêu cầu',exact:true}).click();
    await page.getByRole('button',{name:'Dừng',exact:true}).click();
    for(let n=0;n<40;n++){const detail=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();if(!detail.active_run)break;await new Promise(r=>setTimeout(r,250))}
    const detail=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();assert.equal(detail.active_run,null);assert.ok(detail.messages.some(m=>m.content==='P31 fixture: first run'));assert.equal(errors.length,0,errors.join('\n'));assert.deepEqual(routeErrors,[]);
    await page.screenshot({path:'.runtime/p31-live-ui.png',fullPage:true});
    console.log(JSON.stringify({pass:true,real_api_db_arq_sse:true,model:selection[1],apply_pin_conflict_history_cancel:true,provider_calls:0,screenshot:'.runtime/p31-live-ui.png'}));
  }finally{closing=true;await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
