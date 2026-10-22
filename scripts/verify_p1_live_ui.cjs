// Uses real scoped test API responses; no mock feature/data responses.
const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
  const api=process.env.PAO_P1_BROWSER_API;
  assert.equal(api,'http://127.0.0.1:18100');assert.ok(process.env.PAO_P1_BROWSER_PASSWORD);
  const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
  try{
    const page=await browser.newPage();
    await page.route('**/v1/**',async route=>{
      const url=new URL(route.request().url());
      const response=await route.fetch({url:api+url.pathname+url.search});await route.fulfill({response});
    });
    await page.goto(process.env.PAO_FRONTEND_URL);
    await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');
    await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);
    await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
    await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
    await page.getByRole('button',{name:'Mở bảng điều khiển'}).waitFor();
    await page.goto(new URL('/knowledge',process.env.PAO_FRONTEND_URL).href);
    const panel=page.getByRole('region',{name:'Brain Manager'});
    await panel.getByLabel('Tên Brain').fill('Browser Source');await panel.getByRole('button',{name:'Tạo Brain',exact:true}).click();
    console.log('P1 real UI: authenticated/create source');
    await panel.getByText('Đã tạo Brain riêng tư.',{exact:true}).waitFor();
    // Notice is set after POST, before the refreshed list has hydrated the select.
    await page.waitForFunction(()=>{
      const select=document.querySelector('[aria-label="Chọn Brain"]');
      return select?.value && !select.disabled && select.selectedOptions[0]?.textContent==='Browser Source';
    });
    const sourceId=await panel.getByLabel('Chọn Brain').inputValue();assert.ok(sourceId);
    await panel.getByLabel('Upload file Brain').setInputFiles({name:'source.md',mimeType:'text/markdown',buffer:Buffer.from('<script>window.p1Unsafe=true</script>')});
    await panel.getByRole('button',{name:'Preview source.md',exact:true}).waitFor();
    await panel.getByRole('button',{name:'Preview source.md',exact:true}).click();
    await panel.locator('pre').filter({hasText:'window.p1Unsafe'}).waitFor();assert.equal(await page.evaluate(()=>window.p1Unsafe),undefined);
    await panel.getByLabel('Tiêu đề note').fill('Versioned note');await panel.getByLabel('Nội dung note').fill('First version');
    await panel.getByRole('button',{name:'Tạo note',exact:true}).click();await panel.getByRole('button',{name:'Lưu phiên bản note'}).waitFor();
    await panel.getByLabel('Nội dung note').fill('Second version');await panel.getByRole('button',{name:'Lưu phiên bản note'}).click();
    await panel.getByText('r2 / content v2',{exact:false}).waitFor();
    await panel.getByLabel('Note version').fill('1');await panel.getByRole('button',{name:'Xem note version'}).click();
    await panel.locator('pre').filter({hasText:'First version'}).waitFor();
    const context=page.context(),credential=await page.evaluate(()=>sessionStorage.getItem('pao.access_token'));
    const exported=await context.request.get(`${api}/v1/brains/${sourceId}/export`,{headers:{Authorization:`Bearer ${credential}`}});assert.equal(exported.status(),200);const zip=await exported.body();
    await panel.getByLabel('Tên Brain').fill('Browser Target');await panel.getByRole('button',{name:'Tạo Brain',exact:true}).click();
    await panel.getByRole('option',{name:'Browser Target',exact:true}).waitFor({state:'attached'});
    await page.waitForFunction(()=>{
      const select=document.querySelector('[aria-label="Chọn Brain"]');
      return select?.value && !select.disabled && select.selectedOptions[0]?.textContent==='Browser Target';
    });
    await panel.getByLabel('Import Brain ZIP').setInputFiles({name:'snapshot.zip',mimeType:'application/zip',buffer:zip});
    const confirm=panel.getByRole('button',{name:'Xác nhận import',exact:true});await confirm.waitFor();assert.equal(await confirm.isDisabled(),true);
    assert.equal(await panel.getByRole('button',{name:'Preview source.md',exact:true}).count(),0);
    await panel.getByLabel('Tôi xác nhận thêm bản sao').check();await confirm.click();await panel.getByText('Import hoàn tất trong một transaction.',{exact:true}).waitFor();
    await panel.getByRole('button',{name:'Preview source.md',exact:true}).waitFor();await panel.getByRole('button',{name:'Versioned note',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('[aria-label="Nội dung note"]')?.value==='Second version');
    assert.equal(await panel.getByLabel('Nội dung note').inputValue(),'Second version');
    await panel.getByRole('button',{name:'Trash source.md',exact:true}).click();await panel.getByLabel('Hiện cả trash').check();
    await panel.getByRole('button',{name:'Restore source.md',exact:true}).waitFor();await panel.getByRole('button',{name:'Restore source.md',exact:true}).click();
    await panel.getByRole('button',{name:'Preview source.md',exact:true}).waitFor();
    console.log('PASS real test-backend Browser Brain/files/plain preview/no script execution/Note versions/dry-run confirmation/import/trash restore');
  }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exit(1)});
