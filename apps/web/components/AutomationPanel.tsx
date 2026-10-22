"use client";
import {useEffect,useState} from "react";
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;
type Status={enabled:boolean;address:string|null;namespace:string;task_queue:string};
type Flow={id:string;kind:string;status:string;approval_status:string;payload:Record<string,unknown>;result:Record<string,unknown>;version:number;wait_until:string|null;created_at:string};

export default function AutomationPanel({api,workspace,role}:{api:Api;workspace:string;role:string}){
  const [status,setStatus]=useState<Status|null>(null),[rows,setRows]=useState<Flow[]>([]),[task,setTask]=useState("Kiểm tra và theo dõi báo cáo"),[wait,setWait]=useState(""),[approval,setApproval]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const canStart=["owner","admin","operator"].includes(role),canApprove=["owner","admin"].includes(role);
  async function refresh(){const s=await api<Status>("/v1/automation/status");setStatus(s);setRows(await api<Flow[]>(`/v1/automation/workflows?workspace_id=${workspace}`));}
  useEffect(()=>{void refresh().catch(e=>setError(e.message));},[api,workspace]);
  async function act(fn:()=>Promise<void>){setBusy(true);setError("");try{await fn();await refresh()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
  async function create(){await api("/v1/automation/workflows","POST",{workspace_id:workspace,request_key:crypto.randomUUID(),kind:approval?"approval_wait":"follow_up",payload:{task:task.trim()},approval_required:approval,wait_until:wait?new Date(wait).toISOString():null});}
  async function decide(row:Flow,decision:"approve"|"reject"){await api(`/v1/automation/workflows/${row.id}/decision`,"POST",{version:row.version,decision});}
  return <details className="pao-automation"><summary>Advanced Automation · Phase 17</summary>
    <p>Temporal: <strong>{status?.enabled?"ON":"OFF"}</strong> · namespace {status?.namespace||"—"} · queue {status?.task_queue||"—"}.</p>
    <p className="pao-muted">Workflow dài hạn dùng durable timer và signal phê duyệt. Phase này chỉ cho follow-up nội bộ; không gọi provider write.</p>
    <label>Nhiệm vụ follow-up<input aria-label="Automation task" maxLength={500} value={task} onChange={e=>setTask(e.target.value)}/></label>
    <label>Chờ đến thời điểm<input aria-label="Automation wait until" type="datetime-local" value={wait} onChange={e=>setWait(e.target.value)}/></label>
    <label className="pao-check"><input type="checkbox" checked={approval} onChange={e=>setApproval(e.target.checked)}/>Chờ owner/admin phê duyệt</label>
    <div className="pao-toolbar"><button disabled={!canStart||busy||!status?.enabled||!task.trim()} onClick={()=>void act(create)}>Tạo durable workflow</button><button disabled={busy} onClick={()=>void act(refresh)}>Làm mới</button></div>
    {rows.map(row=><article className="pao-workflow" key={row.id}><strong>{row.kind} · {row.status}</strong><p>{String(row.payload.task||"")} · approval: {row.approval_status} · v{row.version}</p>{row.status==="waiting_approval"&&<div className="pao-toolbar"><button disabled={!canApprove||busy} onClick={()=>void act(()=>decide(row,"approve"))}>Phê duyệt</button><button disabled={!canApprove||busy} onClick={()=>void act(()=>decide(row,"reject"))}>Từ chối</button></div>}</article>)}
    {!status?.enabled&&<p className="pao-muted">Temporal đang khóa mặc định. Bật sau khi self-hosted service và worker đã sẵn sàng.</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
