const assert=require('node:assert/strict');const {chromium}=require('playwright');
const f=JSON.parse(process.env.PAO_RESULT_BROWSER_FIXTURE||'null');assert.ok(f&&new URL(f.api).hostname==='127.0.0.1');let stage='launch';
(async()=>{
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];let closing=false,drop=true,first=null;
 page.setDefaultTimeout(35000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.route('**/v1/**',async route=>{try{
  const req=route.request(),u=new URL(req.url());const response=await route.fetch({url:f.api+u.pathname+u.search});
  if(req.method()==='POST'&&u.pathname===`/v1/results/${f.parent}/deliveries`){
   if(drop){assert.equal(response.status(),200);first=req.postData();drop=false;await route.abort();return}assert.equal(first,req.postData());
  }await route.fulfill({response});
 }catch(e){if(!closing)errors.push('Route failed at '+stage);await route.abort().catch(()=>{})}});
 try{
  stage='login';await page.goto(f.web+'/');await page.getByLabel('Email',{exact:true}).fill('owner@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');
  const me=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/me'&&r.status()===200);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await me;await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor({state:'hidden'});
  stage='goal-inbox';await page.goto(f.web+'/automation/review');const row=page.getByLabel('Result inbox').locator('article').filter({has:page.getByRole('heading',{name:`completed · ${f.parent}`,exact:true})});await row.waitFor();assert.ok((await row.innerText()).includes('goal_dry_run'));
  stage='ack';await row.getByRole('button',{name:'Xác nhận đã xem',exact:true}).click();await row.getByText('Đã xác nhận',{exact:true}).waitFor();
  stage='delivery';await row.getByRole('button',{name:'Giao thông báo trong PAO',exact:true}).click();await page.getByRole('alert').waitFor();await row.getByRole('button',{name:'Giao thông báo trong PAO',exact:true}).click();await row.getByText(/Đã giao in-app, không đồng nghĩa đã đọc/).waitFor();
  stage='reload';await page.reload();await row.getByText('Đã xác nhận',{exact:true}).waitFor();await row.getByText('Thông báo đã giao cho bạn trong PAO.',{exact:true}).waitFor();await row.getByRole('button',{name:'Xem trạng thái giao',exact:true}).click();await row.getByText(/lần xử lý 1/).waitFor();
  stage='mobile';await page.setViewportSize({width:390,height:844});await page.evaluate(async()=>{await document.fonts.ready;await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=window.innerWidth,undefined,{timeout:5000});await page.screenshot({path:f.screenshot,fullPage:true});assert.deepEqual(errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,goal_inbox:true,ack:true,lost_ack_delivery_dedup:true,notification_reload:true,mobile_width:390,page_errors:0}));
 }catch(e){console.error('Result browser failed at '+stage+': '+String(e.message).split('\n')[0]);throw e}
 finally{closing=true;await page.close();await browser.close()}
})().catch(()=>{process.exitCode=1});
