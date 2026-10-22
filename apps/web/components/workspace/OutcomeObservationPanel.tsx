"use client";
import {useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import "./goal-runner.css";
type Window={status:string;reason:string;causal_effect_proven:boolean;baseline?:{covered_hours:number;expected_hours:number};outcome?:{covered_hours:number;expected_hours:number};delta?:Record<string,string>;confounders:unknown[]};
type Preview={observed_at:string;confirmation_hash:string;outcomes:Record<string,Window>;pins:unknown};
type Saved={id:string;action_id:string;observed_at:string;source_hash:string;statuses:Record<string,string>};
type Detail=Saved&{current_source_matches:boolean;snapshot:{outcomes:Record<string,Window>}};
type Command={path:string;body:{observed_at:string;confirmation_hash:string;request_key:string}};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function Windows({values}:{values:Record<string,Window>}){return <>{Object.entries(values).map(([name,w])=><article key={name}><h3>{name} · {w.status}</h3><p>Lý do: {w.reason}</p>
 {w.baseline&&w.outcome&&<p>Coverage baseline: {w.baseline.covered_hours}/{w.baseline.expected_hours} giờ · sau action: {w.outcome.covered_hours}/{w.outcome.expected_hours} giờ</p>}
 {w.delta&&<pre>{JSON.stringify(w.delta,null,2)}</pre>}{!!w.confounders.length&&<p>Có {w.confounders.length} yếu tố nhiễu; xem bằng chứng trước khi kết luận.</p>}
 <p>Không chứng minh quan hệ nhân quả.</p></article>)}</>}
export default function OutcomeObservationPanel(){
 const {api,me,activeWorkspace}=usePao(),workspace=activeWorkspace?.id,write=activeWorkspace?.role!=="viewer";
 const [enabled,setEnabled]=useState(false),[action,setAction]=useState(""),[preview,setPreview]=useState<Preview|null>(null),[ack,setAck]=useState(false);
 const [rows,setRows]=useState<Saved[]>([]),[detail,setDetail]=useState<Detail|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[unknown,setUnknown]=useState(false);
 const generation=useRef(0),lock=useRef(false),pending=useRef<Command|null>(null);
 useEffect(()=>{const ticket=++generation.current;setEnabled(false);setAction("");setPreview(null);setAck(false);setRows([]);setDetail(null);setUnknown(false);pending.current=null;setError("");
  if(workspace)void api<{enabled:boolean}>(`/v1/ads/outcome-observations/status?workspace_id=${workspace}`).then(v=>{if(ticket===generation.current)setEnabled(v.enabled)}).catch(e=>{if(ticket===generation.current)setError((e as Error).message)});
  return()=>{generation.current++};
 },[api,workspace]);
 async function work(fn:(ticket:number)=>Promise<void>){if(lock.current)return;lock.current=true;setBusy(true);setError("");const ticket=generation.current;
  try{await fn(ticket)}catch(e){if(ticket===generation.current){const message=(e as Error).message;setError(message);
   if(["outcome_preview_expired","outcome_source_changed","outcome_daily_budget_exhausted","outcome_observations_disabled","action_source_stale"].includes(message)){
    pending.current=null;setUnknown(false);setPreview(null);setAck(false);
   }
  }}finally{lock.current=false;setBusy(false)}
 }
 async function history(id:string,ticket:number){const list=await api<Saved[]>(`/v1/ads/actions/${id}/outcome-observations`);if(ticket===generation.current)setRows(list)}
 async function review(){setPreview(null);setAck(false);await work(async ticket=>{const value=await api<Preview>(`/v1/ads/actions/${action.trim()}/outcome-preview`,"POST",{});if(ticket===generation.current)setPreview(value)})}
 async function send(command:Command,ticket:number){pending.current=command;setUnknown(true);await api(command.path,"POST",command.body);if(ticket!==generation.current)return;pending.current=null;setUnknown(false);setPreview(null);setAck(false);await history(action.trim(),ticket)}
 async function save(){if(!preview||!ack||!enabled||!write||pending.current)return;
  const command={path:`/v1/ads/actions/${action.trim()}/outcome-observations`,body:{observed_at:preview.observed_at,confirmation_hash:preview.confirmation_hash,request_key:crypto.randomUUID()}};
  await work(ticket=>send(command,ticket));
 }
 return <div className="gr-workspace"><section aria-label="Pinned outcome observations"><h2>Quan sát outcome đã lưu</h2>
  <p role="status">{enabled?"Lưu quan sát đang bật":"Lưu quan sát đang tắt trên backend"}. Chỉ ghi bằng chứng vào PAO, không thay đổi Ads, không gọi model hay dịch vụ ngoài.</p>
  <p>observed = đủ coverage để quan sát liên hệ; pending = chưa hết cửa sổ; insufficient = thiếu nguồn/dữ liệu hợp lệ. KPI tăng không chứng minh tác động nhân quả. Dữ liệu test không thay nghiệm thu Meta thật.</p>
  {error&&<p role="alert">{error}</p>}
  {unknown&&<aside><p>Kết quả lưu chưa rõ hoặc bị từ chối. Không đổi input, tab hoặc reload: lệnh retry chỉ giữ trong màn hình này. Thử lại đúng khóa; nếu preview hết hạn/nguồn thay đổi, kiểm tra lịch sử trước khi tạo preview mới.</p><button disabled={busy} onClick={()=>void work(ticket=>send(pending.current!,ticket))}>Thử lại đúng quan sát</button></aside>}
  <label>Action đã có (UUID)<input aria-label="Outcome action ID" value={action} disabled={busy||unknown} onChange={e=>{setAction(e.target.value);setPreview(null);setAck(false);setRows([]);setDetail(null)}}/></label>
  <button disabled={busy||unknown||!enabled||!uuid.test(action.trim())} onClick={()=>void review()}>Xem trước quan sát có nguồn</button>
  <button disabled={busy||!enabled||!uuid.test(action.trim())} onClick={()=>void work(ticket=>history(action.trim(),ticket))}>Đọc lịch sử quan sát</button>
  {preview&&<section aria-label="Outcome preview"><Windows values={preview.outcomes}/><pre aria-label="Outcome preview pins">{JSON.stringify({observed_at:preview.observed_at,confirmation_hash:preview.confirmation_hash,pins:preview.pins},null,2)}</pre>
   <label><input aria-label="Confirm outcome observation" type="checkbox" checked={ack} disabled={busy||unknown||!write} onChange={e=>setAck(e.target.checked)}/>Tôi đã kiểm tra nguồn và coverage; lưu snapshot, không sửa Ads hay kết luận nhân quả.</label>
   <button disabled={busy||unknown||!ack||!write||!enabled} onClick={()=>void save()}>Lưu quan sát có nguồn</button></section>}
  {rows.map(row=><article key={row.id}><h3>Snapshot · {row.observed_at}</h3><p>{row.id} · {Object.entries(row.statuses).map(([k,v])=>`${k}: ${v}`).join(" · ")}</p>
   <button disabled={busy} onClick={()=>void work(async ticket=>{const value=await api<Detail>(`/v1/ads/outcome-observations/${row.id}`);if(ticket===generation.current)setDetail(value)})}>Mở snapshot đã lưu</button></article>)}
  {detail&&<section aria-label="Stored outcome snapshot"><h3>Bằng chứng lịch sử</h3><p>{detail.current_source_matches?"Nguồn hiện tại vẫn khớp snapshot":"Nguồn đã thay đổi hoặc không còn xác minh được; snapshot cũ không bị ghi đè"}</p><p>Hash {detail.source_hash}</p><Windows values={detail.snapshot.outcomes}/><details><summary>Pins và nguồn gốc</summary><pre>{JSON.stringify(detail.snapshot,null,2)}</pre></details></section>}
 </section></div>;
}
