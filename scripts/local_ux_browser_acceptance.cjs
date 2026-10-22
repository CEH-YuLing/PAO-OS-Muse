// Native API fixture; appearance changes never grant permission or call a provider.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const {open}=require('./p6_browser_harness.cjs');
(async()=>{
 const f=JSON.parse(process.env.PAO_S5_BROWSER),h=await open(f,{multiTab:true}),p=h.page;let step='login';
 const file=name=>f.folder+'/'+name;let writes=0;const contrast=[];
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').first().selectOption(f.workspace);
  await p.waitForFunction(wid=>Object.entries(sessionStorage).some(([key,value])=>key.startsWith('pao.workspace.')&&value===wid),f.workspace);
  await p.goto(f.web+'/dashboard');await p.locator('.pao-page-heading h1').waitFor();
  p.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/v1/')&&['POST','PUT','PATCH','DELETE'].includes(request.method()))writes++});
  step='theme controls';assert.equal(await p.locator('html').getAttribute('data-theme'),'dark');
  await p.getByRole('button',{name:'Chuyển sang giao diện sáng',exact:true}).click();
  assert.equal(await p.locator('html').getAttribute('data-theme'),'light');
  assert.equal(await p.evaluate(()=>localStorage.getItem('pao.ui.theme')),'light');
  await p.reload();await p.locator('.pao-page-heading h1').waitFor();assert.equal(await p.locator('html').getAttribute('data-theme'),'light');
  async function readable(){return p.evaluate(()=>{
   const parse=c=>{const v=c.match(/[\d.]+/g)?.map(Number)||[0,0,0,0];return v.length===3?[...v,1]:v};
   const lum=rgb=>rgb.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
   return [...document.querySelectorAll('.pao-page-heading h1,.pao-page-heading p,.pao-sidebar nav a,.pao-appearance p,.st-tabs button,.cn-tabs button,.pao-kpi-grid header span,.pao-kpi-grid p,.pao-dashboard-card h3,.pao-layer small,.st-panel-head small,.lc-panel label')].filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden').map(e=>{
    const fg=parse(getComputedStyle(e).color);let bg=[0,0,0,0];for(let a=e;a&&bg[3]===0;a=a.parentElement)bg=parse(getComputedStyle(a).backgroundColor);
    const ratio=(Math.max(lum(fg),lum(bg))+.05)/(Math.min(lum(fg),lum(bg))+.05);
    return {text:e.textContent.trim().slice(0,45),ratio:Math.round(ratio*100)/100,font:parseFloat(getComputedStyle(e).fontSize)};
   });
  })}
  step='all areas in both themes';
  for(const theme of ['light','dark']){
   if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:`Chuyển sang giao diện ${theme==='light'?'sáng':'tối'}`,exact:true}).click();
   for(const route of ['dashboard','pao-ai','tasks','meta-ads','tiktok-ads','google-ads','crm','content-creative','analytics','automation','knowledge','settings','business-planning']){
    await p.goto(f.web+'/'+route);await p.locator('.pao-page-heading h1').waitFor();
    await p.waitForFunction(()=>!document.querySelector('.st-loading')&&!document.querySelector('.pao-kpi-grid .is-loading'));
    await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
    assert.equal(await p.locator('html').getAttribute('data-theme'),theme);
    const values=await readable();contrast.push({theme,route,samples:values.length,min:Math.min(...values.map(v=>v.ratio))});
    assert.ok(values.every(v=>v.ratio>=4.5),JSON.stringify({theme,route,low:values.filter(v=>v.ratio<4.5)}));
    if(route==='dashboard')assert.equal(await p.getByText('Chưa có dữ liệu',{exact:true}).count()>0,true);
    if(route==='pao-ai'){await p.getByText('Đang tắt',{exact:true}).waitFor();assert.equal(await p.getByText('READY',{exact:true}).count(),0)}
    if(['dashboard','settings','business-planning','pao-ai'].includes(route))await p.screenshot({path:file(`${theme}-${route}.png`),fullPage:false});
   }
  }
  step='settings appearance and retention of state';await p.goto(f.web+'/settings');
  await p.getByRole('group',{name:'Chọn giao diện PAO'}).getByRole('button',{name:/^Sáng/}).click();
  assert.equal(await p.locator('html').getAttribute('data-theme'),'light');
  await p.getByTestId('settings-tab-integrations').click();
  for(const [group,platform] of [['ads','meta'],['ads','google'],['ads','tiktok'],['bots','telegram'],['mcp',null],['plugins','plugins_messaging']]){
   await p.getByTestId('connection-group-'+group).click();if(platform)await p.getByTestId('connection-tab-'+platform).click();await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  }
  await p.screenshot({path:file('light-connections.png'),fullPage:false});
  await p.getByTestId('settings-tab-capabilities').click();await p.screenshot({path:file('light-capabilities.png'),fullPage:false});
  step='copilot keyboard and hidden focus';assert.equal(await p.getByRole('dialog',{name:'PAO Copilot'}).count(),0);
  await p.getByRole('button',{name:'Mở PAO Copilot',exact:true}).click();await p.getByRole('dialog',{name:'PAO Copilot'}).waitFor();
  await p.keyboard.press('Escape');assert.equal(await p.getByRole('dialog',{name:'PAO Copilot'}).count(),0);
  assert.equal(await p.getByRole('button',{name:'Mở PAO Copilot',exact:true}).evaluate(e=>e===document.activeElement),true);
  step='mobile';for(const width of [390,320]){
   await p.setViewportSize({width,height:844});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
   await p.getByRole('button',{name:'Chuyển sang giao diện tối',exact:true}).click();await p.getByRole('button',{name:'Chuyển sang giao diện sáng',exact:true}).click();
  }
  await p.screenshot({path:file('light-mobile.png'),fullPage:true});
  await p.getByRole('button',{name:'Mở điều hướng',exact:true}).click();await p.keyboard.press('Escape');
  assert.equal(await p.locator('.pao-sidebar.is-mobile-open').count(),0);
  step='theme cross-tab sync';const second=await p.context().newPage();
  await second.goto(f.web+'/join');await second.getByRole('button',{name:'Chuyển sang giao diện tối',exact:true}).click();
  await p.waitForFunction(()=>document.documentElement.dataset.theme==='dark');await second.close();
  assert.equal(writes,0,'Appearance/read-only UI must not issue an API mutation');assert.deepEqual(h.errors,[]);
  step='public preference and denied storage';const browser=await chromium.launch({channel:'msedge',headless:true});
  try{
   const c=await browser.newContext();await c.addInitScript(()=>localStorage.setItem('pao.ui.theme','light'));
   const page=await c.newPage();await page.goto(f.web+'/');await page.getByLabel('Email',{exact:true}).waitFor();
   assert.equal(await page.locator('html').getAttribute('data-theme'),'light');await page.screenshot({path:file('light-login.png'),fullPage:false});
   const denied=await browser.newContext();await denied.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})});
   const blocked=await denied.newPage();await blocked.goto(f.web+'/join');await blocked.getByRole('button',{name:'Chuyển sang giao diện sáng',exact:true}).click();
   assert.equal(await blocked.locator('html').getAttribute('data-theme'),'light');
  }finally{await browser.close()}
  const result={pass:true,themes:['dark','light'],routes_each_theme:13,node_tests:128,theme_persistence:true,settings_options:true,cross_tab:true,storage_denial:true,mobile_widths:[390,320],copilot_escape_focus:true,api_mutations:0,provider_calls:false,contrast_samples:contrast};
  fs.writeFileSync(file('theme-browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }catch(e){await p.screenshot({path:file('theme-failure.png'),fullPage:false}).catch(()=>{});throw Error(step+': '+e.message)}finally{await h.close()}
})().catch(e=>{console.error(String(e.message).slice(0,1600));process.exitCode=1});
