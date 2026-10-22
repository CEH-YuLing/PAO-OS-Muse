// No real auth codes, provider requests or backend calls. Own synthetic session only.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),base=process.env.PAO_FRONTEND_URL||'http://127.0.0.1:3212';assert.match(base,/^http:\/\/127\.0\.0\.1:\d+$/);
const accessMode=process.argv.includes('--access');
const folder=path.join(root,'.runtime',(accessMode?'codex-access-browser-':'codex-login-browser-')+Date.now());fs.mkdirSync(folder);
const wid='11111111-1111-4111-8111-111111111111',second='33333333-3333-4333-8333-333333333333',viewer='44444444-4444-4444-8444-444444444444',actor='22222222-2222-4222-8222-222222222222',cid='55555555-5555-4555-8555-555555555555',op='66666666-6666-4666-8666-666666666666';
let row={id:cid,workspace_id:wid,owner_id:actor,provider:'codex_cli',model:'fixture-model',version:2,status:'pending',authentication_ready:false,profile_operation_pending:false,credentials_stored_in_PAO:false,scope:'local_personal_self_only',tools_enabled:false,activation_required:true};
let mode='idle',lost=false,step='start',browser;const writes=[],outside=[],unknown=[],errors=[];
const rid='77777777-7777-4777-8777-777777777777',gid='88888888-8888-4888-8888-888888888888',bid='99999999-9999-4999-8999-999999999999';
let refs=[],grants=[],lostGrant=false,partial=false,pausePreview=false,releasePreview,previewSeen=false;
if(accessMode)row={...row,version:5,status:'connected',authentication_ready:true};
const member=id=>({id,name:id===wid?'Doanh nghiệp thử A':id===second?'Doanh nghiệp thử B':'Doanh nghiệp chỉ xem',role:id===viewer?'viewer':'owner'});
const capabilities={provider:'codex_cli',browser_login_enabled:true,scope:'local_personal_self_only',managed_by:'official_codex_app_server',subscription_sharing_enabled:false,tools_enabled:false};
const login=()=>({operation_id:mode==='idle'?null:op,connection_id:cid,version:row.version,status:mode,expires_in:600,user_code:mode==='awaiting_user'?'ABCD-EFGH':null,verification_url:mode==='awaiting_user'?'https://auth.openai.com/codex/device':null,grant_activated:false,provider_inference_verified:false});
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});const context=await browser.newContext({viewport:{width:1440,height:1050},serviceWorkers:'block'});
 await context.addInitScript(({actor,wid})=>{sessionStorage.setItem('pao.access_token','fixture-only-token');if(!sessionStorage.getItem('pao.workspace.'+actor))sessionStorage.setItem('pao.workspace.'+actor,wid)},{actor,wid});
 await context.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),p=url.pathname;let value;
  if(url.origin!==base){outside.push(url.origin);return route.abort()}
  if(p==='/api/weather')return route.fulfill({status:200,json:{city:'Hạ Long',current:{temperature_2m:27,relative_humidity_2m:70,weather_code:2,wind_speed_10m:9,precipitation_probability:20}}});
  if(!p.startsWith('/v1/'))return route.continue();
  if(accessMode&&p.includes('/connection-inventory')){
   const native='/v1/workspaces/'+wid+'/connection-inventory';let answer;
   if(req.method()==='GET'){
    if(p.endsWith('/options'))answer={members:[{id:actor,email:'owner@example.test',role:'owner'},{id:second,email:'colleague@example.test',role:'operator'}],brands:[{id:bid,name:'Nhãn hàng thử'}],has_more:false};
    else if(p.endsWith('/references'))answer={items:p.startsWith(native)?refs:[],has_more:partial};
    else if(p.endsWith('/grants'))answer={reference:refs[0],items:grants,has_more:false};
    else answer={items:p.startsWith(native)?[{identity:{kind:'cli_model',connection_id:cid,provider:'codex_cli'},stored_status:row.status,config_version:row.version}]:[],has_more:false};
   }else{
    writes.push({path:p,method:req.method()});assert.equal(req.method(),'POST');const data=req.postDataJSON();
    if(p.endsWith('/mapping-preview')){
     assert.equal(data.kind,'cli_model');assert.equal(data.connection_id,cid);assert.equal(data.expected_version,row.version);assert.equal(data.grantee_id,actor);assert.equal(data.permission,'read_only');assert.ok(!data.account_id);
     previewSeen=true;if(pausePreview)await new Promise(resolve=>{releasePreview=resolve});
     answer={preview_hash:'a'.repeat(64),external_calls:false};
    }else if(p.endsWith('/references')){
     assert.equal(data.apply_data_only_ack,true);assert.equal(data.manager_id,actor);assert.equal(data.grantee_id,actor);assert.equal(data.kind,'cli_model');assert.equal(data.ttl_minutes,30);assert.match(data.request_key,/^[a-f0-9-]{36}$/);assert.equal(data.preview_hash,'a'.repeat(64));assert.equal(data.brand_id,bid);
     assert.equal(refs.length,0);const ref={id:rid,workspace_id:wid,kind:'cli_model',source_id:cid,source_version:row.version,provider:'codex_cli',manager_id:actor,revision:1,status:'staged'};
     const grant={id:gid,workspace_id:wid,reference_id:rid,reference_revision:1,grantee_id:actor,brand_id:bid,account_id:null,revision:1,status:'staged',expires_at:new Date(Date.now()+1800000).toISOString(),model_consent_recorded:false};refs=[ref];grants=[grant];answer={reference:ref,grant};
     if(lostGrant){lostGrant=false;return route.abort('failed')}
    }else if(p.endsWith('/activate-model')){
     assert.equal(data.reference_revision,1);assert.equal(data.grant_revision,1);assert.equal(data.capability,'model_inference');assert.equal(data.allow_model_inference_ack,true);assert.match(data.request_key,/^[a-f0-9-]{36}$/);grants[0].model_consent_recorded=true;answer={consent_recorded:true,tools_enabled:false,selection_required:true};
    }else if(p.endsWith('/revoke')){assert.equal(data.reference_revision,1);assert.equal(data.grant_revision,1);grants[0].status='revoked';grants[0].revision++;answer={reference:refs[0],grants}}
    else{unknown.push(req.method()+':'+p);return route.fulfill({status:403,json:{detail:'fixture_denied'}})}
   }
   return route.fulfill({status:200,json:answer});
  }
  if(req.method()!=='GET'){
   writes.push({path:p,method:req.method()});const data=req.postDataJSON();assert.equal(req.method(),'POST');
   if(p.endsWith('/prepare')){assert.equal(data.version,row.version);row.version++;row.status='pending';row.authentication_ready=false;value={...row}}
   else if(p.endsWith('/login/cancel')){assert.equal(data.version,row.version);assert.equal(data.operation_id,op);row.version++;row.status='error';row.profile_operation_pending=false;mode='idle';value={connection_id:cid,version:row.version,status:'cancelled',cleanup_verified:true,provider_logout_performed:false,grant_activated:false}}
   else if(p.endsWith('/login')){assert.equal(data.version,row.version);assert.equal(data.allow_personal_login,true);assert.match(data.request_key,/^[a-f0-9-]{36}$/);row.version++;row.profile_operation_pending=true;mode='awaiting_user';if(lost){lost=false;return route.abort('failed')}value={...login(),status:'starting',user_code:null,verification_url:null}}
   else if(p.endsWith('/disconnect')){assert.equal(data.version,row.version);row.version++;row.status='disconnected';row.authentication_ready=false;mode='idle';value={...row}}
   else{unknown.push(req.method()+':'+p);return route.fulfill({status:403,json:{detail:'fixture_denied'}})}
   return route.fulfill({status:200,json:value});
  }
  if(p==='/v1/me')value={id:actor,email:'fixture@example.test',workspaces:[member(wid),member(second),member(viewer)]};
  else if(p.endsWith('/context'))value=member(p.split('/')[3]);
  else if(['/v1/agents','/v1/sessions','/v1/brands'].includes(p))value=[];
  else if(p.endsWith('/business-planning/status'))value={available:false,can_manage:false};
  else if(p==='/v1/integrations/meta/connection'||p==='/v1/integrations/google-ads/connection')value={configured:false,status:'disconnected',scopes:[]};
  else if(p==='/v1/telegram/status')value={enabled:false,configured:false,mode:'polling',allowed_peers:0,delivery_issues:[]};
  else if(p==='/v1/voice/status')value={enabled:false,stt_ready:false,tts_ready:false,stt_device:'cpu',stt_compute_type:'int8',tts_provider:'none',max_seconds:30};
  else if(p==='/v1/automation/status')value={enabled:false,address:null,namespace:'default',task_queue:'fixture'};
  else if(p==='/v1/ads/write-status')value={enabled:false,dry_run_default:true,max_budget_change_pct:20};
  else if(p==='/v1/ads/autopilot/status')value={global_enabled:false,meta_enabled:false,default_mode:'observer',phase:1};
  else if(p==='/v1/platform/catalog')value={features:[],integrations:[],model_providers:[],javis_compatibility:{}};
  else if(p==='/v1/model-providers')value=['openai','anthropic','gemini','openrouter'].map(provider=>({provider,name:provider,configured:false,is_default:false,status:'available',model:null,model_count:0,key_hint:null,last_checked_at:null,last_error:null}));
  else if(p.endsWith('/login-capabilities'))value=capabilities;
  else if(p.endsWith('/cli-connections'))value={items:p.includes(wid)?[{...row}]:[],external_calls:false};
  else if(p.endsWith('/login'))value=login();
  else{unknown.push(p);return route.fulfill({status:404,json:{detail:'fixture_missing'}})}
  return route.fulfill({status:200,json:value,headers:{'Cache-Control':'no-store'}});
 });
 const p=await context.newPage();p.setDefaultTimeout(20000);p.on('pageerror',e=>errors.push(e.message));p.on('console',m=>{if(m.type()==='error'&&/hydration|unique.*key|Cannot update|uncontrolled|controlled input/i.test(m.text()))errors.push(m.text())});
 const button=()=>p.getByRole('button',{name:'Kết nối Codex',exact:true}),dialog=()=>p.getByRole('dialog',{name:'Kết nối Codex',exact:true});
 const waitCode=()=>dialog().getByLabel('Mã xác nhận Codex',{exact:true}).waitFor();
 const connect=async()=>{p.once('dialog',d=>{assert.match(d.message(),/Đăng nhập Codex riêng/);d.accept()});await button().click();await waitCode()};
 const cancel=async()=>{p.once('dialog',d=>d.accept());await dialog().getByRole('button',{name:'Hủy / phục hồi phiên',exact:true}).click();await dialog().getByRole('button',{name:'Đăng nhập Codex',exact:true}).waitFor()};
 try{
  if(accessMode){
   const fold=()=>p.locator('details').filter({has:p.locator(':scope > summary').filter({hasText:'Quyền dùng Codex'})}).first();
   const panel=()=>p.getByRole('region',{name:'Quyền dùng Codex cá nhân',exact:true});
   const openAccess=async()=>{await fold().locator(':scope > summary').click();await panel().getByLabel('Kết nối cấp quyền',{exact:true}).waitFor();await p.waitForFunction(()=>!document.querySelector('[aria-label="Quyền dùng Codex cá nhân"] [role="status"]')?.textContent?.includes('Chưa đủ'))};
   step='access does not mutate on mount';await p.goto(base+'/settings?tab=ai&section=providers');await button().waitFor();assert.equal(writes.length,0);await openAccess();assert.equal(writes.length,0);
   assert.equal(await panel().getByLabel('Nhân viên được cấp Codex cá nhân',{exact:true}).inputValue(),actor);assert.equal(await panel().getByLabel('Nhân viên được cấp Codex cá nhân',{exact:true}).isDisabled(),true);assert.equal(await panel().getByLabel('Nhân viên được cấp Codex cá nhân',{exact:true}).locator('option').count(),2);
   const stageButton=()=>panel().getByRole('button',{name:'Lưu quyền chờ kích hoạt',exact:true});
   const dataAck=()=>panel().getByRole('checkbox').filter({hasText:''}).first();
   step='scope and TTL explicit, ACK resets on edits';await panel().getByLabel('Kết nối cấp quyền',{exact:true}).selectOption(cid);await panel().getByLabel('Nhãn hàng cấp Codex cá nhân',{exact:true}).selectOption(bid);await panel().getByLabel('Thời hạn quyền Codex cá nhân',{exact:true}).fill('30');assert.equal(await stageButton().isDisabled(),true);await dataAck().check();await panel().getByLabel('Thời hạn quyền Codex cá nhân',{exact:true}).fill('31');assert.equal(await stageButton().isDisabled(),true);await panel().getByLabel('Thời hạn quyền Codex cá nhân',{exact:true}).fill('30');await dataAck().check();
   step='lost stage ACK requires read, no resend';lostGrant=true;await stageButton().click();await panel().getByRole('alert').waitFor();const atLost=writes.length;assert.equal(refs.length,1);assert.equal(await stageButton().isDisabled(),true);await p.waitForTimeout(300);assert.equal(writes.length,atLost);await panel().getByRole('button',{name:'Đọc lại quyền Codex',exact:true}).click();await panel().getByText('Chưa kích hoạt',{exact:true}).waitFor();assert.equal(writes.length,atLost);
   step='activation separate and never inference/tools';const activate=()=>panel().getByRole('button',{name:'Kích hoạt quyền này',exact:true});assert.equal(await activate().isDisabled(),true);await panel().getByLabel('Đồng ý kích hoạt mô hình suy luận AI',{exact:true}).check();await activate().click();await panel().getByText('Đã ghi nhận đồng ý kích hoạt; quyền vẫn cần kiểm tra ở mỗi tác vụ',{exact:true}).waitFor();assert.equal(await activate().isDisabled(),true);assert.ok(writes.some(w=>w.path.endsWith('/activate-model')));assert.ok(!writes.some(w=>/\/runs|\/engine|\/auth|\/dispatch/.test(w.path)));
   step='revocation preserves history';await panel().getByRole('button',{name:'Thu hồi quyền này',exact:true}).click();await p.waitForFunction(()=>document.querySelector('[aria-label="Quyền dùng Codex cá nhân"]')?.textContent?.includes('Đã thu hồi'));assert.equal(await activate().isDisabled(),true);
   step='dark light mobile and keyboard';for(const theme of ['dark','light']){if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();for(const width of [1440,390,320]){await p.setViewportSize({width,height:1050});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);if(width!==390)await p.screenshot({path:path.join(folder,theme+'-'+width+'.png'),fullPage:true,animations:'disabled'})}}
   step='incomplete inventory blocks grants';partial=true;await panel().getByRole('button',{name:'Đọc lại quyền Codex',exact:true}).click();await panel().getByText('Chưa đủ dữ liệu xác minh. Đọc lại quyền trước khi thay đổi.',{exact:true}).waitFor();assert.equal(await stageButton().isDisabled(),true);partial=false;
   step='SME change drops preview before grant write';await p.setViewportSize({width:1440,height:1050});await panel().getByRole('button',{name:'Đọc lại quyền Codex',exact:true}).click();await panel().getByLabel('Kết nối cấp quyền',{exact:true}).selectOption(cid);await dataAck().check();pausePreview=true;previewSeen=false;const beforeScope=writes.filter(w=>w.path.endsWith('/references')).length;await stageButton().click();await p.waitForFunction(()=>true);for(let n=0;n<30&&!previewSeen;n++)await p.waitForTimeout(50);assert.ok(previewSeen);await p.locator('.pao-topbar-context select').selectOption(second);releasePreview();await p.waitForTimeout(300);assert.equal(writes.filter(w=>w.path.endsWith('/references')).length,beforeScope);await panel().waitFor({state:'hidden'});
   step='viewer has no access form';await p.locator('.pao-topbar-context select').selectOption(viewer);await fold().locator(':scope > summary').click();await p.getByText('Người quản lý cấp quyền.',{exact:false}).waitFor();assert.equal(await p.getByLabel('Kết nối cấp quyền',{exact:true}).count(),0);
   assert.deepEqual(outside,[]);assert.deepEqual(unknown,[]);assert.deepEqual(errors,[]);
   const result={pass:true,fixture_only:true,self_only:true,explicit_brand_ttl_and_ACK:true,staged_not_active:true,activation_separate:true,revoke_preserves_history:true,lost_ACK_read_before_retry:true,partial_inventory_blocks_writes:true,scope_change_blocks_late_stage:true,viewer_guard:true,themes:['dark','light'],widths:[1440,390,320],backend_forwarded:0,real_mutations:0,real_provider_calls:0,native_job_tested:false};fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));
  }else{
  step='official login ceremony';await p.goto(base+'/settings?tab=ai&section=providers');await button().waitFor();await p.waitForFunction(()=>document.querySelector('[aria-label="Kết nối Codex"]')?.disabled===false);await connect();
  assert.deepEqual(writes.map(x=>x.path.split('/').at(-1)),['prepare','login']);assert.equal(await dialog().getByRole('link',{name:'Mở trang đăng nhập OpenAI',exact:false}).getAttribute('href'),'https://auth.openai.com/codex/device');assert.equal(await dialog().locator('input[type=password]').count(),0);assert.equal(await p.locator('.mp-client-grid article').count(),3);
  step='no credential/code storage and hide clears code';let storage=await p.evaluate(()=>JSON.stringify({...sessionStorage,...localStorage}));assert.ok(!storage.includes('ABCD-EFGH'));assert.ok(!p.url().includes('ABCD'));
  await p.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))});await p.getByLabel('Mã xác nhận Codex',{exact:true}).waitFor({state:'hidden'});await p.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))});await waitCode();
  step='complete login is not inference or grant';row={...row,version:row.version+1,status:'connected',authentication_ready:true,profile_operation_pending:false};mode='connected';await dialog().getByText('Đã ghi nhận đăng nhập Codex',{exact:true}).waitFor();assert.equal(await dialog().getByLabel('Mã xác nhận Codex',{exact:true}).count(),0);await dialog().getByRole('button',{name:'Đóng',exact:true}).click();await dialog().waitFor({state:'hidden'});
  const before=writes.length;await button().click();await dialog().getByText('Đã ghi nhận đăng nhập Codex',{exact:true}).waitFor();assert.equal(writes.length,before);
  step='disconnect is separate and does not logout host';p.once('dialog',d=>d.accept());await dialog().getByRole('button',{name:'Ngắt kết nối PAO',exact:true}).click();await dialog().getByRole('button',{name:'Đăng nhập Codex',exact:true}).waitFor();await dialog().getByRole('button',{name:'Đóng',exact:true}).click();await connect();await cancel();assert.equal(await dialog().getByLabel('Mã xác nhận Codex',{exact:true}).count(),0);await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
  step='restart recovery uses exact operation';row.profile_operation_pending=true;mode='interrupted';await button().click();await dialog().getByText('Phiên bị gián đoạn, cần phục hồi',{exact:true}).waitFor();await cancel();await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
  step='lost start ACK only read, no auto resend';lost=true;p.once('dialog',d=>d.accept());await button().click();await dialog().getByRole('alert').waitFor();const afterLost=writes.length;await dialog().getByRole('button',{name:'Đọc lại',exact:true}).click();await waitCode();assert.equal(writes.length,afterLost);
  step='responsive themes and accessible modal';for(const width of [390,320,1440]){await p.setViewportSize({width,height:900});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);const box=await dialog().boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1);await p.screenshot({path:path.join(folder,'login-dark-'+width+'.png'),fullPage:false,animations:'disabled'})}
  await cancel();await dialog().getByRole('button',{name:'Đóng',exact:true}).click();await p.getByRole('button',{name:'Chuyển sang giao diện sáng',exact:true}).click();await connect();await p.screenshot({path:path.join(folder,'login-light-1440.png'),fullPage:false,animations:'disabled'});await cancel();await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
  step='SME and viewer guards';await p.locator('.pao-topbar-context select').selectOption(viewer);await button().waitFor();assert.equal(await button().isDisabled(),true);assert.equal(await p.getByLabel('Mã xác nhận Codex',{exact:true}).count(),0);await p.locator('.pao-topbar-context select').selectOption(second);await p.waitForFunction(()=>document.querySelector('[aria-label="Kết nối Codex"]')?.disabled===false);const writesBeforeSetup=writes.length;await button().click();await dialog().getByLabel('Mã mô hình Codex',{exact:true}).waitFor();assert.equal(writes.length,writesBeforeSetup);await dialog().getByRole('button',{name:'Đóng',exact:true}).click();
  assert.deepEqual(outside,[]);assert.deepEqual(unknown,[]);assert.deepEqual(errors,[]);assert.ok(writes.every(x=>!x.path.includes('/auth/token')&&!x.path.includes('grant')&&!x.path.includes('run')));
  const result={pass:true,fixture_only:true,one_click_existing_profile:true,official_url:true,cached_own_profile:true,disconnect_cancel_recovery:true,lost_ACK_no_retry:true,no_code_storage:true,hide_clears_code:true,tenant_viewer_guards:true,themes:['dark','light'],mobile:[320,390],backend_forwarded:0,real_provider_calls:0,real_login:false};fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({folder,...result}));
  }
 }catch(e){await p.screenshot({path:path.join(folder,'failure.png'),fullPage:false}).catch(()=>{});fs.writeFileSync(path.join(folder,'receipt.json'),JSON.stringify({pass:false,step,error:e.message,unknown,errors,outside},null,2));console.error('Codex login UI failed at '+step+'; '+folder);throw e}
 finally{await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{await browser?.close()});
