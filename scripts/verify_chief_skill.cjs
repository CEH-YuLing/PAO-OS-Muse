// Creates one isolated demo conversation with three runs; never changes Ads.
const assert = require('node:assert/strict');
const {randomUUID} = require('node:crypto');
const {request, chromium} = require('playwright');

(async () => {
  assert.ok(process.env.PAO_SMOKE_EMAIL && process.env.PAO_SMOKE_PASSWORD, 'Supply demo credentials via process environment');
  const api = await request.newContext({baseURL: 'http://127.0.0.1:8100'});
  try {
    let ready = false;
    const startupDeadline = Date.now() + 30000;
    while (Date.now() < startupDeadline) {
      try {ready = (await api.get('/ready', {timeout: 2000})).status() === 200;} catch {}
      if (ready) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    assert.ok(ready, 'API did not become ready');
    const login = await api.post('/v1/auth/token', {data: {email: process.env.PAO_SMOKE_EMAIL, password: process.env.PAO_SMOKE_PASSWORD}});
    assert.equal(login.status(), 200);
    const headers = {Authorization: `Bearer ${(await login.json()).access_token}`};
    const me = await api.get('/v1/me', {headers});
    assert.equal(me.status(), 200);
    const workspace = (await me.json()).workspaces[0].id;
    const session = await api.post('/v1/sessions', {headers, data: {workspace_id: workspace, memory_enabled: false, title: 'Kiểm thử Chief Skill — dữ liệu demo'}});
    assert.equal(session.status(), 201);
    const sid = (await session.json()).id;
    const cases = [
      {skill: 'daily-business-brief', prompt: 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05', tools: ['business.kpi.read', 'business.tasks.read']},
      {skill: 'investigate-ads-drop', prompt: 'Điều tra hiệu quả quảng cáo giảm meta act_1 từ 2026-10-01 đến 2026-10-05', tools: ['business.kpi.read', 'business.ads.intelligence.read']},
      {skill: 'creative-fatigue-review', prompt: 'Đánh giá creative fatigue meta act_1 từ 2026-10-01 đến 2026-10-05', tools: ['business.creative.read', 'business.ads.intelligence.read']},
    ];
    let lastReplay;
    for (const test of cases) {
    const created = await api.post('/v1/runs', {headers, data: {session_id: sid,
      message: test.prompt, request_key: randomUUID()}});
    assert.equal(created.status(), 202);
    const rid = (await created.json()).id;
    let run;
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      const response = await api.get(`/v1/runs/${rid}`, {headers});
      assert.equal(response.status(), 200);
      run = await response.json();
      if (['completed', 'failed', 'cancelled'].includes(run.status)) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    assert.equal(run.status, 'completed', `Run status=${run.status}, error=${run.error_code}`);
    assert.match(run.response, /Chưa đủ dữ liệu/);
    const execution = await api.get(`/v1/runs/${rid}/execution`, {headers});
    assert.equal(execution.status(), 200);
    const plan = (await execution.json()).plan;
    assert.equal(plan.skill_route.skill_id, test.skill);
    assert.equal(plan.skill_result.status, 'insufficient_data');
    assert.equal(plan.skill_snapshot.version, test.skill === 'investigate-ads-drop' ? '1.1.0' : '1.0.0');
    assert.equal(plan.skill_snapshot.execution_binding.policy, 'exact-backend-source-v1');
    assert.match(plan.skill_snapshot.execution_binding.sha256, /^[0-9a-f]{64}$/);
    assert.ok(plan.resource_guard.timeout_seconds > 0);
    assert.ok(plan.resource_guard.timeout_seconds <= plan.skill_snapshot.timeout_seconds);
    assert.equal(plan.resource_guard.max_tools, 2);
    assert.equal(plan.resource_guard.max_response_chars, 32000);
    assert.equal(plan.resource_guard.llm_generated_tokens, 0);
    assert.equal(plan.resource_guard.execution_mode, 'deterministic_read_only');
    const replayResponse = await api.get(`/v1/runs/${rid}/skill-replay`, {headers});
    assert.equal(replayResponse.status(), 200);
    const replay = await replayResponse.json();
    assert.deepEqual(replay.skill_snapshot, plan.skill_snapshot);
    assert.deepEqual(replay.result, plan.skill_result);
    assert.equal(replay.tools_reexecuted, false);
    assert.equal(replay.business_verified, false);
    assert.equal(replay.response, run.response);
    lastReplay = replay;
    const tools = await api.get(`/v1/runs/${rid}/tools`, {headers});
    assert.equal(tools.status(), 200);
    const data = await tools.json();
    assert.deepEqual(data.calls.map(call => call.name).sort(), [...test.tools].sort());
    assert.ok(data.calls.every(call => call.status === 'completed'));
    for (const call of data.calls) {
      assert.deepEqual(plan.business_tool_bindings[call.id], plan.skill_snapshot.execution_binding);
    }
    assert.equal(data.audit.filter(item => item.event === 'tool.completed').length, 2);
    console.log(`PASS live Chief ${test.skill}, durable tools and insufficient-data result; demo run ${rid}`);
    }
    const browser = await chromium.launch({channel: 'msedge', headless: true});
    try {
      const context = await browser.newContext({viewport: {width: 390, height: 844}});
      await context.addInitScript(value => sessionStorage.setItem('pao.access_token', value), headers.Authorization.slice(7));
      const page = await context.newPage();
      await page.goto('http://127.0.0.1:3200/skills');
      const region = page.getByRole('region', {name: 'Replay skill đã lưu'});
      await region.getByLabel('Run ID để xem lại').fill(lastReplay.record_id);
      await region.getByRole('button', {name: 'Xem kết quả đã lưu', exact: true}).click();
      await region.getByText(lastReplay.result.summary, {exact: true}).waitFor();
      await region.getByText('Artifact, contract và nguồn đã lưu', {exact: true}).click();
      assert.ok((await region.locator('pre').innerText()).includes(lastReplay.hash));
      await region.getByLabel('Run ID để xem lại').fill('invalid');
      assert.equal(await region.locator('pre').count(), 0, 'Changing ID must clear old replay');
      await region.getByRole('button', {name: 'Xem kết quả đã lưu', exact: true}).click();
      await region.getByRole('alert').filter({hasText: 'UUID hợp lệ'}).waitFor();
      console.log('PASS skill archive replay API and mobile UI, no re-execution');
    } finally {await browser.close();}
  } finally {
    await api.dispose();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
