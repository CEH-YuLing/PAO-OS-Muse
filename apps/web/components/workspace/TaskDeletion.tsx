"use client";

import {useRef, useState} from "react";
import {Trash2} from "lucide-react";
import type {components} from "../../../../packages/contracts/schema";

type Task = components["schemas"]["TaskOut"];
export default function TaskDeletion({task, api, removed, allowed}: {
  task: Task;
  api: <T>(path: string, method?: string, body?: unknown) => Promise<T>;
  removed: () => void;
  allowed: boolean;
}) {
  const [confirmVersion, setConfirmVersion] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const eligible = task.kind === "human" && task.source === "user"
    && !["running", "completed"].includes(task.status)
    && !task.run_id && !task.goal_id && !task.parent_task_id
    && !task.dependencies.length && !task.evidence.length
    && !Object.keys(task.result_reference).length;
  async function remove() {
    if (lock.current || confirmVersion === null) return;
    lock.current = true; setBusy(true); setError("");
    try {
      await api(`/v1/tasks/${task.id}?version=${confirmVersion}`, "DELETE");
      removed();
    } catch (reason) {
      setError(`${(reason as Error).message}. Nếu mất kết nối, hãy làm mới bảng để kiểm tra trước khi tạo lại.`);
    } finally {lock.current = false; setBusy(false);}
  }
  if (!allowed) return null;
  return <section className="task-deletion" aria-label="Xóa công việc">
    {confirmVersion === null ? <>
      <button type="button" className="task-delete-button" disabled={!eligible} onClick={() => setConfirmVersion(task.version)}>
        <Trash2 size={15}/> Xóa công việc
      </button>
      <small>{eligible ? "Dùng cho công việc tạo nhầm hoặc tạo lỗi. PAO kiểm tra quyền và liên kết trước khi xóa."
        : "Không xóa việc đang chạy, đã hoàn tất, có kết quả hoặc thuộc quy trình. Hãy xử lý trong quy trình gốc."}</small>
    </> : <div role="alertdialog" aria-modal="false" aria-labelledby={`delete-${task.id}`} aria-describedby={`delete-help-${task.id}`}>
      <strong id={`delete-${task.id}`}>Xóa “{task.title}” khỏi bảng công việc?</strong>
      <p id={`delete-help-${task.id}`}>Công việc sẽ biến mất khỏi bảng và không thể tiếp tục xử lý. Lịch sử được giữ lại để đối soát; đây không phải xóa vĩnh viễn dữ liệu. Bạn có thể tạo công việc mới sau đó.</p>
      {error && <p role="alert">{error}</p>}
      <div className="task-delete-actions">
        <button type="button" disabled={busy} onClick={() => {setConfirmVersion(null); setError("");}} autoFocus>Giữ lại</button>
        <button type="button" className="task-delete-button" disabled={busy} onClick={() => void remove()}>{busy ? "Đang xóa…" : "Xác nhận xóa"}</button>
      </div>
    </div>}
  </section>;
}
