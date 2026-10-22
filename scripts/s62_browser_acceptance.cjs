const fs=require('fs');
const path=require('path');
const {chromium}=require('F:/PAO-ACOS/node_modules/playwright');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const out=path.dirname(process.argv[2]);
const assert=(value,message)=>{if(!value)throw new Error(message)};
async function login(page,email,password){
 await page.goto(fixture.web,{waitUntil:'domcontentloaded'});
 await page.getByLabel('Email',{exact:true}).fill(email);
 await page.getByLabel('Mật khẩu',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
 await page.getByRole('combobox',{name:'Doanh nghiệp đang hoạt động'}).waitFor({timeout:45000});
}
async function selectEnterprise(page,id){
 await page.getByRole('combobox',{name:'Doanh nghiệp đang hoạt động'}).selectOption(id);
 await page.waitForFunction(value=>Object.keys(sessionStorage).some(key=>key.startsWith('pao.workspace.')&&sessionStorage.getItem(key)===value),id);
}
async function secureContext(browser){
 const context=await browser.newContext({acceptDownloads:true});
 await context.route('**/*',route=>{
  const url=new URL(route.request().url());
  if(url.hostname!=='127.0.0.1'||url.pathname==='/api/weather')return route.abort();
  return route.continue();
 });
 return context;
}
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const results={real_api_db:true,provider_calls:false,pass:false};
 let activePage;
 const errors=[];
 try{
  const context=await secureContext(browser),page=await context.newPage();
  activePage=page;
  page.on('pageerror',error=>errors.push(error.message));
  page.on('requestfailed',request=>errors.push({path:new URL(request.url()).pathname,error:request.failure()?.errorText}));
  page.on('dialog',dialog=>dialog.accept());
  await login(page,fixture.owner,fixture.password);
  await selectEnterprise(page,fixture.alpha);
  await page.goto(fixture.web+'/settings',{waitUntil:'domcontentloaded'});
  const panel=page.getByRole('region',{name:'Quản lý tài khoản và dữ liệu SaaS'});
  await panel.waitFor({timeout:45000});
  await panel.getByRole('button',{name:'Đọc phiên đăng nhập',exact:true}).click();
  await panel.getByText(/Phiên hiện tại · Còn hiệu lực/).waitFor();
  const invitation=panel.getByRole('group',{name:'Mời nhân viên',exact:true});
  await invitation.getByLabel('Email người nhận').fill('staff-s62@example.test');
  await invitation.getByRole('button',{name:'Tạo mã mời',exact:true}).click();
  const codeInput=invitation.getByLabel('Mã mời — chỉ hiển thị lần này');
  await codeInput.waitFor();
  const code=await codeInput.inputValue();
  assert(code.length>=40,'Invitation code missing');
  results.invitation_created=true;
  const joining=await secureContext(browser),join=await joining.newPage();
  await join.goto(fixture.web+'/join',{waitUntil:'domcontentloaded'});
  await join.getByLabel('Email được mời').fill('staff-s62@example.test');
  await join.getByLabel('Mã mời',{exact:true}).fill(code);
  await join.getByLabel('Mật khẩu cho tài khoản mới — tối thiểu 12 ký tự').fill(fixture.password);
  await join.getByRole('button',{name:'Nhận lời mời',exact:true}).click();
  await join.getByRole('status').filter({hasText:'Đã tham gia doanh nghiệp'}).waitFor();
  results.invitation_accepted_in_browser=true;
  await panel.getByRole('button',{name:'Đọc thành viên',exact:true}).click();
  const memberGroup=panel.getByRole('group',{name:'Thành viên doanh nghiệp',exact:true});
  await memberGroup.getByText(/staff-s62@example.test/).waitFor();
  await selectEnterprise(page,fixture.beta);
  await panel.getByRole('button',{name:'Đọc thành viên',exact:true}).click();
  await memberGroup.getByText(/owner-s62@example.test/).waitFor();
  assert(await memberGroup.getByText(/staff-s62@example.test/).count()===0,'Tenant leakage');
  results.two_sme_ui_isolation=true;
  assert(await invitation.getByLabel('Mã mời — chỉ hiển thị lần này').count()===0,'Code retained across SME switch');
  await selectEnterprise(page,fixture.alpha);
  const downloading=page.waitForEvent('download');
  await panel.getByRole('button',{name:'Tạo và tải bản xuất',exact:true}).click();
  const download=await downloading;const exportPath=path.join(out,'synthetic-export.json');await download.saveAs(exportPath);
  const exported=JSON.parse(fs.readFileSync(exportPath,'utf8'));
  assert(exported.workspace_id===fixture.alpha,'Export scope mismatch');
  assert(!JSON.stringify(exported).includes(fixture.password),'Password leaked');
  results.export_real_download=true;
  await panel.getByRole('button',{name:'Xem trước phạm vi yêu cầu xóa',exact:true}).click();
  await panel.getByRole('button',{name:'Tạo yêu cầu — chưa xóa',exact:true}).click();
  await panel.getByRole('button',{name:'Xác nhận yêu cầu — không tự xóa',exact:true}).click();
  await panel.getByText(/Đã xác nhận, chưa xóa/).waitFor();
  results.deletion_request_confirmed_without_purge=true;
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),'Mobile overflow');
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  results.mobile_390=true;
  await panel.getByRole('button',{name:'Đọc thành viên',exact:true}).click();
  const staff=memberGroup.locator('li').filter({hasText:'staff-s62@example.test'});
  await staff.getByRole('button',{name:'Gỡ khỏi doanh nghiệp',exact:true}).click();
  await staff.waitFor({state:'detached'});
  results.member_removed=true;
  await panel.getByRole('button',{name:'Đăng xuất tất cả phiên',exact:true}).click();
  await page.getByRole('heading',{name:'Đăng nhập',exact:true}).waitFor({timeout:20000});
  results.server_logout_all=true;
  results.pass=true;
 }catch(error){if(activePage&&!activePage.isClosed()){await activePage.screenshot({path:path.join(out,'failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'failure-dom.txt'),await activePage.locator('body').innerText());}fs.writeFileSync(path.join(out,'browser-errors.json'),JSON.stringify(errors,null,2));throw error;
 }finally{await browser.close();fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify(results,null,2));}
 console.log(JSON.stringify(results));
})().catch(error=>{console.error(error.message);process.exitCode=1});
