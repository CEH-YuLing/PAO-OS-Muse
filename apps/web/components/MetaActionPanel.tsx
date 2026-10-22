"use client";
import {useEffect,useState} from "react";
import type {components} from "../../../packages/contracts/schema";
type S=components["schemas"];
type Api=<T>(path:string,method?:string,body?:unknown)=>Promise<T>;

export default function MetaActionPanel({api,workspace,account,manage}:{api:Api;workspace:string;account:string;manage:boolean}){
  const [status,setStatus]=useState<S["WriteStatus"]|null>(null);const [actions,setActions]=useState<S["ActionOut"][]>([]);
  const [selected,setSelected]=useState<S["ActionDetail"]|null>(null);const [resourceType,setResourceType]=useState<'campaign'|'adset'|'ad'>('campaign');
  const [resourceId,setResourceId]=useState('');const [actionType,setActionType]=useState<'pause'|'resume'|'update_budget'>('pause');
  const [budget,setBudget]=useState('');const [reason,setReason]=useState('');const [dryRun,setDryRun]=useState(true);
  const [busy,setBusy]=useState(false);const [notice,setNotice]=useState('');const [error,setError]=useState('');
  async function refresh(){const [s,a]=await Promise.all([api<S["WriteStatus"]>('/v1/ads/write-status'),api<S["ActionOut"][]>(`/v1/approvals?workspace_id=${workspace}&status=all`)]);setStatus(s);setActions(a.filter(row=>row.account_id===account));}
  useEffect(()=>{let live=true;refresh().catch(e=>{if(live)setError(e.message);});return()=>{live=false;};},[api,workspace,account]);
  async function act(fn:()=>Promise<void>){setBusy(true);setError('');setNotice('');try{await fn();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function propose(){const result=await api<S["ActionDetail"]>('/v1/ads/actions','POST',{workspace_id:workspace,account_id:account,resource_type:resourceType,
    resource_id:resourceId,action_type:actionType,budget_minor_units:actionType==='update_budget'?Number(budget):null,reason,confidence:null,source_agent:'user',
    recommendation_id:null,dry_run:dryRun,request_key:crypto.randomUUID()});setSelected(result);setNotice('Đã tạo snapshot trước thay đổi. Hãy kiểm tra rồi xác nhận riêng.');await refresh();}
  async function decide(kind:'approve'|'reject'){if(!selected)return;const result=await api<S["ActionDetail"]>(`/v1/approvals/${selected.action.id}/${kind}`,'POST',{version:selected.action.version,reason:kind==='reject'?'Rejected in PAO approval inbox':null});setSelected(result);setNotice(kind==='approve'?'Đã duyệt và đưa action vào hàng đợi worker.':'Đã từ chối; Meta không thay đổi.');await refresh();}
  const shown=(value:unknown)=>JSON.stringify(value,null,2);
  return <details className="pao-actions"><summary>Ads Approval · Phase 12</summary>
    <p>Copilot ba bước: tạo snapshot → owner/admin duyệt hoặc từ chối → worker thực thi. UI và Telegram chỉ ghi quyết định, không gọi Meta trực tiếp.</p>
    <p>Live write: <strong>{status?.enabled?'ENABLED':'DISABLED'}</strong> · dry-run vẫn khả dụng · budget change tối đa {status?.max_budget_change_pct??'—'}% · formal approval ở Phase {status?.formal_approval_phase??12}.</p>
    <label>Resource type<select aria-label="Loại resource Meta" value={resourceType} onChange={e=>setResourceType(e.target.value as typeof resourceType)}><option value="campaign">Campaign</option><option value="adset">Ad set</option><option value="ad">Ad</option></select></label>
    <label>Resource ID<input aria-label="Meta resource ID" inputMode="numeric" value={resourceId} onChange={e=>setResourceId(e.target.value)}/></label>
    <label>Action<select aria-label="Loại Meta action" value={actionType} onChange={e=>setActionType(e.target.value as typeof actionType)}><option value="pause">Pause</option><option value="resume">Resume</option><option value="update_budget">Update daily budget</option></select></label>
    {actionType==='update_budget'&&<label>Daily budget mới — minor units<input aria-label="Meta daily budget minor units" type="number" min={1} value={budget} onChange={e=>setBudget(e.target.value)}/></label>}
    <label>Lý do<textarea aria-label="Lý do Meta action" value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000}/></label>
    <label className="pao-check"><input type="checkbox" checked={dryRun} onChange={e=>setDryRun(e.target.checked)}/>Dry-run, không gửi POST tới Meta</label>
    <button disabled={busy||!manage||(!dryRun&&!status?.enabled)||!/^\d+$/.test(resourceId)||reason.trim().length<5||(actionType==='update_budget'&&!budget)} onClick={()=>void act(propose)}>Tạo approval snapshot</button>
    <button disabled={busy} onClick={()=>void act(refresh)}>Làm mới approval inbox</button>
    {selected&&<article className="pao-action-review" aria-label="Meta action review"><strong>{selected.action.action_type} · approval {selected.action.approval_status} · execution {selected.action.execution_status} · v{selected.action.version}</strong>
      <p>Before</p><pre>{shown(selected.action.before_state)}</pre><p>Proposed</p><pre>{shown(selected.action.proposed_state)}</pre>
      <p>Hết hạn: {selected.action.approval_expires_at} · kênh quyết định: {selected.action.decision_channel||'—'}</p>
      {selected.action.policy_id&&<p>Autopilot policy: {selected.action.policy_id} · policy v{selected.action.policy_version}</p>}
      {selected.action.error_code&&<p role="alert">{selected.action.error_code}</p>}
      {selected.action.approval_status==='pending'&&<div className="pao-toolbar"><button disabled={busy||!manage} onClick={()=>void act(()=>decide('approve'))}>{selected.action.dry_run?'Duyệt dry-run':'APPROVE GHI META'}</button><button disabled={busy||!manage} onClick={()=>void act(()=>decide('reject'))}>Từ chối</button></div>}
      <p>Audit events: {selected.audit.map(row=>row.event).join(' → ')}</p></article>}
    <h4>Approval inbox và lịch sử</h4>{actions.length?<ul>{actions.map(row=><li key={row.id}><button onClick={()=>void act(async()=>setSelected(await api<S["ActionDetail"]>(`/v1/approvals/${row.id}`)))}>Chi tiết · {row.action_type} · {row.resource_type} {row.resource_id} · {row.approval_status}/{row.execution_status}</button></li>)}</ul>:<p>Chưa có Ads approval.</p>}
    <p className="pao-muted">Approval hết hạn tự chuyển expired. Live POST không tự retry; kết quả không chắc chắn giữ ở unknown. Compensating action được lưu nhưng không tự chạy.</p>
    {notice&&<p role="status">{notice}</p>}{error&&<p role="alert">{error}</p>}
  </details>;
}
