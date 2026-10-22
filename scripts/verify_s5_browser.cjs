const assert=require('node:assert/strict'),{open}=require('./p6_browser_harness.cjs');let step='start';
async function studioFixture(f){
 const signed=await fetch(f.api+'/v1/auth/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'owner@example.test',password:'test-password-123'})});assert.equal(signed.status,200);
 const token=(await signed.json()).access_token;
 async function api(path,body){const r=await fetch(f.api+path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});assert.ok(r.ok,'Native Studio fixture status '+r.status);return r.json()}
 const schema={type:'object',properties:{text:{type:'string',maxLength:4096}},required:['text'],additionalProperties:false};
 async function publish(kind,slug,payload){let data=await api('/v1/studio/definitions',{workspace_id:f.workspace,kind,slug,name:slug,payload});const path='/v1/studio/definitions/'+data.definition.id+'/versions/'+data.version.id;
  if(kind!=='agents')await api(path+'/fixture',{input:{text:'Fixture'},expected_output:{text:'Fixture'}});
  for(const action of ['validate','review','publish'])data=await api(path+'/actions/'+action,{revision:data.definition.revision,self_review:true});return data;
 }
 const agent=await publish('agents','s5-browser-agent',{instruction:'Draft factual text for human review.'});
 const skill=await publish('skills','s5-browser-skill',{instruction:'Return factual text as a JSON object.',agent_version_id:agent.version.id,input_schema:schema,output_schema:schema});
 return {skill:skill.version.id,drain:async run_id=>{const response=await fetch(f.api+'/_s5_fixture/drain',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,'X-Fixture-Key':f.fixture_key},body:JSON.stringify({run_id})});assert.equal(response.status,200)}};
}
(async()=>{
 const f=JSON.parse(process.env.PAO_S5_BROWSER),h=await open(f),p=h.page;
 try{
  const fixture=await studioFixture(f),skill=fixture.skill;await h.login();await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
  await p.waitForFunction(wid=>Object.entries(sessionStorage).some(([key,value])=>key.startsWith('pao.workspace.')&&value===wid),f.workspace);
  await p.goto(f.web+'/business-planning');
  step='profile authoring';await p.getByLabel('Mô tả doanh nghiệp',{exact:true}).fill('Doanh nghiệp thử A, không dùng dữ liệu khách hàng');
  await p.getByLabel('Sản phẩm',{exact:true}).fill('Sản phẩm A\nSản phẩm B');
  await p.getByLabel('Khách hàng mục tiêu',{exact:true}).fill('Khách hàng thử nghiệm');
  await p.getByLabel('Giọng thương hiệu',{exact:true}).fill('Rõ ràng');
  await p.getByLabel('Nguồn lực',{exact:true}).fill('Một biên tập viên');
  await p.getByLabel('Mục tiêu',{exact:true}).fill('Soạn kế hoạch');
  await p.getByRole('button',{name:'Thêm chỉ số mục tiêu',exact:true}).click();await p.getByLabel('KPI 1 tên',{exact:true}).fill('Bản nháp được duyệt');await p.getByLabel('KPI 1 đơn vị',{exact:true}).fill('bản');assert.equal(await p.getByLabel('KPI 1 mục tiêu',{exact:true}).inputValue(),'');
  await p.getByRole('button',{name:'Lưu phiên bản hồ sơ',exact:true}).click();
  await p.getByRole('status').getByText(/Đã lưu hồ sơ phiên bản 1/).waitFor();
  assert.equal(await p.getByLabel('Ngân sách dự kiến tháng',{exact:true}).inputValue(),'');
  step='monthly draft';await p.getByLabel('Tên kế hoạch tháng',{exact:true}).fill('Kế hoạch thử tháng 10');await p.getByLabel('Tháng triển khai',{exact:true}).fill('2026-10');await p.getByLabel('Brief chiến dịch',{exact:true}).fill('Chỉ chuẩn bị bản nháp, không đăng thật');
  await p.getByRole('button',{name:'Thêm đầu việc dự kiến',exact:true}).click();
  await p.getByLabel('Tên đầu việc 1',{exact:true}).fill('Viết nội dung');await p.getByLabel('Hạn đầu việc 1',{exact:true}).fill('2026-10-05');await p.getByLabel('Brief đầu việc 1',{exact:true}).fill('Dùng hồ sơ đã cung cấp');await p.getByLabel('Tiêu chí đầu việc 1',{exact:true}).fill('Không bịa ưu đãi\nCó nguồn');
  await p.getByRole('button',{name:'Lưu bản nháp kế hoạch',exact:true}).click();await p.getByRole('status').getByText(/Đã lưu bản nháp kế hoạch phiên bản 1/).waitFor();
  step='routing configuration';await p.getByLabel('Tên model 1',{exact:true}).fill('qwen3:4b');
  await p.getByRole('button',{name:'Thêm lựa chọn model',exact:true}).click();await p.getByLabel('Tên model 2',{exact:true}).fill('qwen3:8b');
  await p.getByLabel('Model mặc định nghiệp vụ',{exact:true}).selectOption('model_2');
  await p.getByRole('button',{name:'Lưu phiên bản cấu hình AI',exact:true}).click();await p.getByRole('status').getByText(/Đã lưu cấu hình AI phiên bản 1/).waitFor();
  await p.getByRole('button',{name:'Đọc lại cấu hình AI',exact:true}).click();await p.waitForFunction(()=>document.querySelector('[aria-label="Tên model 2"]')?.value==='qwen3:8b');
  assert.equal(await p.getByLabel('Model mặc định nghiệp vụ',{exact:true}).inputValue(),'model_2');
  await p.getByLabel('Công việc xem trước AI',{exact:true}).selectOption({label:'Viết nội dung'});await p.getByRole('button',{name:'Kiểm tra lựa chọn AI — không chạy',exact:true}).click();
  await p.getByRole('alert').getByText(/Chưa đạt kiểm tra lựa chọn/).waitFor();assert.equal(await p.getByLabel('Kết quả xem trước AI',{exact:true}).count(),0);
  // Missing specialist is a denial, not an implicit generic-agent fallback.
  await p.getByLabel('Kỹ năng Nội dung',{exact:true}).selectOption(skill);await p.getByRole('button',{name:'Lưu phiên bản cấu hình AI',exact:true}).click();await p.getByRole('status').getByText(/Đã lưu cấu hình AI phiên bản 2/).waitFor();
  await p.getByRole('button',{name:'Kiểm tra lựa chọn AI — không chạy',exact:true}).click();await p.getByLabel('Kết quả xem trước AI',{exact:true}).getByText(/qwen3:8b/).waitFor();
  await p.getByLabel('Model riêng cho công việc',{exact:true}).selectOption('local');assert.equal(await p.getByLabel('Kết quả xem trước AI',{exact:true}).count(),0);await p.getByRole('button',{name:'Kiểm tra lựa chọn AI — không chạy',exact:true}).click();await p.getByLabel('Kết quả xem trước AI',{exact:true}).getByText(/qwen3:4b/).waitFor();
  step='owner review and native draft admission';await p.getByLabel('Xác nhận tự duyệt kế hoạch',{exact:true}).check();await p.getByLabel('Xác nhận dữ liệu kế hoạch còn thiếu',{exact:true}).check();await p.getByRole('button',{name:'Duyệt chuẩn bị nội bộ',exact:true}).click();await p.getByText(/Đã duyệt cho chuẩn bị nội bộ/).waitFor();await p.getByLabel('Xác nhận chỉ tạo công việc nháp',{exact:true}).check();await p.getByRole('button',{name:'Tạo công việc nháp từ kế hoạch',exact:true}).click();await p.getByLabel('Công việc đã tạo từ kế hoạch',{exact:true}).getByText(/Đã tạo 1 công việc nháp/).waitFor();
  step='native job and draft review';await p.getByRole('button',{name:'Đọc lại vận hành kế hoạch',exact:true}).click();await p.getByLabel('Công việc chạy AI S5',{exact:true}).selectOption({label:'Viết nội dung'});
  const admitted=p.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/jobs')&&r.request().method()==='POST'&&r.status()===202);await p.getByRole('button',{name:'Chạy AI soạn bản nháp',exact:true}).click();const job=await (await admitted).json();await fixture.drain(job.run_id);
  await p.getByRole('button',{name:'Đọc lại vận hành kế hoạch',exact:true}).click();await p.getByRole('button',{name:'Duyệt bản nháp',exact:true}).click();await p.getByText(/Nội dung đã duyệt/).waitFor();
  step='money reservation and simulation';await p.getByText('Ngân sách chiến dịch và hành động mô phỏng',{exact:true}).click();await p.getByLabel('Trần ngân sách S5',{exact:true}).fill('1000');await p.getByLabel('Dự phòng an toàn S5',{exact:true}).fill('100');await p.getByLabel('Đã chi lúc quan sát S5',{exact:true}).fill('100');await p.getByRole('button',{name:'Tạo ngân sách mô phỏng',exact:true}).click();
  await p.getByLabel('Ngân sách đề xuất S5',{exact:true}).selectOption({index:1});await p.getByLabel('Bản nháp đề xuất S5',{exact:true}).selectOption({index:1});await p.getByLabel('Số tiền đề xuất S5',{exact:true}).fill('500');await p.getByRole('button',{name:'Tạo đề xuất và giữ hạn mức mô phỏng',exact:true}).click();
  await p.getByRole('button',{name:'Duyệt hành động mô phỏng',exact:true}).click();await p.getByRole('button',{name:'Mô phỏng kết quả chưa rõ',exact:true}).click();await p.getByText(/Kết quả chưa rõ — đang giữ hạn mức/).waitFor();await p.getByRole('button',{name:'Đối soát không thực hiện',exact:true}).click();await p.getByText(/Đã đối soát mô phỏng thất bại/).waitFor();
  step='business report';await p.getByRole('button',{name:'Tạo báo cáo tiến độ 24 giờ',exact:true}).click();await p.getByText(/^Báo cáo \d/).waitFor();
  step='profile history and stale pins';await p.getByLabel('Giọng thương hiệu',{exact:true}).fill('Giọng mới');await p.getByRole('button',{name:'Lưu phiên bản hồ sơ',exact:true}).click();await p.getByRole('status').getByText(/Đã lưu hồ sơ phiên bản 2/).waitFor();
  await p.getByText('Lịch sử hồ sơ',{exact:true}).click();await p.getByRole('button',{name:'Đọc phiên bản hồ sơ',exact:true}).click();await p.getByLabel('Hồ sơ lịch sử',{exact:true}).waitFor();assert.ok((await p.getByLabel('Hồ sơ lịch sử',{exact:true}).innerText()).includes('Rõ ràng'));
  await p.getByRole('button',{name:'Đọc lại hồ sơ và kế hoạch',exact:true}).click();await p.getByRole('button',{name:'Kế hoạch thử tháng 10 · v1',exact:true}).click();await p.getByText(/Hồ sơ đã thay đổi: đọc lại/).waitFor();
  step='mobile';for(const width of [390,320]){await p.setViewportSize({width,height:844});await p.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth)}await h.mobile();
  step='SME switch';await p.getByRole('button',{name:'Mở điều hướng',exact:true}).click();await p.locator('.pao-sidebar-enterprise select').selectOption(f.second);await p.getByText(/Hiện chỉ chủ doanh nghiệp/).waitFor();assert.equal(await p.getByLabel('Mô tả doanh nghiệp',{exact:true}).count(),0);assert.ok(!(await p.locator('.bp-workspace').innerText()).includes('Kế hoạch thử tháng 10'));
  assert.deepEqual(h.errors,[]);console.log(JSON.stringify({pass:true,real_api_db:true,source_only_candidate:true,profile_versions:true,monthly_draft:true,history:true,stale_pins:true,unknown_budget:true,routing_config:true,routing_two_model_preflight:true,routing_missing_specialist_denied:true,tenant_role_isolation:true,mobile:true,provider_calls:false,primary_rollout:false}));
 }catch(error){await p.screenshot({path:f.screenshot.replace('.png','-failure.png'),fullPage:false}).catch(()=>{});throw error}finally{await h.close()}
})().catch(error=>{console.error('S5 browser failed at '+step+': '+String(error.message).split('\n')[0].slice(0,160));const code=error.cause?.code;if(typeof code==='string'&&/^[A-Z_0-9]+$/.test(code))console.error('Transport diagnostic code: '+code);process.exitCode=1});
