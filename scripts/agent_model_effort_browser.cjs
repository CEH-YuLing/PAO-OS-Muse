// Isolated model/effort authoring fixture. No request reaches backend/provider.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:3200',folder=path.join(root,'.runtime','agent-model-browser-'+Date.now());fs.mkdirSync(folder);
const actor='22222222-2222-4222-8222-222222222222',wid='11111111-1111-4111-8111-111111111111',resource='55555555-5555-4555-8555-555555555555',id='77777777-7777-4777-8777-777777777777';
let browser,detail=null,step='start';const writes=[],unknown=[],external=[],errors=[];
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});const context=await browser.newContext({viewport:{width:1600,height:1000},serviceWorkers:'block'});
 await context.addInitScript(({actor,wid})=>{sessionStorage.setItem('pao.access_token','fixture-only-token');sessionStorage.setItem('pao.workspace.'+actor,wid)},{actor,wid});
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());let body;
  if(url.origin!==base){external.push(url.origin);return route.abort()}
  if(url.pathname==='/api/weather')return route.fulfill({status:200,json:{}});
  if(!url.pathname.startsWith('/v1/'))return route.continue();
  if(request.method()!=='GET'){
   const data=request.postDataJSON();writes.push({path:url.pathname,data});
   assert.equal(request.method(),'POST');assert.ok(['/v1/studio/definitions',`/v1/studio/definitions/${id}/versions`].includes(url.pathname));
   if(!detail){
    assert.equal(data.kind,'agents');assert.deepEqual(data.payload.model_preference,{provider:'openrouter',model:'fixture-B',installation_resource_id:resource,reasoning_effort:'high'});
    detail={definition:{id,workspace_id:wid,owner_id:actor,kind:'agents',name:data.name,slug:data.slug,seed:false,archived:false,revision:1,category:'other',published_version_id:null,latest_version_id:'version-1'},versions:[],events:[]};
   }else{assert.equal(data.payload.model_preference,null);detail.definition.revision++;}
   detail.versions.unshift({id:'version-'+detail.definition.revision,ordinal:detail.definition.revision,status:'draft',payload:structuredClone(data.payload),hash:'a'.repeat(64)});
   body=detail;
  }else if(url.pathname==='/v1/me')body={id:actor,email:'fixture@pao.test',workspaces:[{id:wid,name:'Doanh nghiệp thử',role:'owner'}]};
  else if(url.pathname.endsWith('/context'))body={id:wid,name:'Doanh nghiệp thử',role:'owner'};
  else if(['/v1/sessions','/v1/agents','/v1/brands','/v1/skills'].includes(url.pathname))body=[];
  else if(url.pathname==='/v1/studio/skill-catalog')body={items:detail?[detail.definition]:[],has_more:false};
  else if(url.pathname==='/v1/studio/definitions')body={definitions:detail?[detail.definition]:[]};
  else if(url.pathname==='/v1/studio/definitions/'+id)body=detail;
  else if(url.pathname==='/v1/engines')body={available:true,scope:'installation',engines:[{provider:'openrouter',installation_resource_id:resource,error:null,local:false,models:['fixture-A','fixture-B'],model_details:['fixture-A','fixture-B'].map(model=>({model,display_name:model,reasoning_efforts:['low','high'],default_effort:'low'}))}]};
  else if(url.pathname.endsWith('/business-planning/profile'))body={item:null};
  else if(url.pathname.endsWith('/business-planning/status'))body={available:false,can_manage:false};
  else if(['/v1/voice/status','/v1/automation/status','/v1/telegram/status','/v1/ads/write-status'].includes(url.pathname))body={enabled:false,configured:false,delivery_issues:[]};
  else if(url.pathname==='/v1/ads/autopilot/status')body={global_enabled:false,meta_enabled:false};
  else if(url.pathname==='/v1/platform/catalog')body={features:[],integrations:[],model_providers:[],javis_compatibility:{}};
  else{unknown.push(request.method()+':'+url.pathname);return route.fulfill({status:404,json:{detail:'fixture_missing'}})}
  return route.fulfill({status:200,json:structuredClone(body)});
 });
 const page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.goto(base+'/knowledge?tab=skills');await page.getByRole('button',{name:'Soạn agent mới',exact:true}).click();
  const editor=page.getByRole('form',{name:'Biên tập skill hoặc agent'});
  await editor.getByLabel('Tên hiển thị',{exact:true}).fill('Agent thiết kế');await editor.getByLabel('Mã gọi (chữ thường, số và dấu gạch ngang)',{exact:true}).fill('design-fixture');await editor.getByLabel('Hướng dẫn chuyên môn',{exact:true}).fill('Soạn mô tả thiết kế bằng văn bản.');
  step='select independent model and High';await editor.getByLabel('Model của agent',{exact:true}).selectOption({label:'openrouter · fixture-B'});await editor.getByLabel('Model của agent — mức suy luận',{exact:true}).selectOption('high');
  await editor.getByRole('button',{name:'Lưu bản nháp',exact:true}).click();await editor.getByText(/Phiên bản 1 · Bản nháp/).waitFor();
  assert.equal(await editor.getByLabel('Model của agent — mức suy luận',{exact:true}).inputValue(),'high');
  const old=JSON.stringify(detail.versions[0]);
  step='inherit creates a new draft, not a repin';await editor.getByLabel('Model của agent',{exact:true}).selectOption('');await editor.getByRole('button',{name:'Lưu phiên bản nháp mới',exact:true}).click();await editor.getByText(/Phiên bản 2 · Bản nháp/).waitFor();assert.equal(JSON.stringify(detail.versions[1]),old);
  for(const theme of ['light','dark']){
   if(await page.locator('html').getAttribute('data-theme')!==theme)await page.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
   for(const width of [1600,390,320]){await page.setViewportSize({width,height:1000});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);}
  }
  assert.equal(writes.length,2);assert.deepEqual(unknown,[]);assert.deepEqual(external,[]);assert.deepEqual(errors,[]);
  const result={pass:true,fixture_only:true,agent_model_and_effort_saved:true,inherit_new_version:true,old_definition_unchanged:true,backend_forwarded:0,provider_calls:0,fixture_mutations:2,themes:['light','dark'],widths:[1600,390,320]};
  fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));
 }catch(error){await page.screenshot({path:path.join(folder,'failure.png'),fullPage:true,animations:'disabled'});fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify({pass:false,step,error:error.message,unknown,external,errors},null,2));throw error}
 finally{await context.close()}
})().catch(error=>{console.error(error.message);process.exitCode=1}).finally(async()=>{await browser?.close()});
