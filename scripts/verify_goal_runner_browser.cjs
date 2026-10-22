// Explicit acceptance: browser -> isolated real HTTP API -> Temporal/ARQ/Postgres.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const fixture=JSON.parse(process.env.PAO_GOAL_BROWSER_FIXTURE||'null');
assert.ok(fixture&&new URL(fixture.api).hostname==='127.0.0.1');
let stage='launch';
(async()=>{
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],posts=[];
 page.setDefaultTimeout(35000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 let loseAck=fixture.mode!=='disabled',closing=false;
 await page.route('**/v1/**',async route=>{
  try{
  const request=route.request(),url=new URL(request.url());
  if(request.method()==='POST')posts.push({path:url.pathname,body:request.postDataJSON()});
  const response=await route.fetch({url:fixture.api+url.pathname+url.search});
  // The real API commits, but the browser loses one admission response.
  if(loseAck&&url.pathname.endsWith('/dry-run-runners')){loseAck=false;await route.abort('failed');return}
  await route.fulfill({response});
  }catch(e){
   if(!closing){errors.push('API route failed before teardown');await route.abort('failed').catch(()=>{});}
  }
 });
 async function status(value){await page.waitForFunction(v=>document.querySelector('[aria-label="Goal execution status"]')?.textContent.startsWith(v),value)}
 async function create(goal,plan){
  await page.goto('http://127.0.0.1:3200/automation/goals');
  await page.getByLabel('Goal',{exact:true}).selectOption(goal);
  await page.getByLabel('Goal plan ID',{exact:true}).fill(plan);
  await page.getByLabel('Tiêu chí dry-run',{exact:true}).selectOption('equals');
  await page.getByLabel('Text đích',{exact:true}).fill('Target reached');
  await page.getByRole('button',{name:'Xem trước Goal dry-run',exact:true}).click();
  await page.getByLabel('Goal admission preview').waitFor();
  const button=page.getByRole('button',{name:'Tạo Goal dry-run',exact:true});assert.equal(await button.isDisabled(),true);
  await page.getByRole('checkbox').check();await button.click();
 }
 async function steps(){
  const button=page.getByRole('button',{name:'Duyệt bước hiện tại',exact:true});
  for(let i=0;i<2;i++){
   await button.waitFor();await button.click();
   // The second step must have a distinct current_step/version from the first.
   if(i===0)await page.waitForFunction(()=>document.querySelector('[aria-label="Workflow execution status"]')?.textContent.includes('bước second'));
  }
 }
 try{
  stage='login';await page.goto('http://127.0.0.1:3200/');
  await page.getByLabel('Email',{exact:true}).fill('owner@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');
  const profile=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/me'&&r.status()===200);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await profile;
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor({state:'hidden'});
  if(fixture.mode==='disabled'){
   stage='gates-off';await page.goto('http://127.0.0.1:3200/automation/goals?execution='+fixture.cancelled);
   await page.getByLabel('Goal runner readiness').filter({hasText:'Runner đang tắt'}).waitFor();await status('cancelled');
   await page.goto('http://127.0.0.1:3200/automation/goals');
   assert.equal(await page.getByRole('button',{name:'Xem trước Goal dry-run',exact:true}).isDisabled(),true);
   assert.equal(posts.some(p=>p.path.includes('/goal-executions/')||p.path.endsWith('/dry-run-runners')),false);
  }else{
   stage='admission-lost-ack';await create(fixture.goal,fixture.plan);
   await page.getByRole('button',{name:'Thử lại cùng lệnh',exact:true}).waitFor();
   await page.waitForFunction(()=>!!document.querySelector('[role="alert"]'));
   await page.getByRole('button',{name:'Thử lại cùng lệnh',exact:true}).click();await status('waiting_approval');
   const admits=posts.filter(p=>p.path.endsWith('/dry-run-runners'));assert.equal(admits.length,2);assert.deepEqual(admits[0].body,admits[1].body);
   assert.equal(posts.some(p=>p.path.endsWith('/decision')),false);
   const execution=new URL(page.url()).searchParams.get('execution');assert.ok(execution);
   stage='reload';await page.reload();await status('waiting_approval');
   stage='first-round';await page.getByRole('button',{name:'Duyệt vòng Goal',exact:true}).click();await status('running');
   assert.equal(await page.getByRole('button',{name:'Bắt đầu chạy giả lập',exact:true}).count(),0);
   await steps();await status('waiting_replan');
   stage='replan';await page.getByLabel('Goal replan ID').fill(fixture.replan);
   await page.getByRole('button',{name:'Gửi kế hoạch mới, chưa duyệt',exact:true}).click();await status('waiting_approval');
   assert.equal(posts.filter(p=>p.path.endsWith('/decision')&&p.path.includes('goal-executions')).length,1);
   stage='second-round';await page.getByRole('button',{name:'Duyệt vòng Goal',exact:true}).click();await status('running');await steps();await status('completed');
   assert.match(await page.getByLabel('Goal reservation').innerText(),/Giữ chỗ: 0/);
   stage='cancel';await create(fixture.cancelGoal,fixture.cancelPlan);await status('waiting_approval');
   await page.getByRole('button',{name:'Duyệt vòng Goal',exact:true}).click();await status('running');
   await page.getByRole('button',{name:'Duyệt bước hiện tại',exact:true}).waitFor();
   await page.getByRole('button',{name:'Yêu cầu hủy Goal',exact:true}).click();await status('cancelled');
   assert.match(await page.getByLabel('Goal reservation').innerText(),/Giữ chỗ: 0/);
   fixture.cancelled=new URL(page.url()).searchParams.get('execution');
   await page.setViewportSize({width:390,height:844});await page.reload();await status('cancelled');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
   stage='screenshot';await page.screenshot({path:fixture.screenshot,fullPage:true});
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({pass:true,mode:fixture.mode,real_http:true,page_errors:errors.length,cancelled:fixture.cancelled}));
 }finally{closing=true;await page.unrouteAll({behavior:'ignoreErrors'});await browser.close()}
})().catch(e=>{console.error('Goal browser failed at '+stage+': '+String(e.message).split('\n')[0]);process.exitCode=1});
