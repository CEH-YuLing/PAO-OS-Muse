import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readEvents} from './sse.mjs';

test('decodes Vietnamese across byte boundaries and CRLF, ignores heartbeats', async () => {
  const bytes = new TextEncoder().encode(': heartbeat\r\n\r\nid: 1\r\ndata: {"text":"Chào bạn"}\r\n\r\ndata: {"seq":2}\n\n');
  const stream = new ReadableStream({start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
    controller.close();
  }});
  const result = [];
  for await (const item of readEvents(stream)) result.push(item);
  assert.deepEqual(result, [{text: 'Chào bạn'}, {seq: 2}]);
});

test('rejects malformed event data rather than silently dropping output', async () => {
  const stream = new ReadableStream({start(c) {c.enqueue(new TextEncoder().encode('data: broken\n\n')); c.close();}});
  await assert.rejects(async () => {for await (const item of readEvents(stream)) void item;});
});
