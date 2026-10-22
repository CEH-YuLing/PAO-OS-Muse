const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const fixture=JSON.parse(process.env.PAO_GOAL_SCHEDULE_BROWSER_FIXTURE||'null');
assert.ok(fixture&&new URL(fixture.api).hostname==='127.0.0.1');
let stage='launch';
(async()=>{
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},timezoneId:'Asia/Ho_Chi_Minh'}),errors=[];
 const progress=setInterval(()=>fs.writeFileSync(fixture.dispatchMarker+'.stage',stage),1000);
 page.setDefaultTimeout(35000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 let drop=true,firstBody=null,retryBody=null,closing=false;
 await page.route('**/v1/**',async route=>{
  try{
  const request=route.request(),url=new URL(request.url());
  const response=await route.fetch({url:fixture.api+url.pathname+url.search});
  if(url.pathname==='/v1/schedules/goals'&&request.method()==='POST'){
   if(drop){assert.equal(response.status(),201);firstBody=request.postData();drop=false;await route.abort('failed');return}
   if(!retryBody)retryBody=request.postData();
  }
  await route.fulfill({response});
  }catch(e){if(!closing)errors.push('HTTP route failure at '+stage);await route.abort().catch(()=>{})}
 });
 async function panel(){await page.getByRole('button',{name:'Lịch Goal',exact:true}).click();await page.getByRole('heading',{name:'Lịch Goal đã lưu',exact:true}).waitFor()}
 async function review(){await page.getByRole('button',{name:'Xem trước lịch Goal',exact:true}).click();await page.getByLabel('Goal schedule pinned preview').waitFor();
  const value=JSON.parse(await page.getByLabel('Goal schedule pinned preview').innerText());assert.equal(value.spec.kind,'bounded_goal');assert.equal(value.spec.goal_id,fixture.goal);assert.equal(value.spec.max_iterations,2);assert.ok(value.spec.snapshot_hash&&value.spec.source_binding);}
 try{
  stage='login';await page.goto(fixture.web+'/');await page.getByLabel('Email',{exact:true}).fill('owner@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');
  const profile=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/me'&&r.status()===200);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await profile;
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor({state:'hidden'});
  stage='create';await page.goto(fixture.web+'/automation/review');await panel();await page.getByLabel('Scheduled Goal').selectOption(fixture.goal);
  await page.getByLabel('Goal schedule plan ID').fill(fixture.plan);
  const local=await page.evaluate(()=>{const d=new Date(Date.now()+3600000);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)});
  await page.getByLabel('Goal schedule once time').fill(local);await page.getByLabel('Goal schedule max_cost_microusd').fill('10');await page.getByLabel('Goal schedule cost_ceiling_microusd').fill('5');
  await review();const save=page.getByRole('button',{name:'Lưu lịch Goal tắt',exact:true});assert.equal(await save.isDisabled(),true);
  stage='invalidate';await page.getByLabel('Goal schedule max_iterations').fill('3');await page.getByLabel('Goal schedule pinned preview').waitFor({state:'hidden'});await page.getByLabel('Goal schedule max_iterations').fill('2');await review();
  await page.getByLabel('Confirm Goal schedule').check();await save.click();
  stage='lost-ack';await page.getByRole('button',{name:'Thử lại đúng lệnh Goal',exact:true}).waitFor();assert.equal(await page.getByLabel('Scheduled Goal').isDisabled(),true);
  await page.getByRole('button',{name:'Thử lại đúng lệnh Goal',exact:true}).click();
  let article=page.locator('.gr-workspace article');await article.getByRole('heading',{name:'once · disabled',exact:true}).waitFor();assert.equal(await article.count(),1);assert.equal(firstBody,retryBody);
  stage='enable';await article.getByRole('button',{name:'Bật lịch Goal',exact:true}).click();await article.getByRole('heading',{name:'once · enabled',exact:true}).waitFor();
  stage='reload';await page.reload();await panel();await article.getByRole('heading',{name:'once · enabled',exact:true}).waitFor();
  stage='disable-edit';await article.getByRole('button',{name:'Tắt lịch Goal tương lai',exact:true}).click();await article.getByRole('heading',{name:'once · disabled',exact:true}).waitFor();
  await article.getByRole('button',{name:'Sửa lịch Goal đã tắt',exact:true}).click();await page.getByLabel('Goal schedule mode').selectOption('cron');await page.getByLabel('Goal schedule cron').fill('0 10 * * *');await review();
  await page.getByLabel('Confirm Goal schedule').check();await page.getByRole('button',{name:'Lưu sửa lịch Goal tắt',exact:true}).click();await article.getByRole('heading',{name:'cron · disabled',exact:true}).waitFor();
  stage='archive';await article.getByRole('button',{name:'Lưu trữ lịch Goal',exact:true}).click();await article.getByRole('heading',{name:'cron · archived',exact:true}).waitFor();
  await article.getByRole('button',{name:'Xem slot và audit Goal',exact:true}).click();await page.getByLabel('Goal schedule slots and audit').waitFor();
  let detail=JSON.parse(await page.getByLabel('Goal schedule slots and audit').innerText());assert.deepEqual(detail.slots,[]);assert.equal(detail.events.length,5);
  stage='second-schedule';await page.getByLabel('Goal schedule mode').selectOption('once');await page.getByLabel('Scheduled Goal').selectOption(fixture.goal);await page.getByLabel('Goal schedule once time').fill(local);await review();await page.getByLabel('Confirm Goal schedule').check();await save.click();
  article=page.locator('.gr-workspace article').filter({has:page.getByRole('heading',{name:'once · disabled',exact:true})});await article.waitFor();await article.getByRole('button',{name:'Bật lịch Goal',exact:true}).click();
  await page.getByRole('heading',{name:'once · enabled',exact:true}).waitFor();
  // Harness advances one eligible slot internally on pao_test; no test-only HTTP route.
  fs.writeFileSync(fixture.dispatchMarker,'ready');
  stage='actual-slot';let slot;
  for(let i=0;i<40;i++){
   await page.getByRole('button',{name:'Cập nhật lịch Goal',exact:true}).click();
   const onceRow=page.locator('.gr-workspace article').filter({has:page.getByRole('heading',{name:/^once · /})});
   await onceRow.getByRole('button',{name:'Xem slot và audit Goal',exact:true}).click();await page.getByLabel('Goal schedule slots and audit').waitFor();
   detail=JSON.parse(await page.getByLabel('Goal schedule slots and audit').innerText());if(detail.slots.length){slot=detail.slots[0];break}await page.waitForTimeout(250);
  }
  assert.ok(slot);assert.equal(detail.status,'completed');
  stage='gate-rollback';fs.writeFileSync(fixture.rollbackMarker,'ready');
  for(let i=0;i<40;i++){
   await page.getByRole('button',{name:'Cập nhật lịch Goal',exact:true}).click();
   if((await page.getByLabel('Goal schedule readiness').innerText()).includes('Quản trị lịch đang tắt'))break;
   await page.waitForTimeout(250);
  }
  assert.ok((await page.getByLabel('Goal schedule readiness').innerText()).includes('Quản trị lịch đang tắt'));
  assert.equal(await page.getByRole('button',{name:'Xem trước lịch Goal',exact:true}).isDisabled(),true,'Preview disabled after gate rollback');
  const completedRow=page.locator('.gr-workspace article').filter({has:page.getByRole('heading',{name:'once · completed',exact:true})});
  await page.waitForFunction(()=>[...document.querySelectorAll('.gr-workspace article button')].some(b=>b.textContent==='Tắt lịch Goal tương lai'&&!b.disabled));
  assert.equal(await completedRow.getByRole('button',{name:'Tắt lịch Goal tương lai',exact:true}).isDisabled(),false,'Disable remains available after refresh finishes');
  stage='mobile';await page.setViewportSize({width:390,height:844});await page.evaluate(async()=>{await document.fonts.ready;await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=window.innerWidth,undefined,{timeout:5000});await page.screenshot({path:fixture.screenshot,fullPage:true});
  stage='open-parent';await page.getByRole('link',{name:'Mở phiên Goal từ slot',exact:true}).click();await page.getByLabel('Goal execution status').waitFor();assert.equal(new URL(page.url()).searchParams.get('execution'),slot.execution_id);
  assert.ok((await page.getByLabel('Goal execution status').innerText()).includes('starting'));assert.deepEqual(errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,lifecycle:true,lost_ack_same_key:true,preview_invalidated:true,gate_rollback_readable:true,actual_slot_open_parent:true,parent:slot.execution_id,page_errors:0,mobile_width:390}));
 }catch(e){console.error('Goal schedule browser failed at '+stage+': '+String(e.message).split('\n')[0]);throw e}
 finally{closing=true;clearInterval(progress);await page.close();await browser.close()}
})().catch(e=>{console.error('Goal schedule browser failed at '+stage+': '+String(e.message).split('\n')[0]);process.exitCode=1});
