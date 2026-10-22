// Read-only installed acceptance. Diagnostic auth stays process-only; no API mutations.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{const f=JSON.parse(process.env.PAO_UX_LIVE),browser=await chromium.launch({channel:'msedge',headless:true});
 try{const c=await browser.newContext({viewport:{width:1440,height:1000}}),errors=[],blocked=[];
  await c.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||(['POST','PUT','PATCH','DELETE'].includes(r.method())&&u.pathname.startsWith('/v1/'))){blocked.push({method:r.method(),path:u.pathname});return route.abort()}return route.continue()});
  await c.addInitScript(f=>{if(location.origin===f.web){sessionStorage.setItem('pao.access_token',f.token);sessionStorage.setItem('pao.workspace.'+f.actor,f.workspace)}},f);
  const p=await c.newPage();p.setDefaultTimeout(60000);p.on('pageerror',e=>errors.push(e.message));
  await p.goto(f.web+'/settings');await p.locator('.pao-page-heading h1').waitFor();
  for(const theme of ['light','dark']){
   if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:`Chuyển sang giao diện ${theme==='light'?'sáng':'tối'}`,exact:true}).click();
   for(const route of ['settings','dashboard','pao-ai','business-planning']){
    await p.goto(f.web+'/'+route);await p.locator('.pao-page-heading h1').waitFor();
    await p.waitForFunction(()=>!document.querySelector('.st-loading')&&!document.querySelector('.pao-kpi-grid .is-loading'));
    assert.equal(await p.locator('html').getAttribute('data-theme'),theme);assert.equal(await p.locator('.pao-nav-module').count(),12);
    await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
    if(route==='settings')await p.getByRole('heading',{name:'Giao diện hiển thị',exact:true}).waitFor();
    if(route==='dashboard')await p.getByRole('heading',{name:'Tổng quan',exact:true}).waitFor();
    if(route==='pao-ai')await p.getByText('Đang tắt',{exact:true}).waitFor();
    await p.screenshot({path:f.folder+`/installed-${theme}-${route}.png`,fullPage:false});
   }
  }
  await p.goto(f.web+'/settings?tab=integrations&platform=meta');await p.locator('.st-loading').waitFor({state:'hidden'});
  await p.getByRole('button',{name:'Chuyển sang giao diện sáng',exact:true}).click();
  await p.getByRole('tab',{name:/Meta Ads/}).waitFor();await p.screenshot({path:f.folder+'/installed-light-connections.png',fullPage:false});
  await p.setViewportSize({width:390,height:844});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  await p.screenshot({path:f.folder+'/installed-light-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  const result={pass:true,installed_read_only:true,themes:['light','dark'],routes_each_theme:4,connection_tabs:true,mobile:true,api_mutations:0,provider_calls:false,errors:[]};
  fs.writeFileSync(f.folder+'/installed-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error('Installed UI: '+String(e.message).slice(0,500));process.exitCode=1});
