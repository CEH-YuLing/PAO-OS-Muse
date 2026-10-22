// Client isolation only. The server still authorizes every resource/action.
const stale = () => new Error('Ngữ cảnh doanh nghiệp đã thay đổi; kết quả cũ bị loại bỏ.');

export function createTenantTransport() {
  let revision = 0;
  let active = {revision, controller: new AbortController()};
  const urls = new Set();
  function assert(ticket) {
    if (ticket !== active || ticket.controller.signal.aborted) throw stale();
  }
  function guardedBody(body, ticket) {
    if (!body) return null;
    const reader = body.getReader();
    let closed = false;
    let output;
    const dispose = async reason => {
      try {await reader.cancel(reason);} finally {reader.releaseLock();}
    };
    const clean = () => ticket.controller.signal.removeEventListener('abort', abort);
    const abort = () => {
      if (closed) return;
      closed = true; clean(); output.error(stale());
      void dispose().catch(() => {});
    };
    return new ReadableStream({
      start(controller) {
        output = controller;
        ticket.controller.signal.addEventListener('abort', abort, {once: true});
        if (ticket.controller.signal.aborted) abort();
      },
      async pull(controller) {
        try {
          assert(ticket);
          const next = await reader.read();
          assert(ticket);
          if (closed) return;
          if (next.done) {closed = true; clean(); controller.close(); reader.releaseLock();}
          else controller.enqueue(next.value);
        } catch (error) {
          if (!closed) {closed = true; clean(); controller.error(error); void dispose().catch(() => {});}
        }
      },
      async cancel(reason) {closed = true; clean(); await dispose(reason);},
    });
  }
  function responseGuard(response, ticket) {
    let stream;
    return new Proxy(response, {get(target, property) {
      assert(ticket);
      if (property === 'clone') return () => {assert(ticket); return responseGuard(target.clone(), ticket);};
      if (property === 'body') {if (stream === undefined) stream = guardedBody(target.body, ticket); return stream;}
      if (['json', 'blob', 'text', 'arrayBuffer', 'formData', 'bytes'].includes(property) && typeof target[property] === 'function') {
        return async (...args) => {
          assert(ticket);
          const value = await target[property](...args);
          assert(ticket);
          return value;
        };
      }
      const value = Reflect.get(target, property, target);
      return typeof value === 'function' ? value.bind(target) : value;
    }});
  }
  return {
    ticket: () => active,
    assert,
    invalidate() {
      active.controller.abort();
      for (const url of urls) URL.revokeObjectURL(url);
      urls.clear();
      active = {revision: ++revision, controller: new AbortController()};
      return active.revision;
    },
    async request(ticket, path, init = {}, fetcher = fetch) {
      assert(ticket);
      // Never honor a caller's force-cache for authenticated tenant data.
      const signal = init.signal ? AbortSignal.any([ticket.controller.signal, init.signal]) : ticket.controller.signal;
      const response = await fetcher(path, {...init, cache: 'no-store', signal});
      assert(ticket);
      return responseGuard(response, ticket);
    },
    objectUrl(ticket, blob) {assert(ticket); const url = URL.createObjectURL(blob); urls.add(url); return url;},
    releaseUrl(url) {if (urls.delete(url)) URL.revokeObjectURL(url);},
  };
}
