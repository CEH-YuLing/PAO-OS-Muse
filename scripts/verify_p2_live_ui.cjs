// Real isolated API + real ARQ parse/index/grounded chat; no feature mocks/models.
const assert=require('node:assert/strict'),{randomUUID}=require('node:crypto'),{chromium}=require('playwright');
(async()=>{
  const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
  const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
  let stage='login',closing=false,page;
  try{
    page=await browser.newPage();
    const routeErrors=[];
    await page.route('**/v1/**',async route=>{const url=new URL(route.request().url());try{const response=await route.fetch({url:api+url.pathname+url.search});await route.fulfill({response})}catch(error){if(!closing&&!page.isClosed()&&!/aborted|closed/i.test(error.message))routeErrors.push(url.pathname);await route.abort().catch(()=>{})}});
    await page.goto(process.env.PAO_FRONTEND_URL);await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
    await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
    const credential=await page.evaluate(()=>sessionStorage.getItem('pao.access_token')),headers={Authorization:`Bearer ${credential}`};
    async function call(path,method='GET',data){const response=await page.request.fetch(api+path,{method,headers,data});assert.ok(response.ok(),`${method} ${path}: ${response.status()}`);return response.status()===204?null:await response.json()}
    async function until(action,predicate,label){const end=Date.now()+25000;while(Date.now()<end){const value=await action();if(predicate(value))return value;await new Promise(resolve=>setTimeout(resolve,300))}throw Error(label+' did not complete through real worker')}
    stage='source/index';await page.goto(new URL('/knowledge',process.env.PAO_FRONTEND_URL).href);
    const panel=page.getByRole('region',{name:'Brain Manager'}),sources=page.getByRole('region',{name:'Brain Sources'}),knowledge=page.getByRole('region',{name:'Knowledge P2'});
    await panel.getByLabel('Tên Brain').fill('P2 Browser');await panel.getByRole('button',{name:'Tạo Brain',exact:true}).click();
    await page.waitForFunction(()=>{const s=document.querySelector('[aria-label="Chọn Brain"]');return s?.value&&!s.disabled&&s.selectedOptions[0]?.textContent==='P2 Browser'});
    const bid=await panel.getByLabel('Chọn Brain').inputValue(),base='/v1/brains/'+bid;
    await panel.getByLabel('Upload file Brain').setInputFiles({name:'sop.md',mimeType:'text/markdown',buffer:Buffer.from('# SOP\nReturn policy: 7 days.\n[[FAQ]]\n<script>window.p2Unsafe=true</script>')});await panel.getByRole('button',{name:'Preview sop.md',exact:true}).waitFor();
    await sources.getByLabel('Origin nguồn').selectOption({label:'sop.md'});await sources.getByRole('button',{name:'Đăng ký nguồn',exact:true}).click();
    await until(()=>call(base+'/index-jobs'),v=>v.some(j=>j.status==='completed'),'Index');
    stage='retrieval/wiki';await knowledge.getByLabel('Tìm trong nguồn').fill('Return policy');await knowledge.getByRole('button',{name:'Tìm nguồn',exact:true}).click();await knowledge.locator('pre').filter({hasText:'Return policy: 7 days.'}).waitFor();assert.equal(await page.evaluate(()=>window.p2Unsafe),undefined);
    await knowledge.getByLabel('Tiêu đề Wiki').fill('Returns Wiki');await knowledge.getByRole('button',{name:'Tạo Wiki draft từ nguồn',exact:true}).click();await knowledge.getByLabel('Nội dung Wiki').waitFor();
    await until(()=>call(base+'/wiki'),v=>v.length===1,'Wiki draft');let wiki=(await call(base+'/wiki'))[0];assert.equal(wiki.published_version,null);
    assert.equal(await knowledge.getByRole('button',{name:'Publish Wiki đã duyệt',exact:true}).isDisabled(),true);
    await knowledge.getByLabel('Đã duyệt Wiki').check();await knowledge.getByRole('button',{name:'Publish Wiki đã duyệt',exact:true}).click();await until(()=>call(base+'/wiki'),v=>v[0]?.published_version===1,'Wiki publish');
    await knowledge.getByLabel('Nội dung Wiki').fill('Reviewed policy: 7 days.\n[[FAQ]]');await knowledge.getByRole('button',{name:'Lưu phiên bản Wiki',exact:true}).click();await until(()=>call(base+'/wiki'),v=>v[0]?.current_version===2,'Wiki edit');
    await knowledge.getByLabel('Wiki version').fill('1');await knowledge.getByRole('button',{name:'Xem diff Wiki',exact:true}).click();await knowledge.locator('pre').filter({hasText:'Reviewed policy'}).waitFor();
    await knowledge.getByLabel('Đã duyệt Wiki').check();await knowledge.getByRole('button',{name:'Publish Wiki đã duyệt',exact:true}).click();await until(()=>call(base+'/wiki'),v=>v[0]?.published_version===2,'Wiki publish2');
    await knowledge.getByLabel('Wiki version').fill('1');await knowledge.getByRole('button',{name:'Xem Wiki version',exact:true}).click();await until(async()=>knowledge.getByLabel('Nội dung Wiki').inputValue(),v=>v.includes('Nguồn 1'),'Historical Wiki UI');await knowledge.getByLabel('Đã duyệt Wiki').check();await knowledge.getByRole('button',{name:'Revert bản đã từng publish',exact:true}).click();await until(()=>call(base+'/wiki'),v=>v[0]?.published_version===1,'Wiki revert');
    stage='graph';await panel.getByLabel('Tiêu đề note').fill('FAQ');await panel.getByLabel('Nội dung note').fill('See [[Returns Wiki]] and [[Unresolved]].');await panel.getByRole('button',{name:'Tạo note',exact:true}).click();await panel.getByRole('button',{name:'Lưu phiên bản note',exact:true}).waitFor();
    await knowledge.getByRole('button',{name:'Rebuild Graph dẫn xuất',exact:true}).click();await knowledge.getByRole('img',{name:'Knowledge Graph'}).waitFor();const graph=await call(base+'/graph');assert.equal(graph.nodes.length,2);assert.ok(graph.edges.length>=2);assert.ok(graph.unresolved.some(n=>n.label==='Unresolved'));
    stage='chat/attachment';const me=await call('/v1/me'),sid=(await call('/v1/sessions','POST',{workspace_id:me.workspaces[0].id,title:'P2 Browser Chat'})).id;
    const association=await call('/v1/sessions/'+sid+'/brain');await call('/v1/sessions/'+sid+'/brain','PUT',{brain_id:bid,version:association.version});
    await page.goto(new URL('/pao-ai',process.env.PAO_FRONTEND_URL).href);
    await page.getByRole('button').filter({hasText:'P2 Browser Chat'}).first().click();const chat=page.getByLabel('Nguồn trong chat');await chat.locator('summary').click();await chat.getByLabel('Dùng nguồn trong chat').check();await chat.getByLabel('Phạm vi nguồn chat').selectOption('attachments');
    await until(()=>call('/v1/sessions/'+sid+'/knowledge'),v=>v.enabled&&v.scope==='attachments','Chat context');
    await chat.getByLabel('Đính kèm file chat').setInputFiles({name:'delivery.txt',mimeType:'text/plain',buffer:Buffer.from('Delivery policy: 3 days.')});await chat.getByText('delivery.txt · 24 bytes',{exact:false}).waitFor();
    const files=await until(()=>call('/v1/sessions/'+sid+'/attachments'),v=>v.length===1,'Attachment');
    await until(()=>call(base+'/index-jobs'),v=>v.length===2&&v.every(j=>j.status==='completed'),'Attachment index');
    await page.getByLabel('Nội dung yêu cầu PAO').fill('Delivery policy');await page.getByRole('button',{name:'Gửi yêu cầu',exact:true}).click();
    const run=await until(async()=>{const response=await call('/v1/sessions/'+sid);return response},v=>v.messages?.some(m=>m.role==='assistant'&&m.content.includes('Delivery policy: 3 days.')),'Grounded chat');
    const message=run.messages.find(m=>m.role==='assistant');assert.ok(!message.content.includes('Return policy: 7 days.'));
    const stream=await page.request.get(api+'/v1/runs/'+message.run_id+'/events',{headers,timeout:5000});assert.equal(stream.status(),200);const streamText=await stream.text();assert.ok(streamText.includes('knowledge_retrieval')&&streamText.includes('run.completed'),'Actual SSE terminal/evidence events missing');
    await page.locator('.pao-ai-message.assistant').filter({hasText:'Delivery policy: 3 days.'}).first().waitFor();
    const evidence=await call('/v1/runs/'+message.run_id+'/knowledge');assert.equal(evidence.items.length,1);assert.ok(evidence.items[0].quote.includes('Delivery policy'));
    const download=page.waitForEvent('download');await chat.getByRole('button',{name:'Tải evidence run (nếu có)',exact:true}).click();await download;
    await chat.getByRole('button',{name:'Gỡ attachment',exact:true}).click();await until(()=>call('/v1/sessions/'+sid+'/attachments'),v=>v.length===0,'Remove link');
    const remaining=await call(base+'/files');assert.ok(remaining.some(f=>f.name==='delivery.txt'));assert.equal(await page.evaluate(()=>window.p2Unsafe),undefined);
    assert.deepEqual(routeErrors,[]);
    console.log('PASS P2 real browser/API/ARQ: index/search/citations/plain rendering/Wiki review/edit/diff/publish/revert/graph/opt-in chat/attachment scope/evidence download/non-destructive removal');
  }catch(error){if(page&&!page.isClosed()){console.error('UI runtime:',await page.locator('.pao-ai-runtime').textContent().catch(()=>''));console.error('UI error:',await page.locator('.pao-ai-error').textContent().catch(()=>''));await page.screenshot({path:'.runtime/p2-browser-failed.png',fullPage:true}).catch(()=>{})}throw Error(stage+': '+error.message.split('\nCall log:')[0])}finally{closing=true;await browser.close()}
})().catch(error=>{console.error(error.message);process.exit(1)});
