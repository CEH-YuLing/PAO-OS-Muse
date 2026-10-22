import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createTenantTransport} from './tenant-transport.mjs';
import {scopedStorageKey, clearActorStorage} from './tenant-storage.mjs';
import {readEvents} from './sse.mjs';

test('forces no-store, preserves caller headers and aborts the old request signal', async () => {
  const transport = createTenantTransport(), ticket = transport.ticket();
  let options;
  const response = await transport.request(ticket, '/v1/data', {cache: 'force-cache', headers: {'If-Match': 'v1'}}, async (_, init) => {
    options = init; return new Response('SME A');
  });
  assert.equal(options.cache, 'no-store');
  assert.equal(options.headers['If-Match'], 'v1');
  assert.equal(await response.text(), 'SME A');
  transport.invalidate();
  assert.equal(options.signal.aborted, true);
  await assert.rejects(transport.request(ticket, '/v1/data'), /kết quả cũ/);
});

for (const method of ['json', 'blob', 'text', 'arrayBuffer', 'formData']) {
  test(`blocks ${method} and clone after switch even when network response was already buffered`, async () => {
    const transport = createTenantTransport(), ticket = transport.ticket();
    const response = await transport.request(ticket, '/v1/file', {}, async () => new Response('{"private":"A"}'));
    const clone = response.clone();
    transport.invalidate();
    await assert.rejects(async () => response[method](), /kết quả cũ/);
    await assert.rejects(async () => clone[method](), /kết quả cũ/);
  });
}

test('rejects body completing late even if a synthetic fetch ignores abort', async () => {
  let controller;
  const transport = createTenantTransport(), ticket = transport.ticket();
  const body = new ReadableStream({start(value) {controller = value;}});
  const response = await transport.request(ticket, '/v1/export', {}, async () => new Response(body));
  const pending = response.blob();
  transport.invalidate();
  controller.enqueue(new TextEncoder().encode('late private A')); controller.close();
  await assert.rejects(pending, /kết quả cũ/);
});

test('caller cancellation and tenant cancellation are both retained', async () => {
  const transport = createTenantTransport(), caller = new AbortController();
  let combined;
  await transport.request(transport.ticket(), '/v1/upload', {signal: caller.signal}, async (_, init) => {
    combined = init.signal; return new Response('ok');
  });
  caller.abort(); assert.equal(combined.aborted, true);
});

test('preserves feature detection for an unavailable native body method', async () => {
  const transport = createTenantTransport(), native = new Response('A');
  Object.defineProperty(native, 'bytes', {value: undefined});
  const response = await transport.request(transport.ticket(), '/v1/file', {}, async () => native);
  assert.equal(response.bytes, undefined);
  assert.equal(await response.text(), 'A');
});

test('SSE reader rejects/cancels old scope rather than replaying buffered old deltas', async () => {
  let source, cancelled = false;
  const transport = createTenantTransport(), ticket = transport.ticket();
  const body = new ReadableStream({start(controller) {source = controller;}, cancel() {cancelled = true;}});
  const response = await transport.request(ticket, '/v1/events', {}, async () => new Response(body));
  const events = readEvents(response.body);
  source.enqueue(new TextEncoder().encode('data: {"text":"A"}\n\n'));
  assert.equal((await events.next()).value.text, 'A');
  transport.invalidate();
  await assert.rejects(events.next(), /kết quả cũ/);
  assert.equal(cancelled, true);
});

test('early SSE consumer exit cancels and unlocks the underlying body', async () => {
  let cancelled = false;
  const transport = createTenantTransport();
  const body = new ReadableStream({start(controller) {
    controller.enqueue(new TextEncoder().encode('data: {"text":"A"}\n\n'));
  }, cancel() {cancelled = true;}});
  const response = await transport.request(transport.ticket(), '/v1/events', {}, async () => new Response(body));
  const events = readEvents(response.body);
  assert.equal((await events.next()).value.text, 'A');
  await events.return();
  assert.equal(cancelled, true);
  assert.equal(body.locked, false);
});

test('object URLs cannot be created for stale scope; existing URL is revoked on invalidate', async () => {
  const transport = createTenantTransport(), ticket = transport.ticket();
  const url = transport.objectUrl(ticket, new Blob(['A']));
  transport.invalidate(); transport.releaseUrl(url);
  await assert.rejects(fetch(url));
  assert.throws(() => transport.objectUrl(ticket, new Blob(['late'])), /kết quả cũ/);
});

test('storage namespace isolates actor, SME and resource; logout cleanup leaves other users intact', () => {
  const a = scopedStorageKey('owner', 'A', 'voice', 'session');
  const b = scopedStorageKey('owner', 'B', 'voice', 'session');
  const other = scopedStorageKey('other', 'A', 'voice', 'session');
  assert.notEqual(a, b); assert.notEqual(a, other);
  assert.notEqual(scopedStorageKey('a.b', 'c', 'voice'), scopedStorageKey('a', 'b.c', 'voice'));
  assert.throws(() => scopedStorageKey('', 'A', 'prompt'), /Chưa chọn/);
  const rows = new Map([[a, 'a'], [b, 'b'], [other, 'other'], ['unrelated', 'keep']]);
  const storage = {get length() {return rows.size;}, key: index => [...rows.keys()][index], removeItem: key => rows.delete(key)};
  clearActorStorage(storage, 'owner');
  assert.deepEqual([...rows.keys()], [other, 'unrelated']);
});
