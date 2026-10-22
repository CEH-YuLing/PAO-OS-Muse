// Real test API and real dedicated ARQ worker; no mocks for data/features.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
  const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
  const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
  try{
    const page=await browser.newPage();
    await page.route('**/v1/**',async route=>{const url=new URL(route.request().url());const response=await route.fetch({url:api+url.pathname+url.search});await route.fulfill({response});});
    await page.goto(process.env.PAO_FRONTEND_URL);
    await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');
    await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);
    await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
    await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
    await page.goto(new URL('/knowledge',process.env.PAO_FRONTEND_URL).href);
    const panel=page.getByRole('region',{name:'Brain Manager'}),sources=page.getByRole('region',{name:'Brain Sources'});
    await panel.getByLabel('Tên Brain').fill('Sources Browser');await panel.getByRole('button',{name:'Tạo Brain',exact:true}).click();
    await page.waitForFunction(()=>{const s=document.querySelector('[aria-label="Chọn Brain"]');return s?.value&&!s.disabled&&s.selectedOptions[0]?.textContent==='Sources Browser'});
    await panel.getByLabel('Upload file Brain').setInputFiles({name:'sop.md',mimeType:'text/markdown',buffer:Buffer.from('# SOP\r\nReturn within 7 days.\r\n<script>window.sourceUnsafe=true</script>')});
    await panel.getByRole('button',{name:'Preview sop.md',exact:true}).waitFor();
    await sources.getByLabel('Origin nguồn').selectOption({label:'sop.md'});
    await sources.getByRole('button',{name:'Đăng ký nguồn',exact:true}).click();
    const fileRow=sources.getByRole('listitem').filter({hasText:'sop.md'});
    await expectCompleted(fileRow,sources);
    await sources.getByRole('button',{name:'Chọn source sop.md',exact:true}).click();
    await sources.getByRole('button',{name:'Preview source version',exact:true}).click();
    await sources.getByLabel('Source plain preview').filter({hasText:'Return within 7 days.'}).waitFor();
    assert.equal(await page.evaluate(()=>window.sourceUnsafe),undefined);
    await sources.getByRole('button',{name:'Đăng ký nguồn',exact:true}).click();
    await sources.getByRole('button',{name:'Tải lại Sources',exact:true}).waitFor({state:'visible'});
    assert.equal(await fileRow.count(),1);
    await panel.getByLabel('Tiêu đề note').fill('Versioned SOP');await panel.getByLabel('Nội dung note').fill('First source version');
    await panel.getByRole('button',{name:'Tạo note',exact:true}).click();
    await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Lưu phiên bản note');return b&&!b.disabled});
    await sources.getByLabel('Loại nguồn').selectOption('note');await sources.getByLabel('Origin nguồn').selectOption({label:'Versioned SOP'});
    await sources.getByRole('button',{name:'Đăng ký nguồn',exact:true}).click();
    const noteRow=sources.getByRole('listitem').filter({hasText:'Versioned SOP'});await expectCompleted(noteRow,sources);
    await panel.getByLabel('Nội dung note').fill('Second source version');await panel.getByRole('button',{name:'Lưu phiên bản note',exact:true}).click();
    await noteRow.getByText('Stale: origin đã đổi',{exact:false}).waitFor();
    await sources.getByRole('button',{name:'Refresh source Versioned SOP',exact:true}).click();await expectCompleted(noteRow,sources);
    await sources.getByRole('button',{name:'Chọn source Versioned SOP',exact:true}).click();
    await sources.getByLabel('Source version').fill('1');await sources.getByRole('button',{name:'Preview source version',exact:true}).click();
    await sources.getByLabel('Source plain preview').filter({hasText:'First source version'}).waitFor();
    await sources.getByLabel('Source version').fill('2');await sources.getByRole('button',{name:'Preview source version',exact:true}).click();
    await sources.getByLabel('Source plain preview').filter({hasText:'Second source version'}).waitFor();
    console.log('PASS real browser + API + ARQ source registration/dedupe/hash/line preview/no script execution/note stale-refresh/v1-v2');
  }finally{await browser.close();}
  async function expectCompleted(row,sources){
    const deadline=Date.now()+20000;
    while(Date.now()<deadline){
      await sources.getByRole('button',{name:'Tải lại Sources',exact:true}).click();
      if(await row.getByText('completed',{exact:true}).count())return;
      // Browser polls actual DB job status; this is not a simulated worker clock.
      await new Promise(resolve=>setTimeout(resolve,300));
    }
    throw Error('Source did not complete through real worker within20s');
  }
})().catch(error=>{console.error(error.message);process.exit(1)});
