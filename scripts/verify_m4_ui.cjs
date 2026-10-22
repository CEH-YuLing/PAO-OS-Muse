// Real signed approvals + actual test ARQ/Redis delivery. No mocks of API responses.
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
  const create=async title=>{const r=await page.request.post(api+'/v1/tasks',{headers,data:{workspace_id:wid,title,status:'waiting_approval',success_criteria:['Synthetic criteria'],evidence:[{reference:'Synthetic M4 review evidence'}]}});assert.equal(r.status(),201);return r.json()};
  const yes=await create('Synthetic M4 approve'),no=await create('Synthetic M4 reject'),stale=await create('Synthetic M4 stale');
  const inbox=await(await page.request.get(api+'/v1/business-events/approvals?workspace_id='+wid,{headers})).json();
  const yesTicket=inbox.find(row=>row.id===yes.id).ticket;
  await page.goto(new URL('/tasks',process.env.PAO_FRONTEND_URL).href);
  const center=page.getByRole('region',{name:'Trung tâm phê duyệt'});
  for(const [title,button] of [['Synthetic M4 approve','Duyệt yêu cầu'],['Synthetic M4 reject','Từ chối yêu cầu']]){
   await center.getByRole('button',{name:'Xem phê duyệt: '+title,exact:true}).click();
   const review=center.getByRole('region',{name:'Nội dung cần duyệt'});await review.getByText('Synthetic M4 review evidence',{exact:false}).waitFor();
   assert.equal(await review.getByRole('button',{name:button,exact:true}).isDisabled(),true);
   await review.getByRole('checkbox').check();await review.getByRole('button',{name:button,exact:true}).click();
   await review.waitFor({state:'hidden'});
  }
  await center.getByRole('button',{name:'Xem phê duyệt: Synthetic M4 stale',exact:true}).click();
  const changed=await page.request.patch(api+'/v1/tasks/'+stale.id,{headers,data:{version:stale.version,description:'Changed while reviewing'}});assert.equal(changed.status(),200);
  const review=center.getByRole('region',{name:'Nội dung cần duyệt'});await review.getByRole('checkbox').check();await review.getByRole('button',{name:'Duyệt yêu cầu',exact:true}).click();
  await center.getByRole('alert').waitFor();assert.match(await center.getByRole('alert').innerText(),/changed/i);
  await review.waitFor({state:'hidden'});
  const replay=await page.request.post(api+'/v1/business-events/approvals/decision',{headers,data:{ticket:yesTicket,decision:'approve'}});assert.equal(replay.status(),409);
  for(const [id,status] of [[yes.id,'completed'],[no.id,'failed'],[stale.id,'waiting_approval']]){
   const row=await(await page.request.get(api+'/v1/tasks/'+id,{headers})).json();assert.equal(row.status,status);
  }
  let delivered=false;
  for(let attempt=0;attempt<60;attempt++){
   const response=await page.request.get(api+'/v1/business-events/diagnostics?workspace_id='+wid,{headers});
   if(response.ok()&&(await response.json()).receipts===4){delivered=true;break;}
   await page.waitForTimeout(500);
  }
  assert(delivered,'All four events must be delivered by the actual test worker');
  const ledger=await(await page.request.get(api+'/v1/business-events/ledger?workspace_id='+wid,{headers})).json();assert.equal(ledger.length,4);
  assert(!JSON.stringify(ledger).includes('Synthetic M4 review evidence'));assert.deepEqual(errors,[]);
  await page.screenshot({path:'.runtime/m4-approval-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_http_db_ui_arq:true,approve_reject:true,review_required:true,stale_and_replay_denied:true,delivered:4,provider_calls:0,screenshot:'.runtime/m4-approval-ui.png'}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
