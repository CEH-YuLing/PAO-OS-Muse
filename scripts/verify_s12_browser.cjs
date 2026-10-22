const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {open} = require('./p6_browser_harness.cjs');
let step = 'start';
(async () => {
  const f = JSON.parse(process.env.PAO_S12_BROWSER_FIXTURE);
  const h = await open(f, {multiTab: true}), p = h.page;
  // Use the genuine Next -> fixture API proxy, including streaming SSE/body.
  await p.unroute('**/v1/**');
  const selector = () => p.locator('.pao-topbar-context select');
  const signal = name => fs.writeFileSync(path.join(f.markers, name), '');
  async function ack(name) {
    await p.waitForFunction(() => true);
    const deadline = Date.now() + 10000;
    while (!fs.existsSync(path.join(f.markers, name))) {
      assert.ok(Date.now() < deadline, 'Fixture handshake timed out');
      await p.waitForTimeout(50);
    }
  }
  const downloads = [], cancelled = [];
  p.on('download', d => downloads.push(d.suggestedFilename()));
  p.on('request', r => {if (/\/cancel(?:\?|$)/.test(r.url())) cancelled.push(r.url())});
  try {
    step = 'login'; await h.login();
    await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.workspace);
    await p.goto(f.web + '/pao-ai');
    await p.getByRole('button', {name: /^S12 stream A/}).click();
    await p.getByText('S12 initial private A', {exact: true}).waitFor();
    step = 'switch during SSE';
    await selector().selectOption(f.second);
    await p.getByRole('button', {name: /^S12 chat B/}).waitFor();
    signal('late'); await ack('late.done');
    await p.waitForTimeout(400);
    assert.equal(await p.getByText(/S12 (initial|late) private A/).count(), 0);
    const token = await p.evaluate(() => sessionStorage.getItem('pao.access_token'));
    const snapshot = await p.request.get(f.api + '/v1/runs/' + f.run, {headers: {Authorization: 'Bearer ' + token}});
    assert.equal(snapshot.status(), 200);
    const run = await snapshot.json();
    assert.equal(run.status, 'running', 'Original server run must stay running');
    assert.equal(run.session_id, f.stream, 'Run must retain its original session');
    assert.equal(run.cancel_requested, false); assert.equal(cancelled.length, 0);

    step = 'export body pending';
    await selector().selectOption(f.workspace);
    step = 'export session selection';
    await p.getByRole('button', {name: /^S12 export A/}).click();
    step = 'export chat panel';
    await p.getByText('Hội thoại · quyền riêng tư và usage', {exact: true}).click();
    const headers = p.waitForResponse(r => new URL(r.url()).pathname === '/v1/sessions/' + f.export + '/export');
    step = 'export request';
    await p.getByRole('button', {name: 'Xuất Markdown', exact: true}).click();
    await ack('export.ready');
    assert.equal((await headers).status(), 200);
    await selector().selectOption(f.second);
    await p.getByRole('button', {name: /^S12 chat B/}).waitFor();
    signal('export.release'); await p.waitForTimeout(500);
    assert.equal(downloads.length, 0);
    step = 'current scope export';
    await p.getByRole('button', {name: /^S12 chat B/}).click();
    await p.getByText('Hội thoại · quyền riêng tư và usage', {exact: true}).click();
    const downloaded = p.waitForEvent('download');
    await p.getByRole('button', {name: 'Xuất Markdown', exact: true}).click();
    await downloaded; assert.equal(downloads.length, 1);

    step = 'independent tabs';
    const other = await p.context().newPage();
    try {
      await other.addInitScript(({token, actor, workspace}) => {
        sessionStorage.setItem('pao.access_token', token);
        sessionStorage.setItem('pao.workspace.' + actor, workspace);
      }, {token, actor: f.actor, workspace: f.workspace});
      await other.goto(f.web + '/pao-ai');
      await other.getByRole('button', {name: /^S12 stream A/}).waitFor();
      assert.equal(await other.locator('.pao-topbar-context select').inputValue(), f.workspace);
      assert.equal(await selector().inputValue(), f.second);
      await other.locator('.pao-topbar-context select').selectOption(f.second);
      await other.getByRole('button', {name: /^S12 chat B/}).waitFor();
      assert.equal(await selector().inputValue(), f.second);
    } finally {await other.close()}

    step = 'prompt scope';
    await p.evaluate(({actor, workspace}) => {
      window.dispatchEvent(new CustomEvent('pao:prompt', {detail: 'S12 legacy prompt'}));
      window.dispatchEvent(new CustomEvent('pao:prompt', {detail: {actor, workspace, revision: 0, text: 'S12 wrong SME prompt'}}));
    }, {actor: f.actor, workspace: f.workspace});
    assert.equal(await p.locator('.pao-ai-composer textarea').inputValue(), '');
    await p.getByLabel('Ask PAO', {exact: true}).fill('S12 current B draft');
    await p.getByLabel('Ask PAO', {exact: true}).press('Enter');
    await p.waitForFunction(() => document.querySelector('.pao-ai-composer textarea')?.value === 'S12 current B draft');
    await selector().selectOption(f.workspace);
    await p.getByRole('button', {name: /^S12 stream A/}).waitFor();
    assert.equal(await p.locator('.pao-ai-composer textarea').inputValue(), '');

    step = 'role refresh on focus';
    signal('role'); await ack('role.done');
    const refreshed = p.waitForResponse(r => new URL(r.url()).pathname === '/v1/me');
    await p.evaluate(() => window.dispatchEvent(new Event('focus')));
    await refreshed;
    await p.waitForFunction(() => document.querySelector('.pao-topbar-context select')?.selectedOptions[0]?.textContent.includes('viewer'));
    assert.equal(await selector().inputValue(), f.workspace);
    step = 'revoked membership';
    signal('revoke'); await ack('revoke.done');
    await p.locator('.pao-topbar-context').getByLabel('Làm mới quyền doanh nghiệp').click();
    await p.getByRole('heading', {name: 'Chọn doanh nghiệp làm việc', exact: true}).waitFor();
    assert.equal(await p.getByLabel('Doanh nghiệp đang hoạt động').inputValue(), '');
    assert.equal(await p.getByRole('button', {name: /^S12 stream A/}).count(), 0);
    const denied = await p.request.get(f.api + '/v1/sessions/' + f.stream, {headers: {Authorization: 'Bearer ' + token}});
    assert.equal(denied.status(), 404);
    await p.getByLabel('Doanh nghiệp đang hoạt động').selectOption(f.second);
    await p.getByRole('button', {name: /^S12 chat B/}).waitFor();
    await p.reload(); await p.getByRole('button', {name: /^S12 chat B/}).waitFor();
    assert.equal(await selector().inputValue(), f.second);
    step = 'mobile'; await h.mobile();
    assert.deepEqual(h.errors, []);
    console.log(JSON.stringify({pass: true, real_http: true, direct_stream_proxy: true,
      stream_scope: true, server_run_not_cancelled: true, raw_body_discarded: true,
      current_scope_download: true, tabs_independent: true, prompt_scope: true,
      role_refresh_on_focus: true, membership_revoked: true, selection_reload: true,
      synthetic_persisted_events: true, real_provider_called: false, production_accepted: false}));
  } finally {signal('export.release'); await h.close()}
})().catch(error => {
  console.error('P6 browser failed at S12 ' + step + ' ' + String(error.message).split('\n')[0].slice(0, 180));
  process.exitCode = 1;
});
