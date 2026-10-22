// Read-only installed check: confirmation can open, but no primary mutation allowed.
const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
(async()=>{
 const f=JSON.parse(process.env.PAO_UX_LIVE),browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),blocked=[],errors=[];
  await context.route('**/*',route=>{const r=route.request(),u=new URL(r.url());if(u.hostname!=='127.0.0.1'||(['POST','PUT','PATCH','DELETE'].includes(r.method())&&u.pathname.startsWith('/v1/'))){blocked.push({method:r.method(),path:u.pathname});return route.abort()}return route.continue()});
  await context.addInitScript(f=>{if(location.origin===f.web){sessionStorage.setItem('pao.access_token',f.token);sessionStorage.setItem('pao.workspace.'+f.actor,f.workspace)}},f);
  const p=await context.newPage();p.setDefaultTimeout(60000);p.on('pageerror',e=>errors.push(e.message));
  await p.goto(f.web+'/tasks');await p.locator('.tasks-toolbar').waitFor();await p.locator('.task-card').first().waitFor();
  const firstTitle=await p.locator('.task-card h3').first().innerText();await p.locator('.task-card').first().click();
  const area=p.getByRole('region',{name:'Xóa công việc',exact:true});await area.waitFor();const button=area.getByRole('button',{name:'Xóa công việc',exact:true});
  const enabled=await button.isEnabled();if(enabled){await button.click();await area.getByRole('alertdialog').waitFor();await area.getByRole('button',{name:'Giữ lại',exact:true}).click()}
  for(const theme of ['light','dark']){
   // Persist only the normal browser-local appearance preference.
   if(await p.locator('html').getAttribute('data-theme')!==theme){await p.locator('.task-drawer').getByRole('button',{name:'Đóng task detail',exact:true}).click();await p.getByRole('button',{name:'Chuyển sang giao diện '+(theme==='light'?'sáng':'tối'),exact:true}).click();await p.locator('.task-card').filter({has:p.getByRole('heading',{name:firstTitle,exact:true})}).click()}
   await p.screenshot({path:f.folder+'/installed-delete-'+theme+'.png',fullPage:false});
  }
  for(const width of [320,390]){await p.setViewportSize({width,height:844});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await p.screenshot({path:f.folder+'/installed-delete-'+width+'.png',fullPage:false})}
  assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
  const result={pass:true,api_mutations:0,primary_task_not_deleted:true,confirmation_keep_verified:enabled,themes:['light','dark'],mobile:[320,390]};fs.writeFileSync(f.folder+'/installed-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
