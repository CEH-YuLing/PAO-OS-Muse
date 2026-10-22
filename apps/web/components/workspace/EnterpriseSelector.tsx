"use client";
import {usePao} from "@/lib/PaoRuntimeContext";
import {settingsLabel} from '@/lib/settings-vi';
import "./enterprise-selector.css";

export default function EnterpriseSelector() {
  const runtime = usePao();
  return <label className="pao-enterprise-selector">Doanh nghiệp
    <select aria-label="Doanh nghiệp đang hoạt động" value={runtime.workspaceId}
      disabled={runtime.switchingWorkspace} onChange={event => void runtime.selectWorkspace(event.target.value)}>
      <option value="" disabled>{runtime.switchingWorkspace ? "Đang kiểm tra quyền…" : "Chọn doanh nghiệp"}</option>
      {runtime.me?.workspaces.map(member => <option key={member.id} value={member.id}>{member.name} · {settingsLabel(member.role)}</option>)}
    </select>
    <button type="button" aria-label="Làm mới quyền doanh nghiệp" title="Kiểm tra lại quyền thành viên"
      disabled={runtime.switchingWorkspace} onClick={() => void runtime.refreshMemberships()}>↻</button>
  </label>;
}
