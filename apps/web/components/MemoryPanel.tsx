"use client";
import {useEffect, useRef, useState} from "react";
import type {components} from "../../../packages/contracts/schema";
type S = components["schemas"];
type Api = <T>(path: string, method?: string, body?: unknown) => Promise<T>;

export function BrandPicker({api, workspace, value, onChange, disabled}: {
  api: Api; workspace: string; value: string; onChange: (id: string) => void; disabled: boolean;
}) {
  const [brands, setBrands] = useState<S["BrandOut"][]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const alive = useRef(true);
  useEffect(() => {
    let live = true;
    alive.current = true;
    api<S["BrandOut"][]>(`/v1/brands?workspace_id=${workspace}`).then(x => {if (live) setBrands(x);})
      .catch(e => {if (live) setError(e.message);});
    return () => {live = false; alive.current = false;};
  }, [api, workspace]);
  return <details><summary>Thương hiệu cho hội thoại mới</summary>
    <label>Phạm vi thương hiệu<select aria-label="Phạm vi thương hiệu" value={value} disabled={disabled || saving} onChange={e => onChange(e.target.value)}>
      <option value="">Không gắn thương hiệu</option>{brands.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
    </select></label>
    <form onSubmit={async e => {e.preventDefault(); setSaving(true); setError("");
      try {const b = await api<S["BrandOut"]>("/v1/brands", "POST", {workspace_id: workspace, name: name.trim()});
        if (!alive.current) return;
        setBrands(old => old.some(x => x.id === b.id) ? old : [...old, b]); onChange(b.id); setName("");
      } catch (e) {if (alive.current) setError((e as Error).message);} finally {if (alive.current) setSaving(false);}
    }}><label>Tên thương hiệu mới<input maxLength={120} value={name} onChange={e => setName(e.target.value)} /></label>
      <button disabled={disabled || saving || !name.trim()}>Tạo thương hiệu</button></form>
    <p className="pao-muted">Lựa chọn này áp dụng khi tạo hội thoại mới. Bộ nhớ của từng thương hiệu được giữ riêng.</p>
    {error && <p role="alert">{error}</p>}
  </details>;
}

export default function MemoryPanel({api, session, canWrite}: {api: Api; session: S["SessionOut"]; canWrite: boolean}) {
  const [items, setItems] = useState<S["MemoryOut"][]>([]);
  const [status, setStatus] = useState<S["MemoryStatus"] | null>(null);
  const [enabled, setEnabled] = useState(session.memory_enabled ?? true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [searched, setSearched] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [offset, setOffset] = useState(0);
  const [edit, setEdit] = useState<S["MemoryOut"] | null>(null);
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [importance, setImportance] = useState(3);
  const live = useRef(true);
  const revision = useRef(0);
  const scope = {workspace_id: session.workspace_id, brand_id: session.brand_id ?? null};
  const scopeQuery = `workspace_id=${session.workspace_id}${session.brand_id ? `&brand_id=${session.brand_id}` : ""}`;
  async function refresh(page = offset) {
    const ticket = ++revision.current;
    const rows = await api<S["MemoryOut"][]>(`/v1/memory?${scopeQuery}&offset=${page}`);
    if (live.current && ticket === revision.current) {setItems(rows); setOffset(page); setSearched(false); setDegraded(false);}
  }
  useEffect(() => {
    live.current = true;
    let previous = "";
    const poll = async () => {
      try {
        const next = await api<S["MemoryStatus"]>(`/v1/memory/status?session_id=${session.id}`);
        if (!live.current) return;
        setStatus(next);
        const signature = JSON.stringify(next);
        if (previous && previous !== signature && next.job_status === "completed") await refresh(0);
        previous = signature;
      } catch (e) {if (live.current) setError((e as Error).message);}
    };
    void refresh(0).catch(e => {if (live.current) setError(e.message);});
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => {live.current = false; revision.current++; clearInterval(timer);};
    // Parent keys this panel by identity and session, resetting all private drafts on navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, session.id]);
  async function act(action: () => Promise<unknown>, reload = true) {
    setBusy(true); setError("");
    try {await action(); if (live.current && reload) await refresh();}
    catch (e) {if (live.current) setError((e as Error).message);}
    finally {if (live.current) setBusy(false);}
  }
  function clear() {setEdit(null); setKey(""); setValue(""); setImportance(3);}
  const jobLabels: Record<string, string> = {queued: "Đang chờ trích xuất", running: "Đang trích xuất", completed: "Đã xử lý", failed: "Trích xuất thất bại"};
  return <details className="pao-memory"><summary>Bộ nhớ cá nhân · {session.brand_id ? "Theo thương hiệu" : "Không gắn thương hiệu"}</summary>
    <p className="pao-muted">Chỉ dùng trong tài khoản và phạm vi này. Dữ kiện mâu thuẫn cần bạn duyệt. Xóa bộ nhớ không xóa nội dung hội thoại gốc.</p>
    <label className="pao-check"><input type="checkbox" checked={enabled} disabled={busy || !canWrite} onChange={e => {
      const next = e.target.checked;
      void act(async () => {await api(`/v1/sessions/${session.id}`, "PATCH", {memory_enabled: next});
        if (live.current) setEnabled(next);});
    }} />Dùng và ghi nhớ cho hội thoại này</label>
    <p role="status">{!enabled ? "Memory đã tắt cho hội thoại này" : status && !status.enabled ? "Memory đang tắt trên máy chủ" : "Memory đang bật"}
      {status?.job_status ? ` · ${jobLabels[status.job_status] || status.job_status} · ${status.extracted} dữ kiện mới` : ""}</p>
    {status?.error_code && <p className="pao-muted">{status.error_code === "embedding_unavailable" ? "Đã lưu dữ kiện; embedding chưa sẵn sàng, có thể tìm theo từ khóa." : `Trạng thái Memory: ${status.error_code}`}</p>}
    <form onSubmit={async e => {e.preventDefault(); const ticket = ++revision.current; setBusy(true); setError("");
      try {const result = await api<S["MemorySearchResult"]>("/v1/memory/search", "POST", {...scope, query});
        if (live.current && ticket === revision.current) {setItems(result.items.map(x => x.memory)); setSearched(true); setDegraded(result.degraded);}
      } catch (e) {if (live.current) setError((e as Error).message);} finally {if (live.current) setBusy(false);}
    }}><label>Tìm bộ nhớ<input value={query} maxLength={2000} onChange={e => setQuery(e.target.value)} /></label>
      <button disabled={busy || !query.trim()}>Tìm kiếm</button> <button type="button" disabled={busy} onClick={() => void act(() => refresh(0), false)}>Tải danh sách</button></form>
    {degraded && <p className="pao-muted">Đang tìm theo từ khóa vì embedding chưa sẵn sàng.</p>}
    <div className="pao-memory-list" aria-label="Danh sách bộ nhớ">{!items.length && <p>Chưa có dữ kiện phù hợp trong phạm vi này.</p>}
      {items.map(m => <article key={m.id} className="pao-message">
        <strong>{m.key}</strong><p>{m.value}</p><p className="pao-muted">{m.status === "active" ? "Đang dùng" : m.status === "pending" ? "Chờ duyệt mâu thuẫn" : "Đã thay thế"} · Mức quan trọng {m.importance}/5 · Phiên bản {m.version}</p>
        <small>{m.source_run_id ? `Nguồn run: ${m.source_run_id}` : "Thêm thủ công"}{!m.embedding_model ? " · Chưa có embedding" : ""}</small>
        {canWrite && <div className="pao-toolbar"><button disabled={busy} onClick={() => {setEdit(m); setKey(m.key); setValue(m.value); setImportance(m.importance);}}>Sửa</button>
          {m.status !== "active" && <button disabled={busy} onClick={() => void act(() => api(`/v1/memory/${m.id}`, "PATCH", {key: m.key, value: m.value, importance: m.importance, version: m.version, status: "active"}))}>Duyệt và dùng</button>}
          <button disabled={busy} onClick={() => void act(async () => {await api(`/v1/memory/${m.id}?version=${m.version}`, "DELETE"); if (edit?.id === m.id) clear();})}>Xóa</button></div>}
      </article>)}</div>
    {!searched && <div className="pao-toolbar"><button disabled={busy || offset === 0} onClick={() => void act(() => refresh(Math.max(0, offset - 100)), false)}>Trang trước</button>
      <span>Trang {offset / 100 + 1}</span><button disabled={busy || items.length < 100} onClick={() => void act(() => refresh(offset + 100), false)}>Trang sau</button></div>}
    {canWrite && <form onSubmit={e => {e.preventDefault(); void act(async () => {
      await api(edit ? `/v1/memory/${edit.id}` : "/v1/memory", edit ? "PATCH" : "POST", edit
        ? {key, value, importance, version: edit.version, status: edit.status === "active" ? "active" : "pending"}
        : {...scope, key, value, importance}); if (live.current) clear();
    });}}><h3>{edit ? "Sửa dữ kiện" : "Thêm dữ kiện"}</h3>
      <label>Khóa dữ kiện<input required minLength={2} maxLength={120} value={key} onChange={e => setKey(e.target.value)} placeholder="Ví dụ: target_market" /></label>
      <label>Dữ kiện<textarea aria-label="Dữ kiện" required minLength={5} maxLength={500} value={value} onChange={e => setValue(e.target.value)} /></label>
      <label>Mức quan trọng<select aria-label="Mức quan trọng" value={importance} onChange={e => setImportance(Number(e.target.value))}>{[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
      <button disabled={busy}>{edit ? "Lưu thay đổi" : "Thêm bộ nhớ"}</button> {edit && <button type="button" disabled={busy} onClick={clear}>Bỏ sửa</button>}
      <p className="pao-muted">Thay đổi áp dụng cho lần truy xuất tiếp theo. Cùng khóa nhưng khác giá trị sẽ được lưu chờ duyệt.</p>
    </form>}
    {error && <p className="pao-error" role="alert">{error}</p>}
  </details>;
}
