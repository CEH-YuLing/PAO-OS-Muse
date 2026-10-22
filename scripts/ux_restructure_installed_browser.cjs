// Installed UI, read-only API calls only. Process-only diagnostic auth.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{const f=JSON.parse(process.env.PAO_UX_LIVE),browser=await chromium.launch({channel:'msedge',headless:true});try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),errors=[],blocked=[];
 await context.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||(['POST','PUT','PATCH','DELETE'].includes(r.method())&&u.pathname.startsWith('/v1/'))){blocked.push({method:r.method(),path:u.pathname});return route.abort()}return route.continue()});
 await context.addInitScript(f=>{if(location.origin===f.web){sessionStorage.setItem('pao.access_token',f.token);sessionStorage.setItem('pao.workspace.'+f.actor,f.workspace)}},f);
 const p=await context.newPage();p.setDefaultTimeout(60000);p.on('pageerror',e=>errors.push(e.message));
 await p.goto(f.web+'/settings?tab=integrations&platform=meta');await p.getByTestId('ads-app-meta').waitFor();
 for(const theme of ['light','dark']){
  if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
  for(const group of ['ads','bots','plugins','mcp']){await p.getByTestId('connection-group-'+group).click();assert.equal(await p.getByTestId('connection-group-'+group).getAttribute('aria-selected'),'true');await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await p.screenshot({path:f.folder+'/installed-connections-'+theme+'-'+group+'.png',fullPage:false})}
 }
 await p.getByTestId('connection-group-plugins').click();assert.equal(await p.getByRole('tablist',{name:'Danh mục plugin'}).getByRole('tab').count(),9);assert.equal(await p.locator('.cn-plugin-cards article').count(),7);
 for(const width of [320,390]){await p.setViewportSize({width,height:844});for(const group of ['ads','bots','plugins','mcp']){await p.getByTestId('connection-group-'+group).click();await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth)}await p.getByTestId('connection-group-plugins').click();await p.screenshot({path:f.folder+'/installed-connections-mobile-'+width+'.png',fullPage:false})}

 await p.setViewportSize({width:1440,height:1000});
 for(const theme of ['light','dark']){
  await p.goto(f.web+'/settings?tab=team&section=members');
  if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();
  assert.equal(await p.getByRole('tablist',{name:'Khu vực cài đặt và kết nối'}).getByRole('tab').count(),7);
  await p.locator('.lc-panel').waitFor();await p.screenshot({path:f.folder+'/installed-ux-settings-'+theme+'.png',fullPage:false});
  await p.goto(f.web+'/knowledge?tab=skills');await p.getByRole('heading',{name:'Skills dành cho agent',exact:true}).waitFor();assert.equal(await p.getByLabel('Biên tập skill hoặc agent',{exact:true}).count(),0);
  await p.screenshot({path:f.folder+'/installed-ux-skills-'+theme+'.png',fullPage:false});
  await p.goto(f.web+'/business-planning#bp-routing');await p.waitForFunction(()=>document.querySelector('#business-view-tab-routing')?.getAttribute('aria-selected')==='true');assert.equal(await p.getByRole('tablist',{name:'Hành trình kế hoạch kinh doanh'}).getByRole('tab').count(),5);
  await p.screenshot({path:f.folder+'/installed-ux-business-'+theme+'.png',fullPage:false});
  for(const route of ['tasks','meta-ads','tiktok-ads','google-ads','content-creative','crm','analytics','automation','channels','pao-ai','dashboard']){await p.goto(f.web+'/'+route);await p.locator('.pao-page-heading h1').waitFor();await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth)}
 }
 for(const width of [320,390]){await p.setViewportSize({width,height:844});for(const route of ['settings?tab=team&section=invitations','knowledge?tab=skills','business-planning','tasks','meta-ads','channels']){await p.goto(f.web+'/'+route);await p.locator('.pao-page-heading h1').waitFor();await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth)}await p.goto(f.web+'/settings?tab=team&section=members');await p.locator('.lc-panel').waitFor();await p.screenshot({path:f.folder+'/installed-ux-mobile-'+width+'.png',fullPage:false})}
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);const result={pass:true,installed_read_only:true,ux_restructure:true,settings_groups:7,business_tabs:5,areas:12,four_groups:true,plugin_categories:9,themes:['light','dark'],mobile:[320,390],api_mutations:0,provider_calls:false,errors:[]};fs.writeFileSync(f.folder+'/installed-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
