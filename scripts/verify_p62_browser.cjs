// Real HTTP fixture API only; no fabricated API responses or live business DB.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
 const fixture = process.env.PAO_P62_FIXTURE_API;
 assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(fixture || ''));
 const ids = JSON.parse(process.env.PAO_P62_PLAN_IDS);
 const browser = await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 try {
  const page = await browser.newPage();
  const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/v1/**',async route=>{
   const u = new URL(route.request().url());
   const response=await route.fetch({url:fixture+u.pathname+u.search});
   await route.fulfill({response});
  });
  await page.goto((process.env.PAO_FRONTEND_URL||'http://127.0.0.1:3200')+'/skills');
  await page.getByLabel('Email',{exact:true}).fill('owner@example.test');
  await page.getByLabel('Mật khẩu',{exact:true}).fill('test-password-123');
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
  await page.goto((process.env.PAO_FRONTEND_URL||'http://127.0.0.1:3200')+'/skills');
  const runner=page.getByRole('region',{name:'P6.2 workflow runner',exact:true});
  await runner.waitFor({timeout:30000});
  async function status(text){await runner.getByLabel('Workflow execution status').filter({hasText:text}).waitFor({timeout:30000});}
  async function start(id){
   await runner.getByLabel('Workflow runner plan ID').fill(id);
   await runner.getByRole('button',{name:'Mở kế hoạch chạy thử',exact:true}).click();
   await runner.getByLabel('Workflow runner readiness').filter({hasText:'Worker sẵn sàng'}).waitFor({timeout:15000});
   assert(await runner.getByRole('button',{name:'Bắt đầu chạy giả lập',exact:true}).isDisabled());
   await runner.getByRole('checkbox').check();
   await runner.getByRole('button',{name:'Bắt đầu chạy giả lập',exact:true}).click();
   await status('waiting_approval');
  }
  await start(ids[0]);
  await runner.getByRole('button',{name:'Duyệt bước hiện tại',exact:true}).click();
  await status('waiting_approval · bước second');
  await runner.getByRole('button',{name:'Duyệt bước hiện tại',exact:true}).click();
  await status('completed');
  await start(ids[1]);
  await runner.getByRole('button',{name:'Từ chối bước hiện tại',exact:true}).click();
  await status('cancelled');
  await start(ids[2]);
  await runner.getByRole('button',{name:'Yêu cầu hủy workflow',exact:true}).click();
  await status('cancelled');
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({real_http:true,completed:true,rejected:true,cancelled:true,ack_gate:true,page_errors:0}));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
