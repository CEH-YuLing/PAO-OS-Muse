const assert=require('node:assert/strict');const {chromium}=require('playwright');
(async()=>{
 const api=process.env.PAO_P1_BROWSER_API;assert.equal(api,'http://127.0.0.1:18100');
 const browser=await chromium.launch({channel:process.platform==='win32'?'msedge':undefined,headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/v1/**',async route=>{const u=new URL(route.request().url());await route.fulfill({response:await route.fetch({url:api+u.pathname+u.search})})});
  await page.goto(process.env.PAO_FRONTEND_URL);await page.getByLabel('Email',{exact:true}).fill('brain-ui@example.test');await page.getByLabel('Mật khẩu',{exact:true}).fill(process.env.PAO_P1_BROWSER_PASSWORD);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  await page.waitForFunction(()=>Boolean(sessionStorage.getItem('pao.access_token')));
  const headers={Authorization:`Bearer ${await page.evaluate(()=>sessionStorage.getItem('pao.access_token'))}`};
  const me=await(await page.request.get(api+'/v1/me',{headers})).json();const wid=me.workspaces[0].id;
  const schema={type:'object',properties:{text:{type:'string',maxLength:80}},required:['text'],additionalProperties:false};
  async function post(path,data){const r=await page.request.post(api+path,{headers,data});assert(r.ok(),await r.text());return await r.json()}
  async function make(kind,slug,payload){let d=await post('/v1/studio/definitions',{workspace_id:wid,kind,slug,name:slug,payload});
   const base='/v1/studio/definitions/'+d.definition.id+'/versions/'+d.version.id;
   if(kind!=='agents')await post(base+'/fixture',{input:{text:'fixture'},expected_output:{text:'fixture'}});
   for(const action of ['validate','review','publish'])d=await post(base+'/actions/'+action,{revision:d.definition.revision,self_review:true});return d;
  }
  const agent=await make('agents','p61-agent',{instruction:'Return a concise factual object.'});
  const skill=await make('skills','p61-skill',{instruction:'Return a concise JSON object.',agent_version_id:agent.version.id,input_schema:schema,output_schema:schema});
  const workflow=await make('workflows','p61-workflow',{input_schema:schema,output_schema:schema,steps:[{id:'first',skill_version_id:skill.version.id,inputs:{text:{source:'workflow',field:'text'}}},{id:'second',skill_version_id:skill.version.id,depends_on:['first'],inputs:{text:{source:'step',step:'first',field:'text'}}}],outputs:{text:{source:'step',step:'second',field:'text'}}});
  await page.goto(new URL('/skills',process.env.PAO_FRONTEND_URL).href);const studio=page.getByRole('region',{name:'Agent Skill Workflow Studio'});await studio.getByRole('button',{name:'workflows',exact:true}).click();await studio.getByRole('button',{name:'p61-workflow [published]',exact:true}).click();
  const panel=page.getByRole('region',{name:'P6.1 workflow planning'});await panel.waitFor();await panel.getByRole('button',{name:'Kiểm tra và xem kế hoạch',exact:true}).click();
  const save=panel.getByRole('button',{name:'Lưu kế hoạch task nháp',exact:true});await save.waitFor();assert(await save.isDisabled());await panel.getByRole('checkbox').check();await save.click();await panel.getByRole('status').filter({hasText:'2 task nháp, chưa chạy'}).waitFor();
  const tasks=await(await page.request.get(api+'/v1/tasks?workspace_id='+wid,{headers})).json();assert.equal(tasks.length,2);assert(tasks.every(t=>t.status==='draft'&&!t.run_id));
  assert.equal((await page.request.patch(api+'/v1/tasks/'+tasks[0].id,{headers,data:{version:1,status:'ready'}})).status(),409);
  assert.deepEqual(errors,[]);await page.screenshot({path:'.runtime/p61-workflow-plan-ui.png',fullPage:true});
  console.log(JSON.stringify({pass:true,real_http_ui:true,planned_tasks:2,execution_blocked:true,model_calls:0,provider_calls:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
