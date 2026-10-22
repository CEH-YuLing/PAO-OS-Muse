// Live, local-only acceptance. Credentials must be supplied by the caller.
const assert = require('node:assert/strict');
const {chromium} = require('playwright');

(async () => {
  const email = process.env.PAO_SMOKE_EMAIL;
  const password = process.env.PAO_SMOKE_PASSWORD;
  assert.ok(email && password, 'Supply PAO_SMOKE_EMAIL and PAO_SMOKE_PASSWORD');
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1280, height: 900}});
    let webReady = false;
    const startupDeadline = Date.now() + 45000;
    while (Date.now() < startupDeadline) {
      try {webReady = (await context.request.get('http://127.0.0.1:3200/skills', {timeout: 3000})).status() === 200;} catch {}
      if (webReady) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    }
    assert.ok(webReady, 'Web did not become ready');
    const login = await context.request.post('http://127.0.0.1:8100/v1/auth/token', {data: {email, password}});
    assert.equal(login.status(), 200);
    const {access_token: token} = await login.json();
    const headers = {Authorization: `Bearer ${token}`};
    const me = await context.request.get('http://127.0.0.1:8100/v1/me', {headers});
    assert.equal(me.status(), 200);
    const workspace = (await me.json()).workspaces[0].id;
    const catalog = await context.request.get(`http://127.0.0.1:8100/v1/skills?workspace_id=${workspace}`, {headers});
    assert.equal(catalog.status(), 200);
    const skills = await catalog.json();
    assert.equal(skills.length, 3);
    assert.ok(skills.every(skill => skill.version === (skill.id === 'investigate-ads-drop' ? '1.1.0' : '1.0.0') && /^[a-f0-9]{64}$/.test(skill.hash)));
    const attribution = await context.request.post('http://127.0.0.1:8100/v1/skills/investigate-ads-drop/attribution-preview', {
      headers, data: {workspace_id: workspace, input: {start_date: '2026-10-01', end_date: '2026-10-05', platform: 'meta', account_id: 'act_1'}},
    });
    assert.equal(attribution.status(), 200);
    const attributed = await attribution.json();
    assert.equal(attributed.result.status, 'insufficient_data');
    assert.equal(attributed.tools[0].tool, 'business.attribution.read');
    assert.equal(attributed.tools[0].data.verified_business_revenue, false);
    const preflight = await context.request.post('http://127.0.0.1:8100/v1/skills/daily-business-brief/validate', {
      headers, data: {workspace_id: workspace, agent: 'chief_of_staff', input: {start_date: '2026-10-01', end_date: '2026-10-05'}, requested_tools: ['business.kpi.read']},
    });
    assert.equal(preflight.status(), 200);
    assert.equal((await preflight.json()).execution_available, false);
    const preview = await context.request.post('http://127.0.0.1:8100/v1/skills/daily-business-brief/preview', {
      headers, data: {workspace_id: workspace, input: {start_date: '2026-10-01', end_date: '2026-10-05'}},
    });
    assert.equal(preview.status(), 200);
    const brief = await preview.json();
    assert.equal(brief.read_only, true);
    assert.equal(brief.result.status, 'insufficient_data');
    assert.equal(brief.tools.length, 2);
    await context.addInitScript(value => sessionStorage.setItem('pao.access_token', value), token);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const response = await page.goto('http://127.0.0.1:3200/skills');
    assert.equal(response.status(), 200);
    await page.getByRole('heading', {name: 'Skills', exact: true}).waitFor();
    await page.locator('.st-cap-grid').getByText('Báo cáo doanh nghiệp', {exact: true}).waitFor();
    assert.equal(await page.getByText('REGISTERED', {exact: true}).count(), 3);
    assert.equal(await page.getByText(/Chưa tự thực thi/).count(), 3);
    await page.getByText('Contract và quyền công cụ', {exact: true}).first().click();
    assert.ok((await page.locator('.st-cap-grid').innerText()).includes(skills[0].hash));
    await page.getByLabel('Từ ngày', {exact: true}).fill('2026-10-01');
    await page.getByLabel('Đến ngày', {exact: true}).fill('2026-10-05');
    await page.getByRole('button', {name: 'Đọc bản xem trước', exact: true}).click();
    await page.getByText(brief.result.summary, {exact: true}).waitFor();
    await page.getByText('Dữ liệu và nguồn đã đọc', {exact: true}).click();
    assert.ok((await page.locator('pre').innerText()).includes('business.tasks.read'));
    for (const skill of ['investigate-ads-drop', 'creative-fatigue-review']) {
      const response = await context.request.post(`http://127.0.0.1:8100/v1/skills/${skill}/analysis-preview`, {
        headers, data: {workspace_id: workspace, input: {start_date: '2026-10-01', end_date: '2026-10-05', platform: 'meta', account_id: 'act_1'}},
      });
      assert.equal(response.status(), 200);
      const output = await response.json();
      assert.equal(output.read_only, true);
      assert.equal(output.result.status, 'insufficient_data');
      await page.getByLabel(/^Kỹ năng xem trước/).selectOption(skill);
      await page.getByLabel('Tài khoản Ads', {exact: true}).fill('act_1');
      await page.getByRole('button', {name: 'Đọc bản xem trước', exact: true}).click();
      await page.getByText(output.result.summary, {exact: true}).waitFor();
      await page.getByText('Dữ liệu và nguồn đã đọc', {exact: true}).click();
      assert.ok((await page.locator('pre').innerText()).includes(output.tools[0].tool));
    }
    await page.getByLabel(/^Kỹ năng xem trước/).selectOption('attribution');
    await page.getByRole('button', {name: 'Đọc bản xem trước', exact: true}).click();
    await page.getByText(attributed.result.summary, {exact: true}).waitFor();
    const section = page.getByRole('region', {name: 'Kết quả attribution'});
    await section.getByText(/Chưa có metric attribution/).waitFor();
    await section.getByText(/Chưa xác minh doanh thu doanh nghiệp/).waitFor();
    const endpoint = '**/v1/skills/investigate-ads-drop/attribution-preview';
    const fixture = structuredClone(attributed);
    fixture.result.summary = 'Fixture UI — không phải dữ liệu thật';
    fixture.tools[0].data.metrics = [
      {id: 'fixture-usd', campaign_id: '123', currency: 'USD', platform_reported_revenue: '100.00', attributed_paid_order_revenue: null, attributed_paid_order_count: null},
      {id: 'fixture-vnd', campaign_id: '456', currency: 'VND', platform_reported_revenue: '0', attributed_paid_order_revenue: '0', attributed_paid_order_count: 0},
    ];
    let reads = 0;
    await page.route(endpoint, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      reads++;
      const body = route.request().postDataJSON();
      assert.equal(body.workspace_id, workspace);
      assert.equal(body.input.account_id, 'act_1');
      assert.equal(body.input.start_date, '2026-10-01');
      await route.fulfill({json: fixture});
    });
    await page.getByLabel('Tài khoản Ads', {exact: true}).fill('act_1');
    assert.equal(reads, 0, 'Changing form must not auto-read');
    await page.getByRole('button', {name: 'Đọc bản xem trước', exact: true}).click();
    await page.getByText(fixture.result.summary, {exact: true}).waitFor();
    assert.equal(reads, 1);
    assert.equal(await section.getByRole('row').count(), 3);
    const usd = section.getByRole('row').filter({hasText: 'fixture-usd'});
    assert.ok((await usd.innerText()).includes('chưa biết'));
    const vnd = section.getByRole('row').filter({hasText: 'fixture-vnd'});
    assert.equal(await vnd.getByRole('cell', {name: '0', exact: true}).count(), 3);
    await page.screenshot({path: '.runtime/skills-attribution-desktop.png', fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.waitForFunction(() => Math.abs(parseFloat(getComputedStyle(document.querySelector('.pao-app-stage')).marginLeft)) < 0.5);
    assert.ok(await section.getByRole('table').isVisible());
    const layout = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
      main: {width: document.querySelector('main.pao-page').clientWidth, scroll: document.querySelector('main.pao-page').scrollWidth},
      outside: [...document.querySelectorAll('main, section, table, form, select, input, article, div')]
        .filter(element => element.getBoundingClientRect().right > innerWidth + 1)
        .slice(0, 12).map(element => ({tag: element.tagName, class: element.className, width: element.getBoundingClientRect().width}))}));
    assert.ok(layout.main.scroll <= layout.main.width + 1, `Mobile Skills content overflow: ${JSON.stringify(layout)}`);
    assert.ok(layout.main.width >= layout.width - 2, 'Mobile sidebar must not compress Skills');
    await section.scrollIntoViewIfNeeded();
    await page.screenshot({path: '.runtime/skills-attribution-mobile.png'});
    const scroll = await section.getByRole('table').evaluate(table => {
      const container = table.parentElement;
      container.scrollLeft = container.scrollWidth;
      return {left: container.scrollLeft, width: container.clientWidth, content: container.scrollWidth};
    });
    assert.ok(scroll.left > 0 && scroll.content > scroll.width, 'Mobile table must scroll to source columns');
    await page.unroute(endpoint);
    let release;
    const held = new Promise(resolve => {release = resolve;});
    let arrived;
    const waiting = new Promise(resolve => {arrived = resolve;});
    await page.route(endpoint, async route => {
      if (route.request().method() !== 'POST') return route.continue();
      arrived(); await held;
      await route.fulfill({json: {...fixture, result: {...fixture.result, summary: 'LATE_FIXTURE_MUST_NOT_DISPLAY'}}});
    });
    await page.getByRole('button', {name: 'Đọc bản xem trước', exact: true}).click();
    await waiting;
    await page.getByLabel(/^Kỹ năng xem trước/).selectOption('daily-business-brief');
    const delivered = page.waitForResponse(response => response.url().endsWith('/attribution-preview') && response.request().method() === 'POST');
    release(); await delivered;
    await page.waitForTimeout(300);
    assert.equal(await page.getByText('LATE_FIXTURE_MUST_NOT_DISPLAY', {exact: true}).count(), 0);
    assert.equal(await section.count(), 0);
    await page.unroute(endpoint);
    await page.route(endpoint, route => route.request().method() === 'POST'
      ? route.fulfill({status: 403, json: {detail: 'fixture_permission_denied'}}) : route.continue());
    await page.getByLabel(/^Kỹ năng xem trước/).selectOption('attribution');
    await page.getByRole('button', {name: 'Đọc bản xem trước', exact: true}).click();
    await page.getByRole('alert').filter({hasText: 'fixture_permission_denied'}).waitFor();
    assert.equal(await section.count(), 0);
    await page.unroute(endpoint);
    assert.equal(await page.getByText('REGISTERED', {exact: true}).count(), 3);
    assert.deepEqual(errors, []);
    console.log('PASS live Skills/attribution preview; UI fixtures for unknown/zero/currencies, mobile, stale response and 403; no external actions');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
