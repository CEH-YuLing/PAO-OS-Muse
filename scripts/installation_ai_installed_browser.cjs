// Installed authenticated GET-only UI. Never click Connect/Save/Test/Disconnect.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const fixture=JSON.parse(process.env.PAO_AI_INSTALLED),base='http://127.0.0.1:3200';
const reads=[],blocked=[],errors=[];let browser;
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1600,height:1000},serviceWorkers:'block'});
 await context.addInitScript(({token,actor,workspace})=>{sessionStorage.setItem('pao.access_token',token);sessionStorage.setItem('pao.workspace.'+actor,workspace)},fixture);
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.origin!==base){blocked.push('external');return route.abort()}
  if(url.pathname==='/api/weather')return route.fulfill({status:200,json:{}});
  if(url.pathname.startsWith('/v1/')){
   if(request.method()!=='GET'||url.pathname==='/v1/engines'||url.pathname.endsWith('/models')){blocked.push(request.method()+':'+url.pathname);return route.abort()}
   reads.push(url.pathname);
  }
  return route.continue();
 });
 const page=await context.newPage();page.setDefaultTimeout(20000);page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base+'/settings?tab=ai&section=providers');
 const shared=()=>page.getByLabel('Tài nguyên AI dùng chung',{exact:true});
 await shared().waitFor();await shared().getByText('Chưa có tài nguyên chung.',{exact:false}).waitFor();
 assert.equal(await page.locator('.mp-client-grid>article').count(),3);
 assert.equal(await page.locator('.pao-personal-codex,.mp-profile-status').count(),0);
 for(const theme of ['dark','light']){
  if(await page.locator('html').getAttribute('data-theme')!==theme)await page.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
  for(const width of [1600,390,320]){
   await page.setViewportSize({width,height:1000});await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
   if(width!==390)await page.screenshot({path:path.join(fixture.folder,theme+'-'+width+'.png'),fullPage:true,animations:'disabled'});
  }
 }
 await page.getByTestId('model-connection-tab-api').click();await page.getByLabel('Cài đặt mô hình đám mây',{exact:true}).locator('.cm-grid>article').first().waitFor();
 assert.equal(await page.locator('.cm-grid>article').count(),4);
 await page.goto(base+'/settings?tab=ai&section=access');await shared().waitFor();
 assert.equal(await page.getByText('Nâng cao: quyền API cá nhân cũ',{exact:true}).count(),0);
 assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);
 const result={pass:true,installed_GET_only:true,api_mutations:0,provider_calls:0,client_cards:3,api_cards:4,personal_grant_wizard_removed:true,themes:['dark','light'],widths:[1600,390,320],requests:reads.length};
 fs.writeFileSync(path.join(fixture.folder,'browser-receipt.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await context.close();
})().catch(error=>{console.error(error.message);process.exitCode=1}).finally(async()=>{await browser?.close()});
