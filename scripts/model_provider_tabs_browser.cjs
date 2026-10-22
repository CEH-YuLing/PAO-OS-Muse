// UI-only fixture acceptance: no request is forwarded to a real backend/provider.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const base=process.env.PAO_FRONTEND_URL||'http://127.0.0.1:3200';
assert.ok(/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
const root=path.resolve(__dirname,'..'),folder=path.join(root,'.runtime','model-provider-tabs-browser-'+Date.now());fs.mkdirSync(folder);
const wid='11111111-1111-4111-8111-111111111111',second='33333333-3333-4333-8333-333333333333',viewer='44444444-4444-4444-8444-444444444444',actor='22222222-2222-4222-8222-222222222222';
const member=(id)=>({id,name:id===wid?'Doanh nghiệp thử A':id===second?'Doanh nghiệp thử B':'Doanh nghiệp chỉ xem',role:id===viewer?'viewer':'owner'});
const providers=['openai','anthropic','gemini','openrouter'].map((provider,i)=>({provider,name:['OpenAI','Anthropic','Google Gemini','OpenRouter'][i],configured:false,is_default:false,status:'available',model:null,model_count:0,key_hint:null,last_checked_at:null,last_error:null}));
const saved=new Map([wid,second,viewer].map(id=>[id,structuredClone(providers)]));
let step='start',browser,release,releaseApi,holdApi=false,heldApi=false,lost=false,hold=false,held=false,bad=false,unavailable=false;
const errors=[],outside=[],writes=[],unknown=[],cliReads=[];
const nativeWrites=[],nativeModels=new Map();
const sharedFixture=process.argv.includes('--shared-resources'),resourceWrites=[];
const connectFixture=process.argv.includes('--connect-chat'),personalWrites=[];
let ownReady=false,ownRevision=2,lostOwnAck=false;
const museFixture=process.argv.includes('--muse-only'),museWrites=[];
let museRevision=0,museConnected=false,museLoginState='none',museLostAck=false;
const museView=workspace=>({revision:museRevision,connected:museConnected,can_manage:workspace!==viewer,
 models:museConnected?[{model:'muse-fixture',display_name:'Muse thử nghiệm',reasoning_efforts:['low','high'],default_effort:'high'}]:[],
 account_state:museConnected?'accountLogin':'loggedOut',scope:'installation',connection_mode:'catalog_only',inference_enabled:false,inference_verified:false,credentials_stored_in_PAO:false});
const resources=[{provider:'openrouter',installation_resource_id:'66666666-6666-4666-8666-666666666666',revision:1,enabled:false,is_default:false,default_model:'fixture-first',models:['fixture-first','fixture-second'],error:'installation_ai_resource_disabled'}];
const nativeView=workspace=>({workspace_id:workspace,actor_id:actor,provider:'antigravity_native',scope:'local_personal_machine_session',credentials_stored_in_PAO:false,inference_enabled:false,inference_called:false,provider_support_confirmed:false,status:nativeModels.has(workspace)?'catalog_available':'not_checked',models:nativeModels.get(workspace)||[],busy:false});
const responseRow=(workspace)=>({id:'55555555-5555-4555-8555-555555555555',workspace_id:workspace,owner_id:actor,provider:'codex_cli',model:workspace===wid?'fixture-model-A':'fixture-model-B',version:2,status:connectFixture?'connected':'pending',authentication_ready:connectFixture,profile_operation_pending:false,credentials_stored_in_PAO:false,scope:'local_personal_self_only',tools_enabled:false,activation_required:true,device_id:'must-not-retain',setup_help:'must-not-retain'});
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1050},serviceWorkers:'block'});
 await context.addInitScript(({actor,wid})=>{sessionStorage.setItem('pao.access_token','fixture-only-token');if(!sessionStorage.getItem('pao.workspace.'+actor))sessionStorage.setItem('pao.workspace.'+actor,wid)},{actor,wid});
 await context.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.origin!==base){outside.push(url.origin);return route.abort()}
  if(url.pathname==='/api/weather')return route.fulfill({status:200,json:{city:'Hạ Long',current:{temperature_2m:27,relative_humidity_2m:70,weather_code:2,wind_speed_10m:9,precipitation_probability:20}}});
  if(!url.pathname.startsWith('/v1/'))return route.continue();
  if(url.pathname==='/v1/muse-client/login'){
   const workspace=url.searchParams.get('workspace_id');assert.ok([wid,second,viewer].includes(workspace));
   if(workspace===viewer)return route.fulfill({status:403,json:{detail:'muse_installation_manager_required'}});
   if(req.method()==='POST'){museWrites.push('login');museLoginState='pending'}
   if(req.method()==='DELETE'){museWrites.push('cancel');museLoginState='cancelled'}
   return route.fulfill({status:200,json:{status:museLoginState,profile:'pao_isolated',credentials_stored_in_PAO:false,
    ...(museLoginState==='pending'?{verification_url:'https://auth.meta.com/device',user_code:'FIXTURE'}:{})}});
  }
  if(url.pathname==='/v1/muse-client'){
   const workspace=url.searchParams.get('workspace_id');assert.ok([wid,second,viewer].includes(workspace));
   if(req.method()!=='GET'){
    assert.notEqual(workspace,viewer);const data=req.postDataJSON();assert.equal(data.expected_revision,museRevision);assert.match(data.request_key,/^[a-f0-9-]{36}$/);
    assert.ok(['POST','DELETE'].includes(req.method()));museWrites.push(req.method());museRevision++;museConnected=req.method()==='POST';
    if(museLostAck){museLostAck=false;return route.abort('failed')}
   }
   return route.fulfill({status:200,json:museView(workspace)});
  }
  if(connectFixture&&url.pathname.endsWith('/cli-connections/55555555-5555-4555-8555-555555555555/models')){
   assert.equal(req.method(),'POST');assert.deepEqual(req.postDataJSON(),{version:2});
   return route.fulfill({status:200,json:{workspace_id:wid,actor_id:actor,connection_id:'55555555-5555-4555-8555-555555555555',
    version:2,current_model:'fixture-model-A',models:[{model:'fixture-model-A',is_default:true},{model:'fixture-model-B',is_default:false}],
    inference_called:false,consent_required:false,scope:'local_personal_self_only'}});
  }
  if(connectFixture&&url.pathname.endsWith('/personal-cli')){
   const workspace=url.pathname.split('/')[3],row=responseRow(workspace);
   if(req.method()!=='GET'){
    assert.equal(req.method(),'PUT');const data=req.postDataJSON();personalWrites.push(data);
    assert.equal(data.expected_revision,ownRevision);assert.equal(data.connection_id,row.id);
    assert.equal(data.make_default,true);assert.equal(data.allow_personal_inference_ack,true);
    assert.equal(data.enabled,true);assert.equal(data.grantee_id,undefined);
    ownRevision++;ownReady=true;if(lostOwnAck){lostOwnAck=false;return route.abort('failed')}
   }
   return route.fulfill({status:200,json:{workspace_id:workspace,actor_id:actor,revision:ownRevision,enabled:true,
    make_default:true,ready:ownReady,connection_id:row.id,connections:[{id:row.id,model:row.model,status:row.status,
    authentication_ready:row.authentication_ready,operation_pending:false}],scope:'local_personal_self_only',
    tools_enabled:false,provider_calls:false,expires_at:null}});
  }
  const nativeMatch=/^\/v1\/workspaces\/([^/]+)\/antigravity-native(?:\/(connect|disconnect|test))?$/.exec(url.pathname);
  if(nativeMatch){
   const workspace=nativeMatch[1];assert.ok([wid,second].includes(workspace));
   if(req.method()==='POST'){
    nativeWrites.push(nativeMatch[2]);
    if(nativeMatch[2]==='test'){assert.deepEqual(req.postDataJSON(),{acknowledge_local_session:true,acknowledge_unsupported_consumer_wrapper:true,acknowledge_fixed_model_test:true});return route.fulfill({status:409,json:{detail:'antigravity_native_tools_not_disabled'}})}
    if(nativeMatch[2]==='connect'){assert.deepEqual(req.postDataJSON(),{acknowledge_local_session:true,acknowledge_unsupported_consumer_wrapper:true});nativeModels.set(workspace,['gemini-native-fixture','claude-native-fixture'])}
    else {assert.equal(nativeMatch[2],'disconnect');nativeModels.delete(workspace)}
   }else assert.equal(req.method(),'GET');
   return route.fulfill({status:200,json:nativeView(workspace)});
  }
  if(req.method()!=='GET'){
   if(sharedFixture&&url.pathname==='/v1/installation-ai/'+resources[0].installation_resource_id){
    const data=req.postDataJSON(),row=resources[0];resourceWrites.push(data);assert.equal(data.expected_revision,row.revision);assert.match(data.request_key,/^[a-f0-9-]{36}$/);assert.equal(req.method(),'PUT');
    Object.assign(row,{enabled:data.enabled,is_default:data.is_default,default_model:data.default_model,revision:row.revision+1,error:null});
    return route.fulfill({status:200,json:{saved_revision:row.revision,replayed:false,provider_calls:false}});
   }
   const match=/^\/v1\/model-providers\/(openai|anthropic|gemini|openrouter)(\/(connect|model|default|test))?$/.exec(url.pathname);
   if(!match){unknown.push(req.method()+':'+url.pathname);return route.fulfill({status:403,json:{detail:'fixture_readonly'}})}
   const data=req.postData()?req.postDataJSON():{},scope=data.workspace_id||url.searchParams.get('workspace_id');
   assert.ok([wid,second].includes(scope));
   const nonce=req.headers()['idempotency-key'];if(['connect','model'].includes(match[3]))assert.match(nonce||'',/^[a-f0-9-]{36}$/);
   writes.push({method:req.method(),path:url.pathname,workspace:scope});
   const list=saved.get(scope),row=list.find(x=>x.provider===match[1]);
   if(match[3]==='connect'){
    assert.match(data.api_key,/^fixture-/);Object.assign(row,{configured:true,status:'connected',model:'fixture-first',model_count:2,key_hint:'••••real'});
    if(lost){lost=false;return route.abort('failed')}
    return route.fulfill({status:200,json:{...row,models:['fixture-first','fixture-second']}});
   }
   if(match[3]==='model'){assert.ok(['fixture-first','fixture-second'].includes(data.model));row.model=data.model;return route.fulfill({status:200,json:row})}
   if(match[3]==='default'){for(const item of list)item.is_default=item===row;return route.fulfill({status:200,json:row})}
   if(match[3]==='test')return route.fulfill({status:200,json:{ok:true,provider:row.provider,model:row.model}});
   assert.equal(req.method(),'DELETE');Object.assign(row,providers.find(x=>x.provider===row.provider));return route.fulfill({status:204});
  }
  let body;
  if(url.pathname==='/v1/me')body={id:actor,email:'fixture@example.test',workspaces:[member(wid),member(second),member(viewer)]};
  else if(/^\/v1\/workspaces\/[^/]+\/context$/.test(url.pathname))body=member(url.pathname.split('/')[3]);
  else if(['/v1/agents','/v1/sessions','/v1/brands'].includes(url.pathname))body=[];
  else if(url.pathname.endsWith('/business-planning/status'))body={available:false,can_manage:false};
  else if(url.pathname==='/v1/integrations/meta/connection'||url.pathname==='/v1/integrations/google-ads/connection')body={configured:false,status:'disconnected',scopes:[]};
  else if(url.pathname==='/v1/telegram/status')body={enabled:false,configured:false,mode:'polling',allowed_peers:0,delivery_issues:[]};
  else if(url.pathname==='/v1/voice/status')body={enabled:false,stt_ready:false,tts_ready:false,stt_device:'cpu',stt_compute_type:'int8',tts_provider:'none',max_seconds:30};
  else if(url.pathname==='/v1/automation/status')body={enabled:false,address:null,namespace:'default',task_queue:'fixture'};
  else if(url.pathname==='/v1/ads/write-status')body={enabled:false,dry_run_default:true,max_budget_change_pct:20};
  else if(url.pathname==='/v1/ads/autopilot/status')body={global_enabled:false,meta_enabled:false,default_mode:'observer',phase:1};
  else if(url.pathname==='/v1/platform/catalog')body={features:[],integrations:[],model_providers:[],javis_compatibility:{}};
  else if(url.pathname==='/v1/model-providers')body=saved.get(url.searchParams.get('workspace_id'))||providers;
  else if(url.pathname==='/v1/installation-ai')body={enabled:true,can_manage:url.searchParams.get('workspace_id')!==viewer,resources:sharedFixture?resources:[],provider_calls:false};
  else if(/^\/v1\/model-providers\/(openai|anthropic|gemini|openrouter)\/models$/.test(url.pathname)){
   assert.match(req.headers()['idempotency-key']||'',/^[a-f0-9-]{36}$/);
   const row=saved.get(url.searchParams.get('workspace_id')).find(x=>x.provider===url.pathname.split('/')[3]);body={provider:row.provider,models:['fixture-first','fixture-second']};
   if(holdApi){holdApi=false;heldApi=true;await new Promise(resolve=>{releaseApi=resolve})}
  }
  else if(url.pathname.endsWith('/cli-connections/login-capabilities'))body={provider:'codex_cli',browser_login_enabled:connectFixture,scope:'local_personal_self_only',managed_by:'official_codex_app_server',subscription_sharing_enabled:false,tools_enabled:false};
  else if(url.pathname.endsWith('/personal-cli'))body={workspace_id:url.pathname.split('/')[3],actor_id:actor,revision:0,enabled:false,make_default:false,ready:false,connection_id:null,connections:[],scope:'local_personal_self_only',tools_enabled:false,provider_calls:false,expires_at:null};
  else if(url.pathname.endsWith('/cli-connections')){
   const workspace=url.pathname.split('/')[3];cliReads.push(workspace);
   if(unavailable)return route.fulfill({status:503,json:{detail:'cli_connections_disabled'}});
   if(hold){hold=false;held=true;await new Promise(resolve=>{release=resolve})}
   body={items:[responseRow(bad?second:workspace)],external_calls:false};
  }else{unknown.push(url.pathname);return route.fulfill({status:404,json:{detail:'fixture_missing'}})}
  await route.fulfill({status:200,json:body,headers:{'Cache-Control':'no-store'}}).catch(()=>{});
 });
 const p=await context.newPage();p.on('pageerror',e=>errors.push(e.message));p.on('console',m=>{if(m.type()==='error'&&/hydration|hydrated|unique.*key|Cannot update|uncontrolled|controlled input/i.test(m.text()))errors.push(m.text())});p.setDefaultTimeout(20000);
 const tab=id=>p.getByTestId('model-connection-tab-'+id),clients=()=>p.getByLabel('Kết nối Client AI',{exact:true});
 const go=async query=>{await p.goto(base+'/settings?tab=ai&section=providers'+(query||''));await tab('client').waitFor();await p.locator('.st-loading').waitFor({state:'hidden'})};
 const selected=async id=>{await p.waitForFunction(id=>document.getElementById('model-connection-tab-'+id)?.getAttribute('aria-selected')==='true',id)};
 const read=()=>clients().getByRole('button',{name:'Đọc hồ sơ Codex đã lưu',exact:true});
 const choose=async id=>{await p.locator('.pao-topbar-context select').selectOption(id);await tab('client').waitFor();await p.locator('.st-loading').waitFor({state:'hidden'});await tab('client').click();await selected('client')};
 try{
  step='default and explicit read';await go('');await selected('client');
  if(museFixture){
   const muse=()=>clients().getByLabel('Client Muse',{exact:true});
   const connect=()=>muse().getByRole('button',{name:'Kết nối Muse',exact:true});
   await connect().waitFor();await p.waitForFunction(()=>!document.querySelector('[aria-label="Kết nối Muse"] button[aria-label="Kết nối Muse"]')?.disabled);
   assert.equal(await clients().locator('.mp-client-grid>article').count(),4);assert.deepEqual(museWrites,[]);
   step='official isolated login no password or key';await connect().click();
   await muse().getByRole('link',{name:'Mở trang đăng nhập Muse chính chủ'}).waitFor();
   assert.equal(await muse().locator('input[type=password]').count(),0);assert.equal(await muse().getByRole('link',{name:'Mở trang đăng nhập Muse chính chủ'}).getAttribute('href'),'https://auth.meta.com/device');
   assert.deepEqual(museWrites,['login']);
   museLoginState='granted';await muse().getByRole('alert').filter({hasText:'Đăng nhập Muse thành công'}).waitFor();
   step='explicit catalog connect';await connect().click();await muse().getByText('Đã kết nối danh mục Muse · chưa bật hội thoại',{exact:true}).waitFor();
   await muse().getByText('Mô hình và mức suy luận từ Muse',{exact:true}).click();await muse().getByText('Muse thử nghiệm',{exact:true}).waitFor();
   assert.deepEqual(museWrites,['login','POST']);
   step='lost ACK does not retry native connection';museLostAck=true;await connect().click();await muse().getByRole('alert').waitFor();assert.deepEqual(museWrites,['login','POST','POST']);
   await muse().getByRole('button',{name:'Đọc lại trạng thái đã lưu',exact:true}).click();await muse().getByText('Đã kết nối danh mục Muse · chưa bật hội thoại',{exact:true}).waitFor();assert.equal(museWrites.length,3);
   step='viewer and cross-workspace metadata';await choose(second);await muse().getByText('Đã kết nối danh mục Muse · chưa bật hội thoại',{exact:true}).waitFor();await choose(viewer);await connect().waitFor();assert.equal(await connect().isDisabled(),true);await choose(wid);
   step='disconnect cancel and confirm';p.once('dialog',d=>d.dismiss());await muse().getByRole('button',{name:'Ngắt Muse khỏi PAO',exact:true}).click();assert.equal(museWrites.length,3);
   p.once('dialog',d=>d.accept());await muse().getByRole('button',{name:'Ngắt Muse khỏi PAO',exact:true}).click();await muse().getByText('Chưa kết nối Muse trong PAO',{exact:true}).waitFor();assert.equal(museWrites.length,4);
   for(const theme of ['light','dark']){
    if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
    for(const width of [1440,390,320]){await p.setViewportSize({width,height:1050});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await p.screenshot({path:path.join(folder,'muse-'+theme+'-'+width+'.png'),fullPage:true,animations:'disabled'})}
   }
   assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);assert.deepEqual(outside,[]);
   const result={pass:true,fixture_only:true,muse_login:true,catalog_only:true,inference_enabled:false,lost_ACK_no_retry:true,viewer_guard:true,disconnect_confirmation:true,themes:['light','dark'],widths:[1440,390,320],backend_requests_forwarded:0,real_mutations:0,provider_calls:0};
   fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));return;
  }
  if(connectFixture){
   assert.equal(personalWrites.length,0);assert.deepEqual(cliReads,[]);
   const button=()=>p.getByRole('button',{name:'Kết nối Codex',exact:true});
   const dialog=()=>p.getByRole('dialog',{name:'Kết nối Codex',exact:true});
   const ready=()=>dialog().getByText('Đã kết nối để chọn trong PAO AI.',{exact:false});
   step='one Connect reuses login and binds current profile';await button().click();await ready().waitFor();
   assert.equal(personalWrites.length,1);assert.equal(await dialog().locator('input[type=password]').count(),0);
   await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
   step='repeated Connect reads existing ready setting without another PUT';await button().click();await ready().waitFor();assert.equal(personalWrites.length,1);
   await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
   step='lost ACK never retries or changes default';ownReady=false;lostOwnAck=true;await button().click();await dialog().getByRole('alert').waitFor();
   assert.equal(personalWrites.length,2);await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
   await button().click();await ready().waitFor();assert.equal(personalWrites.length,2);
   for(const theme of ['dark','light']){
    await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
    if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
    await button().click();await ready().waitFor();
    for(const width of [1440,390,320]){await p.setViewportSize({width,height:1000});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);if(width!==390)await p.screenshot({path:path.join(folder,'connect-'+theme+'-'+width+'.png'),animations:'disabled'})}
   }
   assert.equal(personalWrites.length,2);assert.deepEqual(writes,[]);assert.deepEqual(unknown,[]);assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);
   const result={pass:true,fixture_only:true,explicit_connect:true,reuses_existing_login:true,repins_after_relogin:true,
    ready_connect_no_duplicate_write:true,lost_ACK_no_retry:true,keeps_default:true,backend_requests_forwarded:0,
    real_mutations:0,external_provider_calls:0,fixture_policy_writes:personalWrites.length,themes:['dark','light'],widths:[1440,390,320]};
   fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));return;
  }
  assert.deepEqual(await p.getByRole('tablist',{name:'Phương thức kết nối mô hình'}).getByRole('tab').allTextContents(),['Kết nối qua ClientƯu tiên gói thuê bao','Kết nối qua APIKhóa API của doanh nghiệp']);
  assert.equal(await clients().locator('article').count(),4);assert.equal(await clients().locator('.mp-client-grid input').count(),0);assert.equal(await clients().locator('input[type=password]').count(),0);assert.equal(await p.getByLabel('Cài đặt mô hình đám mây',{exact:true}).count(),0);assert.deepEqual(cliReads,[]);
  for(const name of ['Codex','Claude Code'])assert.equal(await clients().getByRole('button',{name:'Kết nối '+name,exact:true}).isDisabled(),true);
  step='native Client uses current PAO session without password';
  const native=()=>clients().getByLabel('Client Antigravity',{exact:true});
  assert.equal(await native().getByRole('button',{name:'Kết nối',exact:true}).isEnabled(),true);
  p.once('dialog',d=>d.dismiss());await native().getByRole('button',{name:'Kết nối',exact:true}).click();assert.equal(nativeWrites.length,0);
  p.once('dialog',d=>d.accept());await native().getByRole('button',{name:'Kết nối',exact:true}).click();await native().getByRole('status').waitFor();assert.equal(nativeWrites.length,1);assert.equal(await p.locator('input[type=password]').count(),0);
  await native().getByText('Danh sách model từ CLI',{exact:true}).click();await native().getByText('gemini-native-fixture',{exact:true}).waitFor();
  step='native smoke blocked before prompt, no retry or password';
  p.once('dialog',d=>d.dismiss());await native().getByRole('button',{name:'Thử model an toàn',exact:true}).click();assert.equal(nativeWrites.filter(x=>x==='test').length,0);
  p.once('dialog',d=>d.accept());await native().getByRole('button',{name:'Thử model an toàn',exact:true}).click();await native().getByRole('alert').filter({hasText:'trước khi gửi câu hỏi'}).waitFor();assert.equal(nativeWrites.filter(x=>x==='test').length,1);assert.equal(await native().getByRole('button',{name:'Thử model an toàn',exact:true}).isEnabled(),true);
  await native().getByRole('button',{name:'Ngắt trong PAO',exact:true}).click();await native().getByRole('button',{name:'Kết nối',exact:true}).waitFor();assert.equal(await native().getByText('gemini-native-fixture',{exact:true}).count(),0);
  assert.equal(await read().count(),0);assert.equal(await clients().locator('.pao-personal-codex,.mp-profile-status').count(),0);assert.deepEqual(cliReads,[]);
  step='API form retained and draft guard';await tab('api').click();await selected('api');
  const api=()=>p.getByLabel('Cài đặt mô hình đám mây',{exact:true}),card=id=>api().getByLabel('mô hình '+id,{exact:true});
  await card('openai').waitFor();assert.equal(await api().locator('.cm-grid>article').count(),4);assert.deepEqual(await api().locator('.cm-card-heading h3').allTextContents(),['OpenAI','Claude (Anthropic)','Google Gemini','OpenRouter']);
  const key=p.getByLabel('Khóa API OpenAI',{exact:true}),draft='fixture-unsaved-key-not-real';await key.fill(draft);
  p.once('dialog',d=>d.dismiss());await tab('client').click();await selected('api');assert.equal(await key.inputValue(),draft);
  p.once('dialog',d=>d.accept());await tab('client').click();await selected('client');assert.equal(await p.locator('input[type=password]').count(),0);
  await tab('api').click();await key.waitFor();assert.equal(await key.inputValue(),'');assert.ok(!(await p.evaluate(()=>JSON.stringify({...sessionStorage,...localStorage}))).includes(draft));assert.ok(!p.url().includes(draft));
  step='history and deep link';await p.goBack();await selected('client');await p.goForward();await selected('api');await p.reload();await selected('api');await go('&model_connection=constructor');await selected('client');
  step='keyboard and aria';await tab('client').focus();await p.keyboard.press('ArrowRight');await selected('api');await p.keyboard.press('Home');await selected('client');await p.keyboard.press('End');await selected('api');
  assert.equal(await tab('api').getAttribute('aria-controls'),'model-connection-panel-api');assert.equal(await p.locator('#model-connection-panel-api').getAttribute('aria-labelledby'),'model-connection-tab-api');
  step='save consent, multiple drafts, persisted masked state';await key.waitFor();await key.fill('fixture-openai-key-not-real');const secondKey=p.getByLabel('Khóa API Anthropic',{exact:true});await secondKey.fill('fixture-anthropic-key-not-real');
  const save=id=>card(id).getByRole('button',{name:'Lưu cấu hình',exact:true}),remove=id=>card(id).getByRole('button',{name:'Xóa khóa',exact:true});
  assert.equal(await card('openai').getByText('Đã nhập · chưa lưu',{exact:true}).isVisible(),true);
  p.once('dialog',d=>{assert.match(d.message(),/gọi nhà cung cấp/);d.dismiss()});await save('openai').click();assert.equal(writes.length,0);assert.notEqual(await key.inputValue(),'');
  p.once('dialog',d=>d.accept());await save('openai').click();await api().getByRole('status').filter({hasText:'Đã lưu cấu hình OpenAI'}).waitFor();assert.equal(await key.inputValue(),'');assert.equal(await secondKey.inputValue(),'fixture-anthropic-key-not-real');assert.match(await key.getAttribute('placeholder'),/^••••real/);assert.equal(await card('openai').getByText('Đã lưu khóa',{exact:true}).isVisible(),true);
  await card('anthropic').getByRole('button',{name:'Bỏ khóa chưa lưu',exact:true}).click();await p.reload();await selected('api');await key.waitFor();assert.match(await key.getAttribute('placeholder'),/^••••real/);assert.equal(await key.inputValue(),'');
  for(const [id,name] of [['anthropic','Anthropic'],['gemini','Google Gemini'],['openrouter','OpenRouter']]){await p.getByLabel('Khóa API '+name,{exact:true}).fill('fixture-'+id+'-key-not-real');p.once('dialog',d=>d.accept());await save(id).click();await api().getByRole('status').filter({hasText:'Đã lưu cấu hình '+name}).waitFor();assert.equal(await card(id).getByText('Đã lưu khóa',{exact:true}).isVisible(),true)}
  step='delete cancel, delete confirm and reload';const count=writes.length;p.once('dialog',d=>d.dismiss());await remove('anthropic').click();assert.equal(writes.length,count);p.once('dialog',d=>{assert.match(d.message(),/không tự bị thu hồi/);d.accept()});await remove('anthropic').click();await api().getByRole('status').filter({hasText:'Đã xóa khóa Anthropic'}).waitFor();assert.equal(await card('anthropic').getByText('Chưa lưu khóa',{exact:true}).isVisible(),true);await p.reload();await selected('api');await key.waitFor();assert.equal(await remove('anthropic').isDisabled(),true);
  step='advanced explicit model, default and inference gates';await card('openai').getByText('Mô hình và tùy chọn nâng cao',{exact:true}).click();const consent=()=>card('openai').getByLabel('Đồng ý thông tin mô tả OpenAI',{exact:true});const probe=card('openai').getByRole('button',{name:'Kiểm tra suy luận AI có phí',exact:true});assert.equal(await probe.isDisabled(),true);assert.equal(writes.filter(x=>x.path.endsWith('/test')).length,0);
  await consent().check();await card('openai').getByRole('button',{name:'Tải danh mục mô hình',exact:true}).click();await api().getByRole('status').waitFor();await card('openai').getByLabel('Mô hình lựa chọn OpenAI',{exact:true}).selectOption('fixture-second');await consent().check();await card('openai').getByRole('button',{name:'Lưu mô hình đã chọn',exact:true}).click();await api().getByRole('status').waitFor();assert.equal(await card('openai').getByLabel('Mô hình lựa chọn OpenAI',{exact:true}).inputValue(),'fixture-second');
  await consent().check();await card('openai').getByRole('button',{name:'Đặt mặc định doanh nghiệp',exact:true}).click();await card('openai').getByText('Mặc định doanh nghiệp',{exact:true}).waitFor();await card('openai').getByLabel('Đồng ý suy luận AI OpenAI',{exact:true}).check();await probe.click();await api().getByRole('status').filter({hasText:'Lượt suy luận AI vừa phản hồi'}).waitFor();assert.equal(writes.filter(x=>x.path.endsWith('/test')).length,1);
  step='lost save ACK does not auto retry';lost=true;await p.getByLabel('Khóa API OpenRouter',{exact:true}).fill('fixture-new-openrouter-not-real');const beforeLost=writes.length;p.once('dialog',d=>d.accept());await save('openrouter').click();await api().getByRole('alert').waitFor();assert.equal(await api().locator('input[type=password]').count(),0);assert.equal(writes.length,beforeLost+1);await api().getByRole('button',{name:'Đọc lại trạng thái mô hình',exact:true}).click();await key.waitFor();assert.equal(await card('openrouter').getByText('Đã lưu khóa',{exact:true}).isVisible(),true);assert.equal(writes.length,beforeLost+1);
  step='key not persisted or reflected';const stored=await p.evaluate(()=>JSON.stringify({...sessionStorage,...localStorage}));assert.ok(!stored.includes('key-not-real'));assert.ok(!(await p.locator('body').innerText()).includes('fixture-new-openrouter-not-real'));assert.ok(!p.url().includes('fixture-'));
  step='late API response cannot cross workspace';await card('openai').getByText('Mô hình và tùy chọn nâng cao',{exact:true}).click();await consent().check();holdApi=true;await card('openai').getByRole('button',{name:'Tải danh mục mô hình',exact:true}).click();for(let i=0;i<50&&!heldApi;i++)await new Promise(r=>setTimeout(r,40));assert.ok(heldApi);await choose(second);releaseApi();await tab('api').click();await card('openai').waitFor();assert.equal(await card('openai').getByText('Chưa lưu khóa',{exact:true}).isVisible(),true);assert.equal(await key.inputValue(),'');await choose(wid);
  step='personal grant/profile controls removed in both SME contexts';await tab('client').click();assert.equal(await read().count(),0);await choose(second);assert.equal(await read().count(),0);assert.deepEqual(cliReads,[]);
  step='viewer has no read/config action';await choose(viewer);assert.equal(await read().count(),0);await tab('api').click();await card('openai').waitFor();await p.getByText('Chỉ chủ doanh nghiệp/quản trị viên được cấu hình, tải danh mục và kiểm tra. Dùng mô hình theo quyền được cấp riêng.').first().waitFor();assert.equal(await p.locator('input[type=password]').count(),0);assert.ok(!cliReads.includes(viewer));await choose(wid);
  if(sharedFixture){
   step='installation resource save and no individual grants';
   const shared=()=>p.getByLabel('Tài nguyên AI dùng chung',{exact:true});
   await shared().getByLabel('Model mặc định',{exact:true}).selectOption('fixture-second');
   await shared().getByLabel('Bật tài nguyên dùng chung',{exact:true}).check();
   await shared().getByLabel('Dùng làm mặc định cho hội thoại mới',{exact:true}).check();
   await shared().getByRole('button',{name:'Lưu cấu hình dùng chung',exact:true}).click();
   await shared().getByText('Đã bật trong PAO · chưa kiểm thử model thật · Mặc định bản cài',{exact:true}).waitFor();
   assert.equal(resourceWrites.length,1);assert.equal(resourceWrites[0].default_model,'fixture-second');
   await choose(viewer);await shared().getByLabel('Model mặc định',{exact:true}).waitFor();
   assert.equal(await shared().getByLabel('Model mặc định',{exact:true}).isDisabled(),true);
   assert.equal(await shared().getByRole('button',{name:'Lưu cấu hình dùng chung',exact:true}).count(),0);
   await choose(wid);
  }
  step='light dark desktop and mobile';
  for(const theme of ['light','dark']){
   if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
   for(const width of [1440,390,320]){
    await p.setViewportSize({width,height:1050});
    for(const mode of ['client','api']){await tab(mode).click();await selected(mode);if(mode==='api')await key.waitFor();await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);if(width!==390){await p.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0)});await p.screenshot({path:path.join(folder,theme+'-'+width+'-'+mode+'.png'),fullPage:true,animations:'disabled'});if(width===1440){const geometry=await p.locator('.pao-sidebar').evaluate(el=>({width:el.getBoundingClientRect().width,sidebar:getComputedStyle(el).getPropertyValue('--sidebar'),position:getComputedStyle(el).position}));fs.writeFileSync(path.join(folder,theme+'-geometry.json'),JSON.stringify(geometry))}}}
   }
  }
  assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);assert.deepEqual(unknown,[]);
  const result={pass:true,fixture_only:true,installation_resource_save:sharedFixture,resource_fixture_writes:resourceWrites.length,client_first:true,providers:4,api_providers:4,save_delete_all_cards:true,masked_persisted_state:true,multiple_drafts:true,lost_ACK_no_retry:true,explicit_advanced:true,unsaved_key_guard:true,history_deep_links:true,keyboard:true,scope_and_late_response:true,viewer_guard:true,themes:['light','dark'],widths:[1440,390,320],backend_requests_forwarded:0,fixture_mutations:writes.length,real_mutations:0,external_provider_calls:0,real_client_login:false};fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));
 }catch(e){await p.screenshot({path:path.join(folder,'failure.png'),fullPage:true}).catch(()=>{});fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify({pass:false,step,error:e.message,errors,unknown,outside,writes},null,2));console.error('Failed at '+step+'; evidence '+folder);throw e}
 finally{release?.();releaseApi?.();await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{await browser?.close()});
