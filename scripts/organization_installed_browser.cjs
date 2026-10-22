// Installed read-only acceptance. Never log/persist the diagnostic token.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{const f=JSON.parse(process.env.PAO_UX_LIVE),browser=await chromium.launch({channel:'msedge',headless:true});try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),blocked=[],errors=[];
 await context.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||(['POST','PUT','PATCH','DELETE'].includes(r.method())&&u.pathname.startsWith('/v1/'))){blocked.push({method:r.method(),path:u.pathname});return route.abort()}return route.continue()});
 await context.addInitScript(f=>{if(location.origin===f.web){sessionStorage.setItem('pao.access_token',f.token);sessionStorage.setItem('pao.workspace.'+f.actor,f.workspace)}},f);
 const p=await context.newPage();p.setDefaultTimeout(60000);p.on('pageerror',e=>errors.push(e.message));
 for(const theme of ['light','dark']){
  await p.goto(f.web+'/settings?tab=organization');await p.getByLabel('Tên doanh nghiệp hiện tại',{exact:true}).waitFor();
  if(await p.locator('html').getAttribute('data-theme')!==theme)await p.getByRole('button',{name:`Chuyển sang giao diện ${theme==='light'?'sáng':'tối'}`,exact:true}).click();
  assert.equal(await p.getByRole('navigation',{name:'Khu vực cài đặt và kết nối'}).getByRole('button').count(),7);
  await p.screenshot({path:f.folder+'/installed-organization-'+theme+'.png',fullPage:false});
  for(const [tab,heading]of [['enterprise','Thông tin chi tiết doanh nghiệp'],['brands','Thông tin chi tiết nhãn hàng'],['skills','Skills dành cho agent']]){
   await p.goto(f.web+'/knowledge?tab='+tab);await p.getByRole('heading',{name:heading,exact:true}).waitFor();assert.equal(await p.locator('.pao-nav-module').count(),12);await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await p.screenshot({path:f.folder+'/installed-'+tab+'-'+theme+'.png',fullPage:false});
  }
 }
 await p.goto(f.web+'/skills');await p.waitForURL('**/knowledge?tab=skills');await p.getByRole('heading',{name:'Skills dành cho agent',exact:true}).waitFor();
 for(const width of [320,390]){await p.setViewportSize({width,height:844});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await p.screenshot({path:f.folder+'/installed-organization-mobile-'+width+'.png',fullPage:false})}
 assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);const result={pass:true,installed_read_only:true,enterprise_settings:true,knowledge_sections:true,legacy_redirect:true,mobile:[320,390],themes:['light','dark'],api_mutations:0,provider_calls:false,errors:[]};fs.writeFileSync(f.folder+'/installed-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
