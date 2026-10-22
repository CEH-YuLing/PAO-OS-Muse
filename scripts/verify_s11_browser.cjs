const assert = require('node:assert/strict');
const {open} = require('./p6_browser_harness.cjs');
let step = 'start';
(async () => {
  const fixture = JSON.parse(process.env.PAO_S11_BROWSER_FIXTURE);
  let delayA = false, release, waiting;
  const held = new Promise(resolve => {waiting = resolve});
  const h = await open(fixture, {intercept: async (route, response) => {
    const url = new URL(route.request().url());
    if (delayA && url.pathname === '/v1/tasks' && url.searchParams.get('workspace_id') === fixture.workspace) {
      delayA = false;
      await new Promise(resolve => {release = resolve; waiting()});
      await route.fulfill({response});
      return true;
    }
    return false;
  }});
  const p = h.page;
  const selector = () => p.locator('.pao-topbar-context select');
  try {
    step = 'explicit selection';
    await h.login();
    await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(fixture.workspace);
    await p.goto(fixture.web + '/tasks');
    await p.getByText('S11 task only SME A', {exact: true}).waitFor();
    assert.equal(await p.getByText('S11 task only SME B', {exact: true}).count(), 0);

    step = 'late A response';
    delayA = true;
    await p.reload();
    await held;
    await selector().selectOption(fixture.second);
    await p.getByText('S11 task only SME B', {exact: true}).waitFor();
    release();
    await p.waitForTimeout(500);
    assert.equal(await p.getByText('S11 task only SME A', {exact: true}).count(), 0);
    assert.equal(await selector().inputValue(), fixture.second);

    step = 'reload selected SME';
    await p.reload();
    await p.getByText('S11 task only SME B', {exact: true}).waitFor();
    assert.equal(await selector().inputValue(), fixture.second);
    step = 'settings viewer role';
    await p.goto(fixture.web + '/settings');
    await selector().waitFor();
    assert.equal(await selector().inputValue(), fixture.second);
    const requests = [];
    p.on('request', request => requests.push(request.url()));
    const providersResponse = p.waitForResponse(response => new URL(response.url()).pathname === '/v1/model-providers');
    await p.reload();
    await providersResponse;
    assert.ok(requests.some(url => url.includes('/v1/model-providers?workspace_id=' + fixture.second)));
    assert.ok(!requests.some(url => url.includes('workspace_id=' + fixture.workspace)));

    step = 'chat context';
    await p.goto(fixture.web + '/pao-ai');
    await p.getByRole('button', {name: /^S11 chat only SME B/}).waitFor();
    assert.equal(await p.getByRole('button', {name: /^S11 chat only SME A/}).count(), 0);
    const token = await p.evaluate(() => sessionStorage.getItem('pao.access_token'));
    const denied = await p.request.post(fixture.api + '/v1/sessions', {
      headers: {Authorization: 'Bearer ' + token}, data: {workspace_id: fixture.second},
    });
    assert.equal(denied.status(), 403);

    step = 'tampered hint';
    await p.evaluate(async () => {
      const response = await fetch('/v1/me', {headers: {Authorization: 'Bearer ' + sessionStorage.getItem('pao.access_token')}});
      const me = await response.json();
      sessionStorage.setItem('pao.workspace.' + me.id, '00000000-0000-0000-0000-000000000000');
    });
    await p.reload();
    await p.getByRole('heading', {name: 'Chọn doanh nghiệp làm việc'}).waitFor();
    assert.equal(await p.getByLabel('Doanh nghiệp đang hoạt động').inputValue(), '');
    await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(fixture.workspace);
    await p.getByRole('button', {name: /^S11 chat only SME A/}).waitFor();
    step = 'mobile selector';
    await p.setViewportSize({width: 390, height: 844});
    await p.getByRole('button', {name: 'Mở điều hướng', exact: true}).click();
    const mobileSessions = p.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === '/v1/sessions' && url.searchParams.get('workspace_id') === fixture.second;
    });
    await p.locator('.pao-sidebar-enterprise select').selectOption(fixture.second);
    const mobileResponse = await mobileSessions;
    assert.ok((await mobileResponse.json()).every(row => row.workspace_id === fixture.second));
    // Chat's session rail is intentionally collapsed on narrow screens.
    step = 'mobile selected session attached';
    await p.locator('.pao-conversation-row').filter({hasText: 'S11 chat only SME B'}).waitFor({state: 'attached'});
    assert.equal(await p.locator('.pao-sidebar-enterprise select').inputValue(), fixture.second);
    await h.mobile();
    assert.deepEqual(h.errors, []);
    console.log(JSON.stringify({pass: true, real_http: true, per_tenant_role: true,
      selection_reload: true, late_response_discarded: true, tampered_hint_denied: true,
      settings_chat_tasks_scoped: true, mobile_selector: true, real_provider_called: false}));
  } finally {if (release) release(); await h.close()}
})().catch(error => {
  console.error('P6 browser failed at S11 ' + step + ' ' + String(error.message).split('\n')[0].slice(0, 180));
  process.exitCode = 1;
});
