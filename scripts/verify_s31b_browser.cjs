const assert=require('node:assert/strict'),{open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_TELEGRAM_MAPPING_BROWSER);let malformed=true,lost=true,hold=false,held=false,release;const delayed=new Promise(resolve=>{release=resolve}),gets=[],writes=[];
 const h=await open(f,{intercept:async(route,response)=>{
  const req=route.request(),u=new URL(req.url());if(!u.pathname.includes('/telegram/legacy/'))return false;
  if(req.method()==='GET')gets.push(u.pathname);else writes.push(u.pathname);
  if(u.pathname.endsWith('/preview')){
   if(hold){hold=false;held=true;await delayed;await route.fulfill({response});return true}
   if(malformed){malformed=false;await route.fulfill({response,json:{...(await response.json()),provider_calls:true}});return true}
  }
  if(u.pathname.endsWith('/apply')&&lost){lost=false;assert.equal(response.status(),201,'mapping apply HTTP status');await route.abort('failed');return true}
  return false;
 }}),p=h.page,panel=()=>p.getByLabel('Chuyển đổi Telegram cũ',{exact:true}),consoleIssues=[];
 p.on('console',m=>{if(['error','warning'].includes(m.type())){const t=m.text();if(t==='THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.')return;if(/hydration|unique.*key|cannot update|uncontrolled|React/i.test(t)||!(/Failed to load resource|Failed to fetch|net::ERR_/.test(t)))consoleIssues.push(m.type())}});
 const read=async()=>{await panel().getByRole('button',{name:'Đọc lại chuyển đổi Telegram',exact:true}).click();await panel().getByText('Đang đối chiếu chuyển đổi Telegram…',{exact:true}).waitFor({state:'hidden'})};
 async function hit(locator){await locator.scrollIntoViewIfNeeded();await locator.focus();await p.evaluate(()=>new Promise(requestAnimationFrame));assert.ok(await locator.evaluate(el=>{const r=el.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,top=document.elementFromPoint(x,y);return el===document.activeElement&&x>=0&&x<innerWidth&&y>=70&&y<innerHeight&&!!top&&(el===top||el.contains(top))}),'mobile control obscured')}
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);await p.goto(f.web+'/settings');await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  step='malformed authority denied';await panel().getByRole('alert').waitFor();assert.equal(await panel().getByRole('button',{name:'Xác nhận chuyển Telegram cũ',exact:true}).count(),0);assert.deepEqual(writes,[]);await read();await panel().getByText('Telegram ID / private chat: 12345 · có binding',{exact:true}).waitFor();
  step='late owner preview cannot leak to operator';hold=true;await panel().getByRole('button',{name:'Đọc lại chuyển đổi Telegram',exact:true}).click();for(let i=0;i<100&&!held;i++)await new Promise(r=>setTimeout(r,20));assert.ok(held);const n=gets.length;
  await p.locator('.pao-topbar-context select').selectOption(f.second);release();step='operator after late response';await p.getByRole('button',{name:'Kết nối',exact:true}).click();await panel().getByText(/Bạn không phải chủ doanh nghiệp/).waitFor();assert.equal(await panel().getByText(/12345/).count(),0);assert.equal(gets.length,n);
  step='operator after reload';await p.reload();await p.getByRole('button',{name:'Kết nối',exact:true}).click();await panel().getByText(/Bạn không phải chủ doanh nghiệp/).waitFor();assert.equal(gets.length,n);
  step='owner reselected';await p.locator('.pao-topbar-context select').selectOption(f.workspace);await p.getByRole('button',{name:'Kết nối',exact:true}).click();await panel().getByText('Telegram ID / private chat: 12345 · có binding',{exact:true}).waitFor();
  step='both independent consents required';const apply=panel().getByRole('button',{name:'Xác nhận chuyển Telegram cũ',exact:true});assert.ok(await apply.isDisabled());await panel().getByLabel('Chỉ chuyển dữ liệu đang tắt',{exact:true}).check();assert.ok(await apply.isDisabled());await panel().getByLabel('Không phát lại lịch sử Telegram',{exact:true}).check();assert.ok(await apply.isEnabled());
  for(const width of [390,320]){step='mobile '+width;await p.setViewportSize({width,height:844});await hit(apply);await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth,undefined,{timeout:5000})}
  step='committed apply response lost no retry';await apply.click();await panel().getByRole('alert').waitFor();assert.equal(writes.filter(x=>x.endsWith('/apply')).length,1);assert.equal(await apply.count(),0);await read();await panel().getByText(/Kết nối: ĐANG TẮT · phiên bản 1/).waitFor();assert.equal(writes.filter(x=>x.endsWith('/apply')).length,1);
  step='explicit revoke leaves legacy transport blocked';const revoke=panel().getByRole('button',{name:'Thu hồi chuyển đổi Telegram',exact:true});assert.ok(await revoke.isDisabled());await panel().getByLabel('Thu hồi không bật lại bot cũ',{exact:true}).check();await hit(revoke);await revoke.click();await panel().getByText(/Kết nối: ĐÃ THU HỒI · phiên bản 2/).waitFor();await read();await panel().getByText(/Kết nối: ĐÃ THU HỒI · phiên bản 2/).waitFor();assert.equal(writes.filter(x=>x.endsWith('/revoke')).length,1);
  assert.ok(!(await p.locator('body').innerText()).includes('PRIVATE'));assert.ok(!(await p.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}))).includes('PRIVATE'));assert.equal(await panel().locator('input[type=password]').count(),0);
  await h.mobile();assert.deepEqual(h.errors,[]);assert.deepEqual(consoleIssues,[]);
  console.log(JSON.stringify({pass:true,real_http:true,malformed_denied:true,two_consents:true,lost_ack_no_retry:true,manual_get_recovery:true,owner_revoke:true,operator_no_mapping_get:true,late_scope_denied:true,mobile_controls:true,real_provider_calls:false}));
 }finally{release();await h.close()}
})().catch(error=>{console.error('P6 browser failed at Telegram mapping '+step+' '+String(error.message).split('\n')[0].slice(0,160));process.exitCode=1});
