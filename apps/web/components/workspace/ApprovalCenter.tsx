"use client";

import {useCallback, useEffect, useState} from "react";
import type {components} from "../../../../packages/contracts/schema";
import {usePao} from "@/lib/PaoRuntimeContext";
import "./approval-center.css";

type Approval = components["schemas"]["UnifiedApproval"];
type Diagnostics = components["schemas"]["DeliveryDiagnostics"];

export default function ApprovalCenter({workspaceId, onChanged}: {workspaceId: string; onChanged: () => void}) {
  const {api} = usePao();
  const [enabled, setEnabled] = useState(false), [rows, setRows] = useState<Approval[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [selected, setSelected] = useState<Approval | null>(null), [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const status = await api<{enabled: boolean}>("/v1/business-events/status");
      setEnabled(status.enabled); if (!status.enabled) {setRows([]); setSelected(null); return;}
      const [items, state] = await Promise.all([
        api<Approval[]>(`/v1/business-events/approvals?workspace_id=${workspaceId}`),
        api<Diagnostics>(`/v1/business-events/diagnostics?workspace_id=${workspaceId}`),
      ]);
      setRows(items); setDiagnostics(state);
    } catch (reason) {setError((reason as Error).message); setRows([]); setSelected(null);}
  }, [api, workspaceId]);
  useEffect(() => {setSelected(null); setReviewed(false); void load();}, [load]);
  async function decide(decision: "approve" | "reject") {
    if (!selected || !reviewed || busy) return;
    setBusy(true); setError("");
    try {
      await api("/v1/business-events/approvals/decision", "POST", {ticket: selected.ticket, decision});
      setSelected(null); setReviewed(false); await load(); onChanged();
    } catch (reason) {setError((reason as Error).message); setSelected(null); setReviewed(false); await load();}
    finally {setBusy(false);}
  }
  if (!enabled) return null;
  return <section className="approval-center" aria-label="Trung tâm phê duyệt">
    <h2>Trung tâm phê duyệt</h2>
    <p>Task, Tool và Ads giữ quyền riêng. Duyệt không đồng nghĩa hành động đã thực thi.</p>
    <button type="button" disabled={busy} onClick={() => {setSelected(null); setReviewed(false); void load();}}>Tải lại phê duyệt</button>
    {error && <p role="alert">{error}</p>}
    {rows.length === 0 && <p>Không có yêu cầu chờ duyệt.</p>}
    <ul>{rows.map(row => <li key={`${row.kind}:${row.id}`}>
      <button type="button" disabled={busy} onClick={() => {setSelected(row); setReviewed(false); setError("");}}>
        Xem phê duyệt: {row.title}
      </button> · {row.kind} · v{row.version} · {row.dry_run ? "Mô phỏng" : ""}
    </li>)}</ul>
    {selected && <div role="region" aria-label="Nội dung cần duyệt">
      <h3>{selected.title}</h3>
      <p>Hết hạn: {new Date(selected.expires_at).toLocaleString("vi-VN")}</p>
      <pre style={{whiteSpace: "pre-wrap", overflowWrap: "anywhere"}}>{JSON.stringify(selected.review, null, 2)}</pre>
      <small>Input hash: {selected.input_hash}</small>
      <label><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)}/> Tôi đã kiểm tra nội dung và phạm vi thao tác</label>
      <button type="button" disabled={busy || !reviewed || !selected.can_decide} onClick={() => void decide("approve")}>Duyệt yêu cầu</button>
      <button type="button" disabled={busy || !reviewed || !selected.can_decide} onClick={() => void decide("reject")}>Từ chối yêu cầu</button>
      {!selected.can_decide && <p>Không đủ quyền, tính năng chưa bật hoặc yêu cầu đã hết hạn.</p>}
    </div>}
    {diagnostics && <p aria-label="Trạng thái hàng đợi sự kiện">Đã xử lý: {diagnostics.states.delivered || 0} · Chờ: {diagnostics.states.pending || 0} · Cần kiểm tra: {diagnostics.states.dead_letter || 0}</p>}
  </section>;
}
