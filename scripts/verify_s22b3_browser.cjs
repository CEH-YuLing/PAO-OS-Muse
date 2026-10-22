const assert=require('node:assert/strict'),{open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_QUOTA_BROWSER);let ambiguous=false,hold=false,release,held=false,putCount=0;
 const pending=new Promise(resolve=>{release=resolve});
 const h=await open(f,{intercept:async(route,response)=>{
   const request=route.request(),path=new URL(request.url()).pathname;
   if(path===`/v1/workspaces/${f.workspace}/resources/models`){
     if(request.method()==='PUT'){putCount++;if(ambiguous){ambiguous=false;await route.abort('failed');return true}}
     if(request.method()==='GET'&&hold){hold=false;held=true;await pending;await route.fulfill({response});return true}
   }
   return false;
 }}),p=h.page,card=pool=>p.getByLabel(`Quota ${pool}`,{exact:true});
 const save=(pool,title)=>card(pool).getByRole('button',{name:`Lưu quota ${title}`,exact:true});
 const refresh=(pool,title)=>card(pool).getByRole('button',{name:`Tải lại quota ${title}`,exact:true});
 const change=(pool,label,value)=>card(pool).getByLabel(label,{exact:true}).fill(value);
 const field='Lượt AI mỗi ngày (UTC)',title='AI và embeddings';
 const chooseWorkspace=async wid=>{
  if(p.viewportSize().width<1100){await p.getByLabel('Mở điều hướng',{exact:true}).click();await p.locator('.pao-sidebar-enterprise select').selectOption(wid)}
  else await p.locator('.pao-topbar-context select').selectOption(wid);
 };
 const switchTo=async wid=>{await chooseWorkspace(wid);await card('models').getByLabel(field,{exact:true}).waitFor()};
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);await p.goto(f.web+'/settings');
  await card('models').getByLabel(field,{exact:true}).waitFor();assert.equal(await card('models').getByLabel(field,{exact:true}).inputValue(),'17');
  await p.getByText(/Chi phí thực tế và quota còn lại/).waitFor();await card('models').getByText('Lượt hôm nay chưa có usage chính xác',{exact:true}).waitFor();
  const unknown=card('models').locator('dl > div').filter({has: p.getByText('Lượt hôm nay chưa có usage chính xác',{exact:true})});assert.equal(await unknown.locator('dd').innerText(),'1');
  step='validation';await change('models',field,'1e3');assert.equal(await save('models',title).isDisabled(),true);assert.equal(putCount,0);
  step='save/reload';await change('models',field,'18');await save('models',title).click();await card('models').getByRole('status').waitFor();assert.equal(putCount,1);
  await p.reload();await card('models').getByLabel(field,{exact:true}).waitFor();assert.equal(await card('models').getByLabel(field,{exact:true}).inputValue(),'18');
  const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token')),headers={Authorization:'Bearer '+token};
  const path=f.api+`/v1/workspaces/${f.workspace}/resources/models`;
  step='real CAS conflict';const foreign=await p.request.put(path,{headers,data:{expected_version:2,daily_model_calls:21,daily_model_tokens:100000,concurrent_models:2}});assert.equal(foreign.status(),200);
  await change('models',field,'22');await save('models',title).click();await card('models').getByRole('alert').filter({hasText:'phiên khác'}).waitFor();assert.equal(await card('models').getByLabel(field,{exact:true}).count(),0);assert.equal(putCount,2);
  await refresh('models',title).click();await card('models').getByLabel(field,{exact:true}).waitFor();assert.equal(await card('models').getByLabel(field,{exact:true}).inputValue(),'21');
  step='committed PUT with lost response';ambiguous=true;await change('models',field,'23');await save('models',title).click();await card('models').getByRole('alert').filter({hasText:'có thể server đã nhận'}).waitFor();assert.equal(putCount,3);
  assert.equal((await (await p.request.get(path,{headers})).json()).model_policy.daily_model_calls,23);
  await refresh('models',title).click();await card('models').getByLabel(field,{exact:true}).waitFor();assert.equal(await card('models').getByLabel(field,{exact:true}).inputValue(),'23');assert.equal(putCount,3);
  step='late A response discarded on switch';hold=true;await refresh('models',title).click();await p.waitForFunction(()=>true);for(let i=0;i<50&&!held;i++)await new Promise(resolve=>setTimeout(resolve,20));assert.ok(held);
  await switchTo(f.second);release();assert.equal(await card('models').getByLabel(field,{exact:true}).inputValue(),'500');
  step='admin all pools';await change('models','Lượt AI chạy đồng thời','3');await save('models',title).click();await card('models').getByRole('status').waitFor();
  await change('reads','Việc đọc mỗi ngày (UTC)','22');await save('reads','Đọc MCP và Ads').click();await card('reads').getByRole('status').waitFor();
  step='mobile actual control';await p.setViewportSize({width:390,height:844});await change('metadata','Lượt danh mục mỗi ngày (UTC)','19');await save('metadata','Danh mục và cấu hình kết nối').click();await card('metadata').getByRole('status').waitFor();await h.mobile();
  step='operator no quota endpoint';const observed=[];const onRequest=req=>{if(new URL(req.url()).pathname.includes(`/workspaces/${f.employee}/resources/`))observed.push(req.method())};p.on('request',onRequest);
  await chooseWorkspace(f.employee);await p.getByText('Chỉ owner/admin được xem và sửa quota.',{exact:false}).waitFor();assert.equal(await card('models').count(),0);assert.deepEqual(observed,[]);p.off('request',onRequest);
  step='switch back';await switchTo(f.workspace);assert.equal(await card('models').getByLabel(field,{exact:true}).inputValue(),'23');assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,cas:true,unknown_save:true,late_response:true,mobile_save:true,roles:true,reload:true,tenant_switch:true,real_provider_calls:false}));
 }finally{release();await h.close()}
})().catch(e=>{console.error('P6 browser failed at quota '+step+' '+String(e.message).split('\n')[0].slice(0,180));process.exitCode=1});
