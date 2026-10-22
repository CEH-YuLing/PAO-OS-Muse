const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const fixture=JSON.parse(process.env.PAO_SCHEDULE_BROWSER_FIXTURE||'null');
assert.ok(fixture&&new URL(fixture.api).hostname==='127.0.0.1');
let stage='launch';
(async()=>{
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Asia/Ho_Chi_Minh'}),errors=[];
 page.setDefaultTimeout(35000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.route('**/v1/**',async route=>{const url=new URL(route.request().url());const response=await route.fetch({url:fixture.api+url.pathname+url.search});await route.fulfill({response})});
 async function schedules(){await page.getByRole('button',{name:'Xem trước lịch',exact:true}).click();await page.getByRole('heading',{name:'Lịch workflow đã lưu',exact:true}).waitFor()}
 async function save(name){await page.getByRole('button',{name:'Xem trước lịch đã ghim',exact:true}).click();await page.getByLabel('Pinned schedule preview').waitFor();assert.equal(await page.getByRole('button',{name,exact:true}).isDisabled(),true);await page.getByRole('checkbox').check();await page.getByRole('button',{name,exact:true}).click()}
 try{
  stage='login';await page.goto(fixture.web+'/');await page.getByLabel('Email',{exact:true}).fill('owner@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');
  const profile=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/me'&&r.status()===200);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await profile;await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor({state:'hidden'});
  stage='create';await page.goto(fixture.web+'/automation/review');await schedules();
  await page.getByLabel('Schedule template plan ID').fill(fixture.plan);
  const local=await page.evaluate(()=>{const d=new Date(Date.now()+3600000);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)});
  await page.getByLabel('Saved schedule once time').fill(local);await save('Lưu lịch ở trạng thái tắt');
  const article=page.locator('.gr-workspace article');await article.getByRole('heading',{name:'once · disabled',exact:true}).waitFor();
  stage='enable';await article.getByRole('button',{name:'Bật lịch',exact:true}).click();await article.getByRole('heading',{name:'once · enabled',exact:true}).waitFor();
  stage='reload';await page.reload();await schedules();await article.getByRole('heading',{name:'once · enabled',exact:true}).waitFor();
  stage='disable';await article.getByRole('button',{name:'Tắt lịch tương lai',exact:true}).click();await article.getByRole('heading',{name:'once · disabled',exact:true}).waitFor();
  stage='edit';await article.getByRole('button',{name:'Sửa lịch đã tắt',exact:true}).click();await page.getByLabel('Saved schedule mode').selectOption('cron');await page.getByLabel('Saved schedule cron').fill('0 10 * * *');await save('Lưu sửa lịch ở trạng thái tắt');
  await article.getByRole('heading',{name:'cron · disabled',exact:true}).waitFor();
  stage='archive';await article.getByRole('button',{name:'Lưu trữ lịch',exact:true}).click();await article.getByRole('heading',{name:'cron · archived',exact:true}).waitFor();
  await article.getByRole('button',{name:'Xem slot và audit',exact:true}).click();await page.getByLabel('Schedule slots and audit').waitFor();
  const detail=JSON.parse(await page.getByLabel('Schedule slots and audit').innerText());assert.deepEqual(detail.slots,[]);assert.equal(detail.status,'archived','Archived detail');assert.equal(detail.events.length,5,'Five lifecycle events');
  stage='mobile';await page.setViewportSize({width:390,height:844});
  await page.evaluate(async()=>{await document.fonts.ready;await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=window.innerWidth,undefined,{timeout:5000});
  const overflow=await page.evaluate(()=>({width:window.innerWidth,scroll:document.documentElement.scrollWidth,
   elements:[...document.querySelectorAll('main *, .gr-workspace *, .au-panel *')].filter(e=>e.getBoundingClientRect().right>window.innerWidth+1).slice(0,6).map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right}))}));
  assert.equal(overflow.scroll>overflow.width,false,'Mobile overflow '+JSON.stringify(overflow));
  await page.screenshot({path:fixture.screenshot,fullPage:true});assert.deepEqual(errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,create_enable_reload_disable_edit_archive:true,page_errors:0,executions_created:0}));
 }finally{await page.unrouteAll({behavior:'wait'});await browser.close()}
})().catch(e=>{console.error('Schedule browser failed at '+stage+': '+String(e.message).split('\n')[0]);process.exitCode=1});
