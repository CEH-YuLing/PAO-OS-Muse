const assert=require('node:assert/strict'),{open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_SETTINGS_OBSERVATIONS_BROWSER);
 let mode='normal',hold=false,held=false,release;const delayed=new Promise(resolve=>{release=resolve});const writes=[];
 const h=await open(f,{intercept:async(route,response)=>{
  const req=route.request(),url=new URL(req.url());
  if(req.method()!=='GET')writes.push(url.pathname);
  if(url.pathname==='/v1/integrations/meta/connection'&&url.searchParams.get('workspace_id')===f.workspace){
   if(hold){hold=false;held=true;await delayed;await route.fulfill({response});return true}
   if(mode==='partial'){await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'fixture-private-marker-not-a-key'})});return true}
   if(mode==='malformed'){await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({configured:'yes',status:'connected',scopes:[]})});return true}
   await route.fulfill({response,json:{configured:true,status:'connected',scopes:[]}});return true;
  }
  if(url.pathname==='/v1/telegram/status'){const body=await response.json();await route.fulfill({response,json:{...body,enabled:true,configured:true}});return true}
  if(url.pathname==='/v1/ads/write-status'&&mode==='malformed'){await route.fulfill({status:200,contentType:'application/json',body:'{}'});return true}
  return false;
 }}),p=h.page;
 const tab=name=>p.getByRole('button',{name,exact:true});const meta=()=>p.getByLabel('Meta Ads connection status',{exact:true});
 const refresh=async()=>{await tab('Làm mới trạng thái').click();await p.getByLabel('Đang đọc Settings',{exact:true}).waitFor({state:'hidden'})};
 try{
  await h.login();writes.length=0;await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);await p.goto(f.web+'/settings');
  step='stored records are not health';await tab('Integrations').click();await meta().getByText('Đã lưu kết nối',{exact:true}).waitFor();
  await meta().getByText('hoạt động ổn định: Chưa xác minh · Nghiệm thu thật: Chưa xác minh',{exact:true}).waitFor();
  const telegram=p.getByLabel('Telegram connection status',{exact:true});await telegram.getByText('vận hành đang bật',{exact:true}).waitFor();assert.equal(await telegram.getByText('connected',{exact:true}).count(),0);
  step='partial failure clears old connected';mode='partial';await refresh();await meta().getByText('Chưa xác minh',{exact:true}).waitFor();assert.equal(await meta().getByText('Đã lưu kết nối',{exact:true}).count(),0);
  assert.equal(await meta().getByRole('button',{name:'Kết nối',exact:true}).isDisabled(),true);assert.ok(!(await p.locator('body').innerText()).includes('fixture-private-marker-not-a-key'));
  await tab('System Status').click();await p.getByText('8/9 status endpoints phản hồi hợp lệ',{exact:true}).waitFor();await p.getByLabel('Meta integration observation').getByText('UNKNOWN',{exact:true}).waitFor();
  step='malformed 200 and safety unknown';mode='malformed';await refresh();await p.getByText('7/9 status endpoints phản hồi hợp lệ',{exact:true}).waitFor();
  await tab('Safety & Approvals').click();await p.getByRole('alert').filter({hasText:'Chưa đọc được đầy đủ safety gates'}).waitFor();assert.equal(await p.getByText('WRITE GATES OFF',{exact:true}).count(),0);
  step='normal recovery';mode='normal';await refresh();await p.getByText('WRITE GATES OFF',{exact:true}).waitFor();
  step='late response A while switching B';hold=true;await tab('Làm mới trạng thái').click();for(let i=0;i<100&&!held;i++)await new Promise(resolve=>setTimeout(resolve,20));assert.ok(held);
  await p.locator('.pao-topbar-context select').selectOption(f.second);release();await p.getByLabel('Đang đọc Settings',{exact:true}).waitFor({state:'hidden'});
  await tab('Integrations').click();await meta().getByText('disconnected',{exact:true}).waitFor();assert.equal(await meta().getByText('Đã lưu kết nối',{exact:true}).count(),0);assert.equal(await meta().getByRole('button').count(),0);
  step='reload same B';await p.reload();await tab('Integrations').click();await meta().getByText('disconnected',{exact:true}).waitFor();
  step='mobile';await h.mobile();
  step='mobile switch to A';await p.getByLabel('Mở điều hướng',{exact:true}).click();await p.locator('.pao-sidebar-enterprise select').selectOption(f.workspace);await tab('Integrations').click();await meta().getByText('Đã lưu kết nối',{exact:true}).waitFor();
  assert.deepEqual(writes,[]);assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,partial_unknown:true,malformed_unknown:true,late_response:true,tenant_switch:true,reload:true,mobile:true,no_mutations:true,safety_unknown:true,synthetic_status_overlays:true,real_provider_calls:false}));
 }finally{release();await h.close()}
})().catch(error=>{console.error('P6 browser failed at Settings observations '+step+' '+String(error.message).split('\n')[0].slice(0,180));process.exitCode=1});
