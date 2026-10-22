const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/v1/**',async route=>{const u=new URL(route.request().url());try{await route.fulfill({response:await route.fetch({url:api+u.pathname+u.search})})}catch{await route.abort().catch(()=>{})}});
  await page.goto(process.env.PAO_FRONTEND_URL);await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');
  await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));await page.goto(new URL('/skills',process.env.PAO_FRONTEND_URL).href);
  const panel=page.getByRole('region',{name:'Agent Skill Workflow Studio'});await panel.waitFor();
  await panel.getByRole('button',{name:'Import defaults (read-only)',exact:true}).click();
  await panel.getByLabel('Studio test result').filter({hasText:'"imported":8'}).waitFor();
  await panel.getByRole('button',{name:'New draft',exact:true}).click();await panel.getByLabel('Slug',{exact:true}).fill('p4-agent');await panel.getByLabel('Name',{exact:true}).fill('P4 Synthetic Agent');
  await panel.getByRole('button',{name:'Create draft',exact:true}).click();await panel.getByLabel('Versions',{exact:true}).waitFor();
  async function action(name,status){await panel.getByRole('button',{name,exact:true}).click();await page.waitForFunction(status=>[...document.querySelectorAll('select option')].some(x=>x.selected&&x.textContent.includes(status)),status)}
  await action('validate','validated');await panel.getByRole('checkbox').check();await action('review','reviewed');await action('publish','published');
  const headers={Authorization:`Bearer ${await page.evaluate(()=>sessionStorage.getItem('pao.access_token'))}`};
  const me=await(await page.request.get(api+'/v1/me',{headers})).json(),wid=me.workspaces[0].id;
  const definitions=await(await page.request.get(api+'/v1/studio/definitions?workspace_id='+wid,{headers})).json();
  const agent=definitions.definitions.find(x=>x.slug==='p4-agent');assert(agent.published_version_id);
  await panel.getByRole('button',{name:'skills',exact:true}).click();await panel.getByLabel('Slug',{exact:true}).fill('p4-echo');await panel.getByLabel('Name',{exact:true}).fill('P4 Echo');
  const schema={type:'object',properties:{text:{type:'string',maxLength:80}},required:['text'],additionalProperties:false};
  await panel.getByLabel('Studio definition JSON').fill(JSON.stringify({instruction:'Return the input text in a JSON object.',agent_version_id:agent.published_version_id,input_schema:schema,output_schema:schema}));
  await panel.getByRole('button',{name:'Create draft',exact:true}).click();await panel.getByLabel('Versions',{exact:true}).waitFor();
  await panel.getByRole('button',{name:'Test schema only — no model',exact:true}).click();await panel.getByLabel('Studio test result').filter({hasText:'schema_only'}).waitFor();
  await action('validate','validated');await panel.getByRole('checkbox').check();await action('review','reviewed');await action('publish','published');
  await page.goto(new URL('/pao-ai',process.env.PAO_FRONTEND_URL).href);await page.getByRole('button',{name:'Hội thoại mới',exact:true}).last().click();
  await page.getByLabel('Nội dung yêu cầu PAO').fill('/p4-echo {"text":"P4 synthetic"}');await page.getByRole('button',{name:'Gửi yêu cầu',exact:true}).click();
  await page.getByText('{"text": "P4 synthetic"}',{exact:true}).last().waitFor();
  const sessions=await(await page.request.get(api+'/v1/sessions?workspace_id='+wid,{headers})).json();const sid=sessions[0].id;
  for(let i=0;i<80;i++){const d=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();if(!d.active_run&&d.messages.length===2)break;await new Promise(r=>setTimeout(r,200))}
  const done=await(await page.request.get(`${api}/v1/sessions/${sid}`,{headers})).json();assert.equal(done.messages.length,2);assert.equal(done.active_run,null);
  assert.deepEqual(errors,[]);await page.screenshot({path:'.runtime/p4-live-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_api_db_arq_sse:true,editor_versions_review_publish_fixture:true,model_calls:'one synthetic',external_provider_calls:0,screenshot:'.runtime/p4-live-ui.png'}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
