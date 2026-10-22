// Fresh sandbox UI acceptance. No provider calls, prompts, connection saves or source access.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),base='http://127.0.0.1:3300';
assert.equal(root.toLowerCase(),'g:\\pao os muse');
const password=fs.readFileSync(path.join(root,'.runtime/first-login.txt'),'utf8').match(/^Password: (.+)$/m)?.[1];
assert.ok(password);let browser,page;
(async()=>{
 browser=await chromium.launch({channel:'msedge',headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
 const errors=[],blocked=[],badAPI=[],unconfigured=[],responses=[];
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.origin!==base){blocked.push('external');return route.abort()}
  if(url.pathname==='/api/weather')return route.fulfill({status:200,json:{}});
  if(url.pathname.startsWith('/v1/')&&request.method()!=='GET'&&url.pathname!=='/v1/auth/token'){
   blocked.push(request.method()+':'+url.pathname);return route.abort();
  }
  return route.continue();
 });
 page=await context.newPage();page.setDefaultTimeout(45000);
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{
  const url=new URL(r.url());
  if(url.pathname.startsWith('/v1/')&&r.status()>=500)responses.push((async()=>{
   const body=await r.json().catch(()=>({}));
   // Fresh fork deliberately has no actor-bound native Antigravity config.
   // Keep this expected unavailable state explicit, not a blanket 503 exemption.
   if(r.status()===503&&/^\/v1\/workspaces\/[^/]+\/antigravity-native$/.test(url.pathname)
      &&body.detail==='antigravity_native_not_provisioned_for_actor')
    unconfigured.push({provider:'antigravity',status:503,detail:body.detail});
   else badAPI.push({path:url.pathname,status:r.status()});
  })());
 });
 await page.goto(base+'/');
 await page.getByLabel('Email',{exact:true}).fill('owner@muse.pao.local');
 await page.getByLabel('Mật khẩu',{exact:true}).fill(password);
 const logged=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/auth/token');
 await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
 assert.equal((await logged).status(),200);
 // Login also fetches /v1/me before persisting the credential. Do not navigate
 // away after the token response and abort that still-pending identity request.
 await page.waitForFunction(()=>!!sessionStorage.getItem('pao.access_token'));
 const routes=[['dashboard','Tổng quan'],['pao-ai','PAO AI'],['tasks','Công việc và dự án'],
  ['knowledge','Kho tri thức'],['business-planning','Kế hoạch kinh doanh'],['settings','Cài đặt và kết nối']];
 for(const [url,title] of routes){
  await page.goto(base+'/'+url);await page.getByRole('heading',{name:title,exact:true}).first().waitFor();
 }
 await page.goto(base+'/settings?tab=ai&section=providers');
 await page.getByLabel('Tài nguyên AI dùng chung',{exact:true}).waitFor();
 await page.locator('div[aria-label="Kết nối Muse"]').waitFor();
 await page.screenshot({path:path.join(root,'.runtime/muse-sandbox-desktop.png'),animations:'disabled'});
 await page.setViewportSize({width:390,height:950});
 await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
 await page.screenshot({path:path.join(root,'.runtime/muse-sandbox-mobile.png'),animations:'disabled'});
 await Promise.all(responses);
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);assert.deepEqual(badAPI,[]);
 const result={pass:true,origin:base,login:true,routes:routes.map(r=>r[0]),mobile390:true,
  settings_muse_card:true,provider_calls:0,run_creations:0,connections_saved:0,
  mutations:'Only fresh sandbox login/session',page_errors:errors,blocked,unexpected_API_500:badAPI,
  expected_unconfigured_providers:unconfigured};
 fs.writeFileSync(path.join(root,'.runtime/muse-copy-browser.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));await context.close();
})().catch(async e=>{
 const stamp=Date.now();
 if(page){await page.screenshot({path:path.join(root,'.runtime/muse-browser-failure-'+stamp+'.png')}).catch(()=>{});
  const state={url:page.url(),body:(await page.locator('body').innerText().catch(()=>'' )).slice(0,2000),error:e.message};
  fs.writeFileSync(path.join(root,'.runtime/muse-browser-failure-'+stamp+'.json'),JSON.stringify(state,null,2));
  console.error(JSON.stringify(state));}
 process.exitCode=1;
}).finally(async()=>{await browser?.close()});
