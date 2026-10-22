const assert=require('node:assert/strict');const fs=require('node:fs');const {open}=require('./p6_browser_harness.cjs');
const f=JSON.parse(process.env.PAO_OUTCOME_BROWSER_FIXTURE||'null');let stage='launch';
(async()=>{let drop=true,first=null;const h=await open(f,{intercept:async(route,response)=>{
 const req=route.request(),u=new URL(req.url());if(req.method()==='POST'&&u.pathname===`/v1/ads/actions/${f.action}/outcome-observations`){
  if(drop){assert.equal(response.status(),201);first=req.postData();drop=false;await route.abort();return true}assert.equal(first,req.postData());
 }return false;
}}),p=h.page;
 async function tab(){await p.getByRole('button',{name:'Outcome',exact:true}).click();await p.getByRole('heading',{name:'Quan sát outcome đã lưu',exact:true}).waitFor()}
 async function preview(id,status){await p.getByLabel('Outcome action ID').fill(id);await p.getByRole('button',{name:'Xem trước quan sát có nguồn',exact:true}).click();await p.getByLabel('Outcome preview').getByRole('heading',{name:`7d · ${status}`,exact:true}).waitFor();assert.equal(await p.getByRole('button',{name:'Lưu quan sát có nguồn',exact:true}).isDisabled(),true);await p.getByLabel('Confirm outcome observation').check();}
 try{
  stage='login';await h.login();await p.goto(f.web+'/automation/review');await tab();
  stage='observed-preview';await preview(f.action,'observed');await p.getByRole('button',{name:'Lưu quan sát có nguồn',exact:true}).click();
  stage='lost-ack';await p.getByRole('button',{name:'Thử lại đúng quan sát',exact:true}).waitFor();await p.getByRole('button',{name:'Thử lại đúng quan sát',exact:true}).click();await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).waitFor();assert.equal(await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).count(),1);
  await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).click();await p.getByLabel('Stored outcome snapshot').getByText('Nguồn hiện tại vẫn khớp snapshot',{exact:true}).waitFor();
  stage='source-changed';fs.writeFileSync(f.marker,'ready');
  for(let i=0;i<40;i++){await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).click();if((await p.getByLabel('Stored outcome snapshot').innerText()).includes('Nguồn đã thay đổi'))break;await p.waitForTimeout(250)}
  await p.getByLabel('Stored outcome snapshot').getByText(/Nguồn đã thay đổi/).waitFor();await p.getByLabel('Stored outcome snapshot').getByRole('heading',{name:'7d · observed',exact:true}).waitFor();
  stage='insufficient';await preview(f.insufficient,'insufficient');await p.getByRole('button',{name:'Lưu quan sát có nguồn',exact:true}).click();await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).waitFor();await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).click();await p.getByLabel('Stored outcome snapshot').getByRole('heading',{name:'7d · insufficient',exact:true}).waitFor();
  stage='reload';await p.reload();await tab();await p.getByLabel('Outcome action ID').fill(f.action);await p.getByRole('button',{name:'Đọc lịch sử quan sát',exact:true}).click();await p.getByRole('button',{name:'Mở snapshot đã lưu',exact:true}).click();await p.getByLabel('Stored outcome snapshot').getByRole('heading',{name:'7d · observed',exact:true}).waitFor();
  stage='mobile';await h.mobile();console.log(JSON.stringify({pass:true,real_http:true,synthetic_warehouse:true,live_meta_accepted:false,preview_capture_history:true,lost_ack_same_key:true,stale_snapshot_preserved:true,insufficient_not_success:true,reload:true,mobile_width:390,page_errors:0}));
 }catch(e){console.error('P6 browser failed at '+stage+': '+String(e.message).split('\n')[0]);throw e}finally{await h.close()}
})().catch(()=>{process.exitCode=1});
