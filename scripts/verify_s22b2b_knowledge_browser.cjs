const assert=require('node:assert/strict');const {open}=require('./p6_browser_harness.cjs');let step='start';
(async()=>{
 const f=JSON.parse(process.env.PAO_KNOWLEDGE_EMBEDDING_BROWSER),h=await open(f),p=h.page;
 try{
  await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);await p.goto(f.web+'/knowledge');
  await p.getByLabel('Chọn Brain',{exact:true}).selectOption(f.brain);
  const knowledge=p.getByLabel('Knowledge P2',{exact:true});
  step='hybrid search';await knowledge.getByLabel('Tìm trong nguồn',{exact:true}).fill('Return');
  let ready=p.waitForResponse(r=>new URL(r.url()).pathname===`/v1/brains/${f.brain}/retrieval`);
  await knowledge.getByRole('button',{name:'Tìm nguồn',exact:true}).click();let response=await ready;
  assert.equal(response.status(),200);let result=await response.json();assert.equal(result.mode,'hybrid');assert.equal(result.degraded,false);
  await knowledge.getByText('Return policy A: 7 days.',{exact:true}).waitFor();
  step='quota fallback';ready=p.waitForResponse(r=>new URL(r.url()).pathname===`/v1/brains/${f.brain}/retrieval`);
  await knowledge.getByRole('button',{name:'Tìm nguồn',exact:true}).click();response=await ready;result=await response.json();
  assert.equal(response.status(),200);assert.equal(result.mode,'full_text');assert.equal(result.degraded,true);assert.ok(result.items.length);
  step='reload';await p.reload();await p.getByLabel('Chọn Brain',{exact:true}).selectOption(f.brain);
  step='explicit rebuild';await knowledge.getByLabel('Source ID reindex',{exact:true}).fill(f.source);
  ready=p.waitForResponse(r=>new URL(r.url()).pathname===`/v1/brains/${f.brain}/sources/${f.source}/index`);
  await knowledge.getByRole('button',{name:'Xác nhận rebuild index',exact:true}).click();response=await ready;
  assert.equal(response.status(),200);assert.equal((await response.json()).status,'queued');
  step='SME switch';await p.locator('.pao-topbar-context select').selectOption(f.second);
  await p.getByLabel('Chọn Brain',{exact:true}).selectOption(f.otherBrain);
  assert.equal(await knowledge.getByText('Return policy A: 7 days.',{exact:true}).count(),0);
  await knowledge.getByLabel('Tìm trong nguồn',{exact:true}).fill('Return');
  ready=p.waitForResponse(r=>new URL(r.url()).pathname===`/v1/brains/${f.otherBrain}/retrieval`);
  await knowledge.getByRole('button',{name:'Tìm nguồn',exact:true}).click();response=await ready;result=await response.json();
  assert.equal(response.status(),200);assert.equal(result.mode,'hybrid');assert.ok(result.items.every(item=>item.brain_id===f.otherBrain));
  await knowledge.getByText('Return policy B: 14 days.',{exact:true}).waitFor();
  step='mobile';await h.mobile();assert.deepEqual(h.errors,[]);
  console.log(JSON.stringify({pass:true,real_http:true,hybrid:true,quota_fallback:true,reload:true,tenant_switch:true,rebuild_queued:true,real_provider_calls:false}));
 }finally{await h.close()}
})().catch(e=>{console.error('P6 browser failed at Knowledge embeddings '+step+' '+String(e.message).split('\n')[0].slice(0,180));process.exitCode=1});
