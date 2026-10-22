const assert=require('node:assert/strict'),{open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_MCP_LEGACY_BROWSER),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);await p.goto(f.web+'/settings');await p.getByRole('button',{name:'Kết nối',exact:true}).click();
  const panel=p.getByLabel('Kết nối công cụ chỉ đọc',{exact:true}),connection=panel.getByLabel('Kết nối MCP',{exact:true}),tool=panel.getByLabel('Công cụ MCP',{exact:true}),tid='mcp.'+f.source.replaceAll('-','')+'.read_report';
  await connection.selectOption(f.source);await tool.selectOption(tid);
  const run=panel.getByLabel('MCP lượt cha ID',{exact:true}),key=panel.getByLabel('MCP yêu cầu key',{exact:true}),queue=panel.getByRole('button',{name:'Xếp hàng lượt đọc đã được duyệt',exact:true});
  step='selection drops old intent';await run.fill(f.run);await key.fill('fixture-old-intent');await panel.getByLabel('Đồng ý xếp hàng MCP cũ',{exact:true}).check();await tool.selectOption('');await tool.selectOption(tid);assert.equal(await run.inputValue(),'');assert.equal(await key.inputValue(),'');assert.equal(await panel.getByLabel('Đồng ý xếp hàng MCP cũ',{exact:true}).isChecked(),false);
  step='explicit legacy call';await run.fill(f.run);await key.fill('fixture-s23c-legacy');assert.equal(await queue.isDisabled(),true);await panel.getByLabel('Đồng ý xếp hàng MCP cũ',{exact:true}).check();
  const pending=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/calls')&&r.request().method()==='POST');await queue.click();const response=await pending;assert.equal(response.status(),202);const call=await response.json();await panel.getByLabel('Kết quả thao tác MCP',{exact:true}).filter({hasText:call.id}).waitFor();
  assert.equal(await run.inputValue(),'');assert.equal(await key.inputValue(),'');assert.equal(await queue.isDisabled(),true);
  step='native execution';const token=await p.evaluate(()=>sessionStorage.getItem('pao.access_token'));let result;
  for(let i=0;i<80;i++){const response=await p.request.get(f.api+'/v1/runs/'+f.run+'/tools',{headers:{Authorization:'Bearer '+token}});assert.equal(response.status(),200);result=(await response.json()).calls.find(row=>row.id===call.id);if(result?.status==='completed')break;await p.waitForTimeout(100)}
  assert.equal(result?.status,'completed');assert.deepEqual(result.result,{text:'Synthetic read result'});await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,explicit_call:true,native_result:true,drafts_cleared:true,mobile:true,real_server_calls:false}));
 }finally{await h.close()}
})().catch(error=>{console.error('P6 browser failed at MCP legacy '+step+' '+String(error.message).split('\n')[0].slice(0,180));process.exitCode=1});
