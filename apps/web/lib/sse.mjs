// Streaming UTF-8 decoder: handles split multibyte characters and CRLF boundaries.
export async function* readEvents(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const {done, value} = await reader.read();
      buffer += decoder.decode(value, {stream: !done});
      let match;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const data = frame.split(/\r?\n/).filter(line => line.startsWith("data:"))
          .map(line => line.slice(5).replace(/^ /, "")).join("\n");
        if (data) yield JSON.parse(data);
      }
      if (buffer.length > 1000000) throw new Error("SSE frame quá lớn");
      if (done) break;
    }
  } finally {
    // Early exit (tenant/session switch) must close the underlying reader too.
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
