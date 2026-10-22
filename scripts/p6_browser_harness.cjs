const assert=require('node:assert/strict');const {chromium}=require('playwright');
exports.open=async function(f,options={}){
 assert.ok(f&&new URL(f.api).hostname==='127.0.0.1');
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 const context=options.multiTab?await browser.newContext({viewport:{width:1440,height:1000}}):null;
 const page=context?await context.newPage():await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];let closing=false;
 // A local UI test must not trigger the Next weather proxy's upstream request.
 await page.route('**/api/weather*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({city:'Hạ Long',current:null})}));
 page.setDefaultTimeout(35000);page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.route('**/v1/**',async route=>{try{const u=new URL(route.request().url());const response=await route.fetch({url:f.api+u.pathname+u.search});if(options.intercept&&await options.intercept(route,response))return;await route.fulfill({response})}catch(e){if(!closing){errors.push('HTTP route failure');const category=String(e.message).match(/net::ERR_[A-Z_]+|Target closed|disposed|Request context destroyed|already handled|Failed to fetch/gi)||['unclassified'];const path=new URL(route.request().url()).pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi,':id');const summary=String(e.message).split('\n')[0].replace(/https?:\/\/\S+/g,'[url]').replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi,':id').slice(0,240);console.error('Browser route diagnostic '+JSON.stringify({path,category,summary,requestFailure:route.request().failure()?.errorText?.match(/net::ERR_[A-Z_]+/g)||null}));}await route.abort().catch(()=>{})}});
 return {page,errors,
  login:async()=>{await page.goto(f.web+'/');await page.getByLabel('Email',{exact:true}).fill('owner@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');const me=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/me'&&r.status()===200);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await me;await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor({state:'hidden'})},
  mobile:async()=>{await page.setViewportSize({width:390,height:844});await page.evaluate(async()=>{await document.fonts.ready;await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame)});await page.waitForFunction(()=>document.documentElement.scrollWidth<=window.innerWidth,undefined,{timeout:5000});await page.screenshot({path:f.screenshot,fullPage:true});assert.deepEqual(errors,[])},
  close:async()=>{closing=true;await page.close();await browser.close()}
 };
};
