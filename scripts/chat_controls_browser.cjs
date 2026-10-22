// Isolated UI fixture. Never forwards /v1 or model/provider traffic.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),base=process.env.PAO_MODEL_UI_URL||'http://127.0.0.1:3200';
const folder=path.join(root,'.runtime','chat-controls-browser-'+Date.now());fs.mkdirSync(folder);
const actor='22222222-2222-4222-8222-222222222222',wid='11111111-1111-4111-8111-111111111111',sid='33333333-3333-4333-8333-333333333333';
const session={id:sid,workspace_id:wid,user_id:actor,title:'Hội thoại kiểm tra bố cục',brand_id:null,brain_id:null,memory_enabled:false,created_at:'2026-10-20T01:00:00Z'};
const shared=!process.argv.includes('--legacy'),resource='55555555-5555-4555-8555-555555555555';
const openai=process.argv.includes('--openai'),codex=process.argv.includes('--codex');assert.ok(!(openai||codex)||shared);
const muse=process.argv.includes('--muse');assert.ok(!muse||shared);
const personalCatalog=process.argv.includes('--personal-catalog');assert.ok(!personalCatalog||!shared);
let catalogReads=0,refreshAvailable=false;
const provider=shared?(muse?'muse':openai?'openai':codex?'codex_cli':'openrouter'):'codex_cli',modelA=openai?'gpt-6-luna':'fixture-model-A',modelB=openai?'gpt-6.1-sol':'fixture-model-B';
const engine={available:true,version:1,selection:{provider,model:modelA,...(shared?{installation_resource_id:resource,reasoning_effort:null}:{personal_cli_source_id:resource})},pinned:true,knowledge_override:false};
const profile={available:true,version:1,pinned:false,group:'',policy:{privacy:'cloud_allowed',cloud_references:false,context_tokens:2048,max_bytes:32768,max_output_tokens:256,max_run_tokens:4096,max_calls:2,require_reported_usage:false}};
const writes=[],unknown=[],external=[],errors=[];let browser,step='start';
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1600,height:1000},serviceWorkers:'block'});
 await context.addInitScript(({actor,wid})=>{sessionStorage.setItem('pao.access_token','fixture-only-token');sessionStorage.setItem('pao.workspace.'+actor,wid)},{actor,wid});
 await context.route('**/*',async route=>{
  const r=route.request(),u=new URL(r.url());
  if(u.origin!==base){external.push(u.origin);return route.abort()}
  if(u.pathname==='/api/weather')return route.fulfill({status:200,json:{}});
  if(!u.pathname.startsWith('/v1/'))return route.continue();
  let body;
  if(r.method()!=='GET'){
   if(personalCatalog&&u.pathname===`/v1/workspaces/${wid}/cli-connections/${resource}/models`){
    assert.equal(r.method(),'POST');assert.deepEqual(r.postDataJSON(),{version:5});catalogReads++;refreshAvailable=true;
    return route.fulfill({status:200,json:{inference_called:false}});
   }
   writes.push({path:u.pathname,body:r.postDataJSON()});
   if(u.pathname===`/v1/sessions/${sid}/engine`&&r.method()==='PUT'){
    assert.equal(r.postDataJSON().model,modelB);assert.equal(r.postDataJSON().provider,provider);
    if(muse)assert.equal(r.postDataJSON().prepare_muse_context,true);
    if(shared){assert.equal(r.postDataJSON().installation_resource_id,resource);assert.equal(r.postDataJSON().reasoning_effort,'high');}
    engine.version++;engine.selection.model=modelB;engine.selection.reasoning_effort=shared?'high':null;body=engine;
   }else if(u.pathname===`/v1/sessions/${sid}/chat`&&r.method()==='PUT'){
    assert.equal(r.postDataJSON().group,'Nhóm thử');assert.equal(r.postDataJSON().policy.token_mode,'provider');profile.version++;profile.group='Nhóm thử';body=profile;
   }else{unknown.push(r.method()+':'+u.pathname);return route.fulfill({status:403,json:{detail:'fixture_only'}})}
  }else if(u.pathname==='/v1/me')body={id:actor,email:'fixture@pao.test',workspaces:[{id:wid,name:'Doanh nghiệp thử',role:'owner'}]};
  else if(u.pathname===`/v1/workspaces/${wid}/context`)body={id:wid,name:'Doanh nghiệp thử',role:'owner'};
  else if(u.pathname==='/v1/sessions')body=[session];
  else if(u.pathname===`/v1/sessions/${sid}`)body={...session,messages:[{id:'msg-1',role:'user',content:'Nội dung hội thoại không bị dịch chuyển khi mở bộ chọn.',created_at:session.created_at,run_id:null}],active_run:null};
  else if(u.pathname===`/v1/sessions/${sid}/engine`)body=engine;
  else if(u.pathname===`/v1/sessions/${sid}/chat`)body=profile;
  else if(u.pathname===`/v1/sessions/${sid}/knowledge`)body={available:false,enabled:false,scope:'brain',brain_id:null};
  else if(u.pathname==='/v1/engines')body={available:true,scope:shared?'installation':'legacy',engines:[{provider:engine.selection.provider,models:[modelA,modelB,...(openai?['unknown-model']:[]),...(personalCatalog&&refreshAvailable?['fixture-model-C']:[])],local:false,error:null,...(shared?{installation_resource_id:resource,model_details:[modelA,modelB,...(openai?['unknown-model']:[])].map(model=>({model,display_name:model,reasoning_efforts:openai?(model==='unknown-model'?[]:[...(model===modelA?['none']:[]),'low','medium','high','xhigh','max']):['low','high'],default_effort:openai?(model==='unknown-model'?null:'medium'):'low'}))}:{personal_cli_source_id:resource,...(personalCatalog?{personal_cli_source_version:5,model_details:[modelA,modelB,'fixture-model-C'].map(model=>({model,display_name:model,reasoning_efforts:[],default_effort:null}))}:{})})}]};
  else if(u.pathname===`/v1/workspaces/${wid}/model-grants`)body={items:[],has_more:false};
  else if(u.pathname==='/v1/voice/status')body={enabled:false};
  else if(u.pathname==='/v1/automation/status')body={enabled:false};
  else if(u.pathname==='/v1/ads/write-status')body={enabled:false};
  else if(u.pathname==='/v1/ads/autopilot/status')body={global_enabled:false,meta_enabled:false};
  else if(u.pathname.endsWith('/business-planning/status'))body={available:false,can_manage:false};
  else if(u.pathname==='/v1/telegram/status')body={enabled:false,configured:false,delivery_issues:[]};
  else if(['/v1/agents','/v1/brands'].includes(u.pathname))body=[];
  else if(u.pathname==='/v1/platform/catalog')body={features:[],integrations:[],model_providers:[],javis_compatibility:{}};
  else if(u.pathname==='/v1/health')body={status:'ok'};
  else if(u.pathname==='/v1/muse-client')body={revision:0,connected:false,can_manage:false,models:[],scope:'installation',connection_mode:'catalog_only',inference_enabled:false,inference_verified:false,credentials_stored_in_PAO:false};
  else{unknown.push(u.pathname);return route.fulfill({status:404,json:{detail:'fixture_missing'}})}
  return route.fulfill({status:200,json:structuredClone(body)});
 });
 const p=await context.newPage();p.setDefaultTimeout(20000);p.on('pageerror',e=>errors.push(e.message));
 try{
  await p.goto(base+'/pao-ai');
  const model=()=>p.getByRole('button',{name:'Chọn mô hình hội thoại',exact:true});
  const privacy=()=>p.getByRole('button',{name:'Hội thoại, quyền riêng tư và thống kê',exact:true});
  step='header controls loaded';await model().waitFor();await privacy().waitFor();
  assert.equal(await p.locator('.pao-ai-composer .pao-engine-picker').count(),0);
  assert.equal(await p.locator('.pao-ai-chat-header').getByRole('button',{name:'Chọn mô hình hội thoại',exact:true}).count(),1);
  assert.equal(await p.locator('.pao-page-heading').getByRole('button',{name:'Hội thoại, quyền riêng tư và thống kê',exact:true}).count(),1);
  for(const theme of ['dark','light']){
   if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
   for(const width of [1600,1024,768,390,320]){
    step=`${theme}-${width}`;await p.setViewportSize({width,height:900});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
    await p.locator('.pao-app-stage').evaluate(async el=>{await Promise.all(el.getAnimations().map(animation=>animation.finished.catch(()=>{})));await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))});
    await model().scrollIntoViewIfNeeded();const before=await p.locator('.pao-ai-messages').boundingBox();await model().click();
    const dialog=p.getByRole('dialog',{name:'Chọn mô hình hội thoại',exact:true});await dialog.waitFor();
    const rect=await dialog.boundingBox();assert.ok(rect.x>=0&&rect.x+rect.width<=width+1&&rect.y>=0&&rect.y+rect.height<=900+1,JSON.stringify(rect));
    const after=await p.locator('.pao-ai-messages').boundingBox();assert.deepEqual(before,after);
    await dialog.getByRole('tab',{name:'Kết nối qua Client',exact:true}).click();
    for(const name of ['Codex','Claude','Antigravity','Muse'])assert.equal(await dialog.getByRole('heading',{name,exact:true}).count(),1);
    if(muse)assert.equal(await dialog.getByRole('radio',{name:'Muse — '+modelB,exact:true}).isEnabled(),true);
    else assert.equal(await dialog.getByText('Chưa có kết nối Muse trong PAO.',{exact:true}).count(),1);
    if(width===1600||width===390)await p.screenshot({path:path.join(folder,theme+'-client-'+width+'.png'),animations:'disabled'});
    await dialog.getByRole('tab',{name:'Kết nối qua API',exact:true}).click();
    for(const name of ['OpenAI','Claude','Google Gemini','OpenRouter'])assert.equal(await dialog.getByRole('heading',{name,exact:true}).count(),1);
    await dialog.getByLabel('Tìm mô hình',{exact:true}).fill('does-not-exist');assert.equal(await dialog.getByRole('radio').count(),0);
    await dialog.getByLabel('Tìm mô hình',{exact:true}).fill('');
    if(width===1600||width===390)await p.screenshot({path:path.join(folder,theme+'-api-'+width+'.png'),animations:'disabled'});
    await p.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});await model().focus();await p.keyboard.press('Enter');await dialog.waitFor();
    await dialog.getByRole('button',{name:'Đóng chọn mô hình hội thoại',exact:true}).click();assert.equal(await model().evaluate(e=>e===document.activeElement),true);
    await privacy().click();const settings=p.getByRole('dialog',{name:'Hội thoại, quyền riêng tư và thống kê',exact:true});await settings.waitFor();
    const box=await settings.boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1&&box.y+box.height<=901,JSON.stringify(box));
    await p.keyboard.press('Escape');await settings.waitFor({state:'hidden'});
    if(width===1600){const nav=await p.evaluate(()=>{const el=document.querySelector('.pao-sidebar');return {box:el.getBoundingClientRect().toJSON(),top:document.elementFromPoint(100,180)?.className,transform:getComputedStyle(el).transform,visible:!!document.elementFromPoint(100,180)?.closest('.pao-sidebar')}});fs.writeFileSync(path.join(folder,theme+'-sidebar.json'),JSON.stringify(nav));assert.ok(nav.visible,JSON.stringify(nav));}
    if(width===1600||width===390)await p.screenshot({path:path.join(folder,theme+'-'+width+'.png'),fullPage:true,animations:'disabled'});
   }
  }
  step='model still saves through same contract';await model().click();
  const dialog=p.getByRole('dialog',{name:'Chọn mô hình hội thoại',exact:true});
  const sourceName=provider==='muse'?'Muse':provider==='codex_cli'?'Codex':provider==='openai'?'API-OpenAI':'API-OpenRouter';
  if(personalCatalog){
   await dialog.getByRole('tab',{name:'Kết nối qua Client',exact:true}).click();
   await dialog.getByRole('button',{name:'Cập nhật danh mục Codex',exact:true}).click();
   await dialog.getByRole('radio',{name:'Codex — fixture-model-C',exact:true}).waitFor();
   assert.equal(catalogReads,1);
   for(const event of ['pao:codex-profile','pao:ai-resources']){
    const pending=p.waitForResponse(response=>new URL(response.url()).pathname==='/v1/engines');
    await p.evaluate(name=>window.dispatchEvent(new Event(name)),event);await pending;
    await dialog.getByRole('radio',{name:'Codex — fixture-model-C',exact:true}).waitFor();
   }
  }
  const choose=async model=>{await dialog.getByRole('tab',{name:['muse','codex_cli'].includes(provider)?'Kết nối qua Client':'Kết nối qua API',exact:true}).click();await dialog.getByRole('radio',{name:`${sourceName} — ${model}`,exact:true}).check()};
  await choose(modelB);
  assert.ok((await model().innerText()).includes(modelA),'Unsaved draft must not change applied header');
  assert.equal(writes.length,0,'Picking tabs/models never writes until Apply');
  if(openai){
   assert.equal(await p.getByLabel('Mức suy luận',{exact:true}).locator('option[value="none"]').count(),0);
   await p.getByLabel('Mức suy luận',{exact:true}).selectOption('high');
   await choose('unknown-model');
   assert.equal(await p.getByLabel('Mức suy luận',{exact:true}).isDisabled(),true);
   assert.equal(await p.getByLabel('Mức suy luận',{exact:true}).inputValue(),'');
   await choose(modelA);
   assert.equal(await p.getByLabel('Mức suy luận',{exact:true}).locator('option[value="none"]').count(),1);
   await choose(modelB);
   assert.equal(await p.getByLabel('Mức suy luận',{exact:true}).inputValue(),'');
  }
  if(shared)await p.getByLabel('Mức suy luận',{exact:true}).selectOption('high');
  await p.getByRole('button',{name:'Áp dụng mô hình',exact:true}).click();await model().filter({hasText:modelB}).waitFor();await dialog.waitFor({state:'hidden'});
  assert.ok((await model().innerText()).includes(sourceName));
  step='privacy still saves through same contract';await privacy().click();
  for(const name of ['Giới hạn context','Giới hạn output','Ngân sách run'])assert.equal(await p.getByRole('spinbutton',{name,exact:true}).count(),0);
  await p.getByText('Ngữ cảnh, đầu ra và token suy luận theo khả năng của mô hình.',{exact:false}).waitFor();
  await p.getByLabel('Nhóm hội thoại',{exact:true}).fill('Nhóm thử');await p.getByRole('button',{name:'Lưu cấu hình chat',exact:true}).click();await p.waitForFunction(()=>document.querySelector('input[aria-label="Nhóm hội thoại"]')?.value==='Nhóm thử');
  await p.screenshot({path:path.join(folder,'provider-token-policy.png'),animations:'disabled'});
  await p.keyboard.press('Escape');await p.setViewportSize({width:1600,height:900});
  const frame=await model().evaluate(el=>({height:el.getBoundingClientRect().height,font:parseFloat(getComputedStyle(el.querySelector('strong')).fontSize),fontFamily:getComputedStyle(el.querySelector('strong')).fontFamily,caption:parseFloat(getComputedStyle(el.querySelector('small')).fontSize),shape:getComputedStyle(el,'::before').clipPath,borderRadius:getComputedStyle(el).borderRadius}));
  assert.ok(frame.height>=44&&frame.height<=64,JSON.stringify(frame));assert.ok(frame.font>=13&&frame.font<=14);assert.match(frame.fontFamily,/system-ui|sans-serif/i);assert.equal(frame.caption,10);assert.ok(frame.shape.startsWith('polygon('));assert.equal(frame.borderRadius,'0px');
  for(const theme of ['dark','light']){
   if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
   await p.locator('.pao-ai-chat-header').screenshot({path:path.join(folder,theme+'-model-header.png'),animations:'disabled'});
  }
  assert.equal(writes.length,2);assert.equal(catalogReads,personalCatalog?1:0);assert.deepEqual(unknown,[]);assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
  const result={pass:true,fixture_only:true,installation_model_effort:shared,openai_provider_effort:openai,unknown_model_effort_disabled:openai,selected_model:modelB,selected_effort:shared?'high':null,legacy_compatibility:!shared,model_in_chat_header:true,compact_chamfered_frame:frame,privacy_in_page_heading:true,no_composer_control_rows:true,keyboard:true,unchanged_message_geometry:true,themes:['dark','light'],widths:[1600,1024,768,390,320],backend_forwarded:0,provider_calls:0,fixture_writes:writes.length};
  fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));
 }catch(error){await p.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});const overflow=await p.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({class:e.className,tag:e.tagName,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,minWidth:getComputedStyle(e).minWidth})).slice(0,20));fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify({pass:false,step,error:error.message,unknown,external,errors,overflow},null,2));throw error}
 finally{await context.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(async()=>{await browser?.close()});
