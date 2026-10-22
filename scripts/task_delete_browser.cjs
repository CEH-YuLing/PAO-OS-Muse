const assert=require('node:assert/strict'),fs=require('node:fs'),{open}=require('./p6_browser_harness.cjs');
let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_S5_BROWSER),h=await open(f),p=h.page;
 try{
  const auth=await fetch(f.api+'/v1/auth/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'owner@example.test',password:'test-password-123'})});
  assert.equal(auth.status,200);const token=(await auth.json()).access_token;
  async function api(path,method='GET',body){return fetch(f.api+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined})}
  async function create(title,extra={}){const r=await api('/v1/tasks','POST',{workspace_id:f.workspace,title,...extra});assert.equal(r.status,201);return r.json()}
  async function reload(){await p.goto(f.web+'/tasks');await p.locator('.tasks-toolbar').waitFor()}
  async function select(title){await p.locator('.task-card').filter({has:p.getByRole('heading',{name:title,exact:true})}).click();await p.getByRole('complementary',{name:'Chi tiết '+title}).waitFor()}
  const drawer=p.locator('.task-drawer');const deletion=drawer.getByRole('region',{name:'Xóa công việc',exact:true});
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động',{exact:true}).first().selectOption(f.workspace);
  await p.waitForFunction(w=>Object.entries(sessionStorage).some(([k,v])=>k.startsWith('pao.workspace.')&&v===w),f.workspace);
  step='native create and cancel delete';await reload();await p.getByRole('button',{name:'Công việc mới',exact:true}).click();
  const modal=p.getByRole('dialog',{name:'Tạo task',exact:true});await modal.getByLabel('Tiêu đề',{exact:true}).fill('Công việc tạo lỗi để xóa');await modal.getByLabel('Tiêu chí hoàn thành',{exact:true}).fill('Chỉ dữ liệu thử');await modal.getByRole('button',{name:'Tạo task',exact:true}).click();await modal.waitFor({state:'hidden'});
  await select('Công việc tạo lỗi để xóa');await deletion.getByRole('button',{name:'Xóa công việc',exact:true}).click();await deletion.getByRole('button',{name:'Giữ lại',exact:true}).click();
  let rows=await (await api('/v1/tasks?workspace_id='+f.workspace)).json();const task=rows.find(t=>t.title==='Công việc tạo lỗi để xóa');assert.ok(task);
  step='confirm delete';await deletion.getByRole('button',{name:'Xóa công việc',exact:true}).click();await deletion.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();await drawer.waitFor({state:'hidden'});assert.equal((await api('/v1/tasks/'+task.id)).status,404);
  await reload();assert.equal(await p.getByRole('heading',{name:task.title,exact:true}).count(),0);
  step='stale version denied';const stale=await create('Phiên bản đã đổi');await reload();await select(stale.title);await deletion.getByRole('button',{name:'Xóa công việc',exact:true}).click();
  assert.equal((await api('/v1/tasks/'+stale.id,'PATCH',{version:stale.version,description:'Cập nhật từ phiên khác'})).status,200);
  await deletion.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();await deletion.getByRole('alert').waitFor();assert.equal((await api('/v1/tasks/'+stale.id)).status,200);await reload();
  step='running disabled';const running=await create('Không xóa việc đang chạy',{status:'running'});await reload();await select(running.title);assert.equal(await deletion.getByRole('button',{name:'Xóa công việc',exact:true}).isDisabled(),true);await drawer.getByRole('button',{name:'Đóng task detail',exact:true}).click();
  step='lost response no automatic retry';const lost=await create('Mất phản hồi khi xóa');await reload();await select(lost.title);let deletes=0;
  await p.route('**/v1/tasks/'+lost.id+'?version=*',async route=>{if(route.request().method()!=='DELETE')return route.fallback();deletes++;const response=await route.fetch({url:f.api+'/v1/tasks/'+lost.id+'?version='+lost.version});assert.equal(response.status(),200);await route.abort('failed')});
  await deletion.getByRole('button',{name:'Xóa công việc',exact:true}).click();await deletion.getByRole('button',{name:'Xác nhận xóa',exact:true}).click();await deletion.getByRole('alert').waitFor();await p.waitForTimeout(1200);assert.equal(deletes,1);assert.equal((await api('/v1/tasks/'+lost.id)).status,404);await p.unroute('**/v1/tasks/'+lost.id+'?version=*');await reload();assert.equal(await p.getByRole('heading',{name:lost.title,exact:true}).count(),0);
  step='themes and narrow screens';await select(stale.title);await deletion.getByRole('button',{name:'Xóa công việc',exact:true}).click();
  for(const theme of ['light','dark']){await p.evaluate(t=>{document.documentElement.setAttribute('data-theme',t)},theme);await p.screenshot({path:f.folder+'/delete-'+theme+'.png',fullPage:false})}
  for(const width of [320,390]){await p.setViewportSize({width,height:844});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);await p.screenshot({path:f.folder+'/delete-'+width+'.png',fullPage:false})}
  assert.deepEqual(h.errors,[]);const result={pass:true,native_create_delete:true,keep_confirmation:true,stale_version_denied:true,running_disabled:true,lost_ack_no_retry:true,reload_verified:true,mobile:[320,390],themes:['light','dark'],provider_calls:false};fs.writeFileSync(f.folder+'/task-delete-browser.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }catch(e){console.error('Task deletion browser failure at '+step);await p.screenshot({path:f.folder+'/failure.png',fullPage:false});throw e}finally{await h.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
