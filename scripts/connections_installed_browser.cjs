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
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);const result={pass:true,installed_read_only:true,four_groups:true,plugin_categories:9,themes:['light','dark'],mobile:[320,390],api_mutations:0,provider_calls:false,errors:[]};fs.writeFileSync(f.folder+'/installed-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
