// Isolated real HTTP backend on pao_test. Never logs tokens/connection strings.
const assert=require('node:assert/strict');
const {spawn,spawnSync}=require('node:child_process');
const net=require('node:net');
const path=require('node:path');
const {chromium}=require('playwright');
let stage='startup';
const httpFailures=[];
const httpChecks=[];
let diagnosticPage;

(async()=>{
  assert.ok((process.env.PAO_TEST_DATABASE_URL||'').endsWith('/pao_test'),'Dedicated pao_test required');
  const root=path.resolve(__dirname,'..');
  const probe=net.createServer();
  await new Promise((resolve,reject)=>{probe.once('error',reject);probe.listen(8101,'127.0.0.1',resolve)});
  await new Promise(resolve=>probe.close(resolve));
  const server=spawn(path.join(root,'.venv','Scripts','python.exe'),['-m','uvicorn','pao.main:app','--host','127.0.0.1','--port','8101','--no-access-log'],{
    cwd:root,windowsHide:true,stdio:'ignore',env:{...process.env,PAO_ROOT:root,PYTHONPATH:path.join(root,'apps','api'),
      DATABASE_URL:process.env.PAO_TEST_DATABASE_URL,RESULT_INBOX_ENABLED:'true',LEARNING_REVIEW_ENABLED:'true',
      BRAIN_MANAGER_ENABLED:'true',TEMPORAL_ENABLED:'false',GOAL_ADMISSION_ENABLED:'false',GOAL_ITERATIONS_ENABLED:'false',
      WORKFLOW_WORKER_ENABLED:'false',WORKFLOW_DISPATCH_ENABLED:'false',WORKFLOW_DURABLE_ENABLED:'false',
      META_ENABLED:'false',META_WRITE_ENABLED:'false',TELEGRAM_ENABLED:'false'}});
  let browser;
  try{
    stage='test-api';
    let ready=false;
    for(let i=0;i<60;i++){
      if(server.exitCode!==null)throw Error('Owned test API exited');
      try{if((await fetch('http://127.0.0.1:8101/health')).ok){ready=true;break}}catch{}
      await new Promise(resolve=>setTimeout(resolve,500));
    }
    assert.ok(ready,'Owned test API did not become healthy');
    stage='browser-launch';browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    diagnosticPage=page;
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    // Forward genuine HTTP responses rather than fixtures. Browser remains on
    // the real local Web; all backend mutations go only to the test database.
    await page.route('**/v1/**',async route=>{
      const url=new URL(route.request().url());
      const response=await route.fetch({url:'http://127.0.0.1:8101'+url.pathname+url.search});
      httpChecks.push({path:url.pathname,status:response.status()});
      if(!response.ok())httpFailures.push({path:url.pathname,status:response.status()});
      await route.fulfill({response});
    });
    stage='login';await page.goto('http://127.0.0.1:3200/');
    await page.getByLabel('Email',{exact:true}).fill('owner@example.test');
    await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');
    const profile=page.waitForResponse(response=>new URL(response.url()).pathname==='/v1/me'&&response.status()===200);
    await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
    await profile;
    await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor({state:'hidden'});
    await page.getByRole('button',{name:'Mở bảng điều khiển'}).waitFor();
    stage='inbox';await page.goto('http://127.0.0.1:3200/automation/review');
    await page.getByRole('heading',{name:'Kết quả dry-run',exact:true}).waitFor();
    await page.getByText('Đã xác nhận',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Xác nhận đã xem',exact:true}).isDisabled(),true);
    stage='learning';await page.getByRole('button',{name:'Learning có duyệt',exact:true}).click();
    const brains=page.getByLabel('Brain',{exact:true});
    await page.waitForFunction(()=>document.querySelector('select')?.options.length>1);
    stage='learning-brain';const brain=await brains.locator('option').nth(1).getAttribute('value');await brains.selectOption(brain);
    const sessions=page.getByLabel('Hội thoại',{exact:true});
    stage='learning-session';await sessions.locator('option').nth(1).waitFor({state:'attached'});
    const source=page.getByLabel('Nguồn',{exact:true});
    // Login may create an empty chat. Select the source-bearing fixture,
    // never assume the first session is the fixture.
    let found=false;
    for(const value of await sessions.locator('option').evaluateAll(options=>options.map(o=>o.value).filter(Boolean))){
      await sessions.selectOption(value);
      await page.getByRole('button',{name:'Tạo đề xuất, chưa lưu kiến thức',exact:true}).waitFor();
      await page.waitForFunction(()=>!document.querySelector('select')?.disabled);
      if(await source.locator('option').filter({hasText:'Việt Nam'}).count()){found=true;break}
    }
    assert.ok(found,'Fixture message unavailable in owned sessions');
    stage='learning-message';await source.locator('option').nth(1).waitFor({state:'attached'});
    await source.selectOption(await source.locator('option').nth(1).getAttribute('value'));
    await page.getByLabel('Trích đoạn',{exact:true}).fill('Việt Nam');
    stage='learning-proposal';await page.getByRole('button',{name:'Tạo đề xuất, chưa lưu kiến thức',exact:true}).click();
    await page.getByRole('button',{name:'Duyệt lưu ghi chú',exact:true}).waitFor();
    page.on('dialog',dialog=>dialog.accept());
    await page.getByRole('button',{name:'Duyệt lưu ghi chú',exact:true}).click();
    const promoted=page.locator('article').filter({has:page.locator('pre').filter({hasText:/^Việt Nam$/})});
    await promoted.getByRole('button',{name:'Hoàn tác ghi chú',exact:true}).waitFor();
    await promoted.getByRole('button',{name:'Hoàn tác ghi chú',exact:true}).click();
    await promoted.getByText('Trạng thái: reverted',{exact:true}).waitFor();
    stage='schedule';await page.getByRole('button',{name:'Xem trước lịch',exact:true}).click();
    await page.getByRole('button',{name:'Xem trước, không tạo job',exact:true}).click();
    await page.getByLabel('Kết quả xem trước').waitFor();
    const result=JSON.parse(await page.getByLabel('Kết quả xem trước').innerText());
    assert.equal(result.preview_only,true);assert.equal(result.execution_enabled,false);
    stage='outcome';await page.getByRole('button',{name:'Outcome',exact:true}).click();
    await page.getByRole('heading',{name:'Outcome 24h / 72h / 7d',exact:true}).waitFor();
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({pass:true,real_http_backend:true,database:'pao_test',inbox_ack_verified:true,
      learning_propose_promote_revert:true,schedule_preview_only:true,outcome_form:true,
      goal_runner_enabled:false,external_send:false}));
  }finally{
    if(diagnosticPage&&stage!=='outcome')console.log(JSON.stringify({stage,http_failures:httpFailures,http_checks:httpChecks,url_path:new URL(diagnosticPage.url()).pathname,headings:await diagnosticPage.locator('h1,h2').allTextContents().catch(()=>[]),select_counts:await diagnosticPage.locator('select').evaluateAll(nodes=>nodes.map(n=>n.options.length)).catch(()=>[]),inbox_articles:await diagnosticPage.locator('article').count().catch(()=>0)}));
    if(browser)await browser.close();
    if(server.exitCode===null){
      if(process.platform==='win32')spawnSync('taskkill.exe',['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
      else server.kill('SIGTERM');
    }
  }
})().catch(error=>{const reason=String(error.message).split('\n')[0].replace(/postgresql[^\s]+/gi,'[redacted-db]');console.error('P6 browser failed at '+stage+': '+reason);process.exitCode=1});
