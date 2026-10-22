// Installed GET-only acceptance. No Connect/Test/Save or provider requests.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const value=JSON.parse(process.env.PAO_GD01_BROWSER),base='http://127.0.0.1:3200';
const reads=[],denied=[],errors=[];let browser;
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 await context.addInitScript(({token,actor,workspace})=>{sessionStorage.setItem('pao.access_token',token);sessionStorage.setItem('pao.workspace.'+actor,workspace)},value);
 await context.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.origin!==base){denied.push('external');return route.abort()}
  if(url.pathname==='/api/weather')return route.fulfill({status:200,json:{}});
  if(url.pathname.startsWith('/v1/')){
   if(req.method()!=='GET'||url.pathname.endsWith('/models')){denied.push(req.method()+':'+url.pathname);return route.abort()}
   reads.push(url.pathname);
  }
  return route.continue();
 });
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(20000);
 await page.goto(base+'/settings?tab=ai&section=providers');
 const shared=page.getByLabel('Tài nguyên AI dùng chung',{exact:true});await shared.waitFor();
 await shared.getByText('Hạn mức còn lại: chưa xác minh.',{exact:false}).first().waitFor();
 await shared.getByText('Đối chiếu cấu hình cũ · chỉ xem, không thay đổi',{exact:true}).click();
 await shared.getByText('Chỉ thống kê hội thoại của bạn trong doanh nghiệp đang chọn.',{exact:false}).waitFor();
 assert.equal(await page.locator('.mp-client-grid>article').count(),4);
 await page.getByLabel('Kết nối Muse',{exact:true}).getByRole('status').waitFor();
 assert.equal(await page.locator('.pao-personal-codex,.mp-profile-status').count(),0);
 for(const theme of ['dark','light']){
  if(await page.locator('html').getAttribute('data-theme')!==theme)
   await page.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:1000});
   await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
   if(width!==390)await page.screenshot({path:path.join(value.folder,theme+'-'+width+'.png'),fullPage:true,animations:'disabled'});
  }
 }
 await page.getByTestId('model-connection-tab-api').click();
 await page.getByLabel('Cài đặt mô hình đám mây',{exact:true}).waitFor();
 await page.locator('.cm-grid>article').first().waitFor();
 assert.equal(await page.locator('.cm-grid>article').count(),4);
 await page.setViewportSize({width:1440,height:1000});
 await page.goto(base+'/pao-ai');
 await page.getByRole('button',{name:'Chọn mô hình hội thoại',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'Chọn mô hình hội thoại',exact:true});await dialog.waitFor();
 await dialog.getByRole('tab',{name:'Kết nối qua Client',exact:true}).click();
 if(value.personal_model){
  const codex=dialog.getByRole('radio',{name:'Codex — '+value.personal_model,exact:true});
  await codex.waitFor();assert.equal(await codex.isEnabled(),true);
  for(const model of value.personal_models||[]){const radio=dialog.getByRole('radio',{name:'Codex — '+model,exact:true});await radio.waitFor();assert.equal(await radio.isEnabled(),true)}
 }
 for(const model of value.muse_models||[]){
  const radio=dialog.getByRole('radio',{name:'Muse — '+model,exact:true});
  await radio.waitFor();assert.equal(await radio.isEnabled(),true);
 }
 await dialog.getByText('Bộ kết nối hội thoại Claude Code chưa được triển khai.',{exact:true}).waitFor();
 await dialog.getByText('Kết nối Antigravity hiện chỉ đọc danh mục; chưa hỗ trợ hội thoại trong PAO.',{exact:true}).waitFor();
 await page.screenshot({path:path.join(value.folder,'installed-client-picker.png'),animations:'disabled'});
 await dialog.getByRole('tab',{name:'Kết nối qua API',exact:true}).click();
 await dialog.getByRole('combobox',{name:'Lọc loại đầu ra mô hình',exact:true}).selectOption('image');
 const imageModels=dialog.getByRole('radio');
 assert.ok(await imageModels.count()>0,'Current native API catalog contains dedicated image models');
 for(const radio of await imageModels.all())assert.equal(await radio.isEnabled(),false);
 await dialog.getByText('Không dùng cho hội thoại văn bản · cần bộ kết nối chuyên dụng.',{exact:true}).first().waitFor();
 await page.screenshot({path:path.join(value.folder,'installed-modality-filter.png'),animations:'disabled'});
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Hội thoại, quyền riêng tư và thống kê',exact:true}).click();
 await page.getByText('Ngữ cảnh, đầu ra và token suy luận theo khả năng của mô hình.',{exact:false}).waitFor();
 for(const name of ['Giới hạn context','Giới hạn output','Ngân sách run'])assert.equal(await page.getByRole('spinbutton',{name,exact:true}).count(),0);
 await page.screenshot({path:path.join(value.folder,'installed-provider-token-policy.png'),animations:'disabled'});
 await page.keyboard.press('Escape');
 assert.deepEqual(denied,[]);assert.deepEqual(errors,[]);
 const result={pass:true,provider_token_policy_visible:true,no_token_cap_inputs:true,installed_GET_only:true,api_mutations:0,provider_calls:0,reads:reads.length,
  client_cards:4,api_cards:4,muse_metadata_reads_only:true,muse_selectable:!!value.muse_models?.length,muse_model_count:value.muse_models?.length||0,personal_codex_selectable:!!value.personal_model,personal_codex_model_count:value.personal_models?.length||0,client_status_honest:true,unknown_quota_honest:true,modality_filter:true,nonchat_disabled:true,compatibility_preview:true,widths:[1440,390,320],themes:['dark','light']};
 fs.writeFileSync(path.join(value.folder,'browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 await context.close();
})().catch(e=>{console.error(e.message);process.exitCode=1}).finally(async()=>{await browser?.close()});
