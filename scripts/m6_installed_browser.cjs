// Read-only smoke on installed frontend. A process-only diagnostic token is never logged.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{const f=JSON.parse(process.env.PAO_M6_LIVE),browser=await chromium.launch({channel:'msedge',headless:true});
 try{const context=await browser.newContext({viewport:{width:1440,height:1000}}),errors=[],blocked=[];
  await context.route('**/*',async route=>{const request=route.request(),url=new URL(request.url());if(url.hostname!=='127.0.0.1'||(['POST','PUT','PATCH','DELETE'].includes(request.method())&&url.pathname.startsWith('/v1/'))){blocked.push({method:request.method(),path:url.pathname});return route.abort();}return route.continue();});
  await context.addInitScript(value=>{if(location.origin===value.web){sessionStorage.setItem('pao.access_token',value.token);sessionStorage.setItem('pao.workspace.'+value.actor,value.workspace);}},f);
  const page=await context.newPage();page.setDefaultTimeout(60000);page.on('pageerror',e=>errors.push(e.message));
  await page.goto(f.web+'/business-planning');await page.locator('.pao-subviews a[href="/business-planning"]').waitFor();await page.getByLabel('Mô tả doanh nghiệp',{exact:true}).waitFor();assert.equal(await page.locator('.pao-nav-module').count(),12);assert.equal(await page.getByRole('navigation',{name:'Hành trình kế hoạch kinh doanh'}).getByRole('link').count(),6);
  await page.goto(f.web+'/settings?tab=integrations&platform=zalo');await page.getByText('Chưa hỗ trợ kết nối',{exact:true}).waitFor();assert.equal(await page.getByRole('tab',{name:/Zalo OA/}).getAttribute('aria-selected'),'true');await page.screenshot({path:f.folder+'/installed-settings.png',fullPage:false});
  assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);fs.writeFileSync(f.folder+'/installed-browser.json',JSON.stringify({pass:true,read_only:true,installed_ui:true,twelve_areas:true,settings_deep_link:true,business_journey:true,api_mutations:0,provider_calls:false}));console.log('Installed M6 read-only UI passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error('Installed M6 UI failed: '+String(e.message).split('\n')[0].slice(0,180));process.exitCode=1;});
