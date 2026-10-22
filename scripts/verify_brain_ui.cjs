// Browser UI contract with mocks only. No real database/provider writes.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
  const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
  try{
    const page=await browser.newPage();
    const wid='11111111-1111-4111-8111-111111111111';
    let rows=[],enabled=true;
    await page.route('**/v1/**',async route=>{
      const url=new URL(route.request().url()),method=route.request().method();
      let body=[];
      if(url.pathname==='/v1/auth/token')body={access_token:'mock-token',token_type:'bearer',expires_in:3600};
      if(url.pathname==='/v1/me')body={id:'owner',email:'owner@example.test',workspaces:[{id:wid,name:'Test workspace',role:'owner'}]};
      if(url.pathname==='/v1/brains/status')body={enabled,rag_enabled:false,file_types:['text/plain','text/markdown']};
      if(url.pathname==='/v1/brains'){
        if(method==='POST'){
          const data=route.request().postDataJSON();
          body={id:'22222222-2222-4222-8222-222222222222',workspace_id:wid,owner_id:'owner',brand_id:null,name:data.name,legacy_default:false,revision:1,archived_at:null,created_at:'2026-10-06T00:00:00Z'};
          rows.push(body);
        }else body=rows.filter(row=>url.searchParams.get('archived')==='true'||!row.archived_at);
      }
      if(url.pathname.startsWith('/v1/brains/')&&method==='PATCH'){
        const data=route.request().postDataJSON();
        assert.equal(data.revision,rows[0].revision);
        rows[0]={...rows[0],...(data.name?{name:data.name}:{}),...(data.archived!==undefined?{archived_at:data.archived?'2026-10-06T01:00:00Z':null}:{}),revision:rows[0].revision+1};
        body=rows[0];
      }
      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
    });
    const root=process.env.PAO_FRONTEND_URL||'http://127.0.0.1:3200/';
    await page.goto(root);
    await page.getByLabel('Email',{exact:true}).fill('owner@example.test');
    await page.getByLabel('Mật khẩu',{exact:true}).fill('mock-only');
    await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
    await page.getByRole('button',{name:'Mở bảng điều khiển'}).waitFor();
    await page.goto(new URL('/knowledge',root).href);
    const panel=page.getByRole('region',{name:'Brain Manager'});
    await panel.getByLabel('Tên Brain').waitFor();
    await panel.getByLabel('Tên Brain').fill('Marketing');
    await panel.getByRole('button',{name:'Tạo Brain',exact:true}).click();
    await panel.getByText('Đã tạo Brain riêng tư.',{exact:true}).waitFor();
    // POST notice precedes the refreshed list/select hydration.
    await page.waitForFunction(()=>document.querySelector('[aria-label="Chọn Brain"]')?.value==='22222222-2222-4222-8222-222222222222');
    assert.equal(await panel.getByLabel('Chọn Brain').inputValue(),rows[0].id);
    await panel.getByLabel('Tên Brain').fill('Marketing renamed');
    await panel.getByRole('button',{name:'Đổi tên bằng tên nhập trên'}).click();
    await panel.getByRole('option',{name:'Marketing renamed',exact:true}).waitFor({state:'attached'});
    await panel.getByRole('button',{name:'Archive Brain',exact:true}).click();
    await panel.getByText('Đã cập nhật archive; dữ liệu không bị xóa.',{exact:true}).waitFor();
    await page.waitForFunction(()=>document.querySelector('[aria-label="Chọn Brain"]')?.value==='');
    assert.equal(await panel.getByLabel('Chọn Brain').inputValue(),'');
    await panel.getByLabel('Hiện cả archived').check();
    await panel.getByRole('button',{name:'Phục hồi Brain',exact:true}).waitFor();
    await panel.getByRole('button',{name:'Phục hồi Brain',exact:true}).click();
    await panel.getByRole('option',{name:'Marketing renamed',exact:true}).waitFor({state:'attached'});
    assert.equal(rows[0].archived_at,null);
    assert.equal(await panel.getByRole('button',{name:'Gắn với hội thoại đang chọn'}).isDisabled(),true);
    enabled=false;
    await panel.getByRole('button',{name:'Tải lại Brain'}).click();
    await panel.getByText('CHƯA BẬT',{exact:true}).waitFor();
    console.log('PASS Brain UI create/select/rename/archive/restore/gated state (mock only)');
  }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exit(1)});
