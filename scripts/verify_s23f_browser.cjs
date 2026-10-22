const assert=require('node:assert/strict'),{open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_TEAM_BROWSER);let mode='normal',hold=false,held=false,release;const delayed=new Promise(resolve=>{release=resolve}),writes=[],managerGets=[];
 const h=await open(f,{intercept:async(route,response)=>{
  const req=route.request(),u=new URL(req.url());if(req.method()!=='GET')writes.push(u.pathname);
  if(u.pathname.endsWith('/connection-inventory/options')){
   managerGets.push(u.pathname);
   if(hold){hold=false;held=true;await delayed;await route.fulfill({response});return true}
   if(mode==='failed'){await route.fulfill({status:503,contentType:'application/json',body:'{"detail":"fixture-private-team-error"}'});return true}
   if(mode==='malformed'){const data=await response.json();await route.fulfill({response,json:{...data,has_more:'false'}});return true}
   if(mode==='partial'){const data=await response.json();await route.fulfill({response,json:{...data,has_more:true}});return true}
  }return false;
 }}),p=h.page,panel=()=>p.getByLabel('Tài khoản và đội ngũ doanh nghiệp',{exact:true});
 const consoleIssues=[];let knownClockWarnings=0;p.on('console',m=>{if(m.type()==='error'||m.type()==='warning'){const t=m.text();if(m.type()==='warning'&&t==='THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.'){knownClockWarnings++;return}if(/hydration|unique.*key|cannot update|uncontrolled|React/i.test(t)||!(/Failed to load resource|Failed to fetch|net::ERR_/.test(t)))consoleIssues.push(t.replace(/https?:\/\/\S+/g,'[url]').slice(0,160))}});
 const tab=name=>p.getByRole('button',{name,exact:true}),read=async()=>{await panel().getByRole('button',{name:'Đọc lại đội ngũ',exact:true}).click();await panel().getByText('Đang đọc thông tin mô tả đội ngũ…',{exact:true}).waitFor({state:'hidden'})};
 async function hit(locator){await locator.waitFor({state:'visible'});await p.waitForFunction(el=>!el.matches(':disabled'),await locator.elementHandle());await locator.evaluate(el=>el.scrollIntoView({block:'center',inline:'center',behavior:'instant'}));await locator.focus();await p.evaluate(()=>new Promise(requestAnimationFrame));const result=await locator.evaluate(el=>{const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,top=document.elementFromPoint(x,y);return {ok:el===document.activeElement&&x>=0&&x<innerWidth&&y>=70&&y<innerHeight&&!!top&&(el===top||el.contains(top)),x,y,focused:el===document.activeElement,overlay:top?.className||top?.tagName}});assert.ok(result.ok,'control focus/center obscured '+JSON.stringify(result));}
 try{
  await h.login();writes.length=0;await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);await p.goto(f.web+'/settings');
  await panel().getByText(f.email,{exact:true}).waitFor();await panel().getByLabel('Thành viên đủ điều kiện').getByText('owner@example.test',{exact:true}).waitFor();await panel().getByLabel('Vai trò trong doanh nghiệp').getByText('owner',{exact:true}).waitFor();
  assert.ok(!(await p.locator('body').innerText()).includes('Registered agents'));
  step='failed and malformed snapshots discarded';for(const value of ['failed','malformed']){mode=value;await read();await panel().getByRole('alert').waitFor();assert.equal(await panel().getByLabel('Thành viên đủ điều kiện').count(),0);assert.ok(!(await p.locator('body').innerText()).includes('fixture-private-team-error'));}
  step='bounded partial warning';mode='partial';await read();await panel().getByText(/Kết quả bị giới hạn tối đa 100/).waitFor();mode='normal';await read();await panel().getByText(f.email,{exact:true}).waitFor();
  step='late owner metadata after operator switch';hold=true;await panel().getByRole('button',{name:'Đọc lại đội ngũ',exact:true}).click();for(let i=0;i<100&&!held;i++)await new Promise(resolve=>setTimeout(resolve,20));assert.ok(held);const count=managerGets.length;
  await p.locator('.pao-topbar-context select').selectOption(f.second);release();await panel().getByText(/không có quyền đọc danh sách quản lý/).waitFor();assert.equal(await panel().getByText(f.email,{exact:true}).count(),0);assert.equal(await panel().getByRole('button',{name:'Đọc lại đội ngũ',exact:true}).count(),0);assert.equal(managerGets.length,count);
  await p.reload();await panel().getByText(/không có quyền đọc danh sách quản lý/).waitFor();assert.equal(managerGets.length,count);
  step='mobile owner switch and all six Settings tabs';await p.setViewportSize({width:390,height:844});await p.getByLabel('Mở điều hướng',{exact:true}).click();await p.locator('.pao-sidebar-enterprise select').selectOption(f.workspace);await panel().getByText(f.email,{exact:true}).waitFor();
  for(const width of [390,320]){
   await p.setViewportSize({width,height:844});
   for(const name of ['General','Năng lực Javis','Integrations','Cloud Models & Voice','Safety & Approvals','System Status']){
    step='mobile '+width+' '+name;const button=tab(name);await hit(button);await button.click();await p.getByLabel('Đang đọc Settings',{exact:true}).waitFor({state:'hidden'});
    await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth,undefined,{timeout:5000});
    if(name==='General')await hit(panel().getByRole('button',{name:'Đọc lại đội ngũ',exact:true}));
    if(name==='Integrations'){await hit(p.getByRole('button',{name:'Đọc lại trạng thái Ads',exact:true}));await hit(p.getByRole('button',{name:'Đọc lại danh mục trên PAO',exact:true}));}
    if(name==='Cloud Models & Voice')await hit(p.getByLabel('Khóa API OpenAI',{exact:true}));
   }
  }
  step='copilot still reachable without mutation';await p.getByLabel('Mở PAO Copilot',{exact:true}).click();await p.getByText('PAO Copilot',{exact:true}).waitFor();await p.getByLabel('Đóng PAO Copilot',{exact:true}).click();
  await p.setViewportSize({width:1440,height:1000});await tab('General').click();await panel().getByText(f.email,{exact:true}).waitFor();
  await p.waitForFunction(()=>document.querySelector('.pao-sidebar').getBoundingClientRect().x>=0&&Math.abs(document.querySelector('.pao-sidebar').getBoundingClientRect().width-240)<.1&&Math.abs(parseFloat(getComputedStyle(document.querySelector('.pao-app-stage')).marginLeft)-240)<.1);
  await hit(p.locator('.pao-sidebar nav a[href="/settings"]'));
  await p.evaluate(()=>scrollTo(0,0));await p.screenshot({path:f.screenshot.replace('-mobile.png','-desktop-viewport.png')});await p.screenshot({path:f.screenshot.replace('-mobile.png','-desktop.png'),fullPage:true});
  await p.setViewportSize({width:390,height:844});await p.waitForFunction(()=>parseFloat(getComputedStyle(document.querySelector('.pao-app-stage')).marginLeft)===0&&document.querySelector('.pao-sidebar').getBoundingClientRect().right<=0);
  await p.evaluate(()=>scrollTo(0,0));await p.screenshot({path:f.screenshot.replace('-mobile.png','-mobile-viewport.png')});await h.mobile();
  assert.deepEqual(writes,[],'Settings navigation must not mutate');assert.deepEqual(h.errors,[],'browser page/transport errors');assert.equal(consoleIssues.length,0,'unexpected console issue '+JSON.stringify(consoleIssues));
  console.log(JSON.stringify({pass:true,real_http:true,unknown_recovery:true,partial_warning:true,late_response:true,operator_no_manager_get:true,all_tabs_mobile:true,focus_hit_test:true,copilot_preserved:true,no_mutations:true,real_provider_calls:false,console_issues:0,known_three_clock_warnings:knownClockWarnings}));
 }finally{release();await h.close()}
})().catch(error=>{console.error('P6 browser failed at Team Settings '+step+' '+String(error.message).split('\n')[0].slice(0,180));process.exitCode=1});
