"use client";
import {useEffect, useState} from "react";
import type {components} from "../../../packages/contracts/schema";
type Snapshot = components["schemas"]["ExecutionSnapshot"];
type Plan = {goal?: string; fallback?: boolean; steps?: {agent: string; task: string; depends_on: number[]}[]};

export default function ExecutionPanel({api, runId, active}: {
  api: <T>(path: string, method?: string, body?: unknown) => Promise<T>; runId: string; active: boolean;
}) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const data = await api<Snapshot>(`/v1/runs/${runId}/execution`);
        if (live) {setSnapshot(data); setError("");}
      } catch (e) {if (live) setError((e as Error).message);}
      if (live && active) timer = setTimeout(() => void load(), 2000);
    }
    void load();
    return () => {live = false; clearTimeout(timer);};
  }, [api, runId, active, retry]);
  const plan = snapshot?.plan as Plan | undefined;
  const labels: Record<string, string> = {running: "Đang thực thi", completed: "Hoàn tất", failed: "Thất bại", cancelled: "Đã hủy"};
  return <details className="pao-execution"><summary>Kế hoạch và kết quả agent</summary>
    <p className="pao-muted">Các bước thực thi và kết quả công việc; kết quả công cụ và phê duyệt hiển thị ở bảng riêng.</p>
    {plan?.goal && <p>Mục tiêu: {plan.goal}</p>}
    {plan?.fallback && <p role="status">Planner chưa tạo được kế hoạch hợp lệ. Chief trả lời trực tiếp.</p>}
    {plan?.steps?.length === 0 && !plan.fallback && <p>Chief xử lý trực tiếp yêu cầu này.</p>}
    {!!plan?.steps?.length && <ol>{plan.steps.map((step, index) => <li key={index}>
      <strong>{step.agent}</strong>: {step.task}{step.depends_on.length ? ` · Dùng kết quả bước ${step.depends_on.map(n => n + 1).join(", ")}` : ""}
    </li>)}</ol>}
    <div aria-label="Kết quả các agent">{snapshot?.agents.map(agent => <article key={agent.id} className="pao-message">
      <strong>{agent.agent_key} · {labels[agent.status] || agent.status}</strong>
      <p>{agent.task || "Hội thoại từ phiên bản trước"}</p>
      {agent.output && <details><summary>Xem kết quả {agent.agent_key}</summary><p>{agent.output}</p></details>}
      <small>Prompt {agent.prompt_version} · {agent.model}</small>
    </article>)}</div>
    {error && <p className="pao-error" role="alert">{error} <button onClick={() => setRetry(n => n + 1)}>Tải lại các bước</button></p>}
  </details>;
}
