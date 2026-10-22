"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import "./goal-runner.css";
type Spec={template_plan_id:string;mode:"once"|"cron";timezone:string;cron:string|null;once_at:string|null;misfire:string;grace_seconds:number;fold:string;timeout_seconds:number};
type Row={id:string;version:number;status:string;spec:Spec;next_at:string|null;error_code:string|null};
type Pending={path:string;method:string;body:unknown};
const base="/v1/schedules/workflows";
export default function StudioSchedulePanel(){
 const {api,me,activeWorkspace}=usePao(),workspace=activeWorkspace?.id;
 const [rows,setRows]=useState<Row[]>([]),[enabled,setEnabled]=useState(false),[dispatch,setDispatch]=useState(false);
 const [plan,setPlan]=useState(""),[mode,setMode]=useState<"once"|"cron">("once"),[zone,setZone]=useState("Asia/Ho_Chi_Minh");
 const [once,setOnce]=useState(""),[cron,setCron]=useState("0 9 * * *"),[misfire,setMisfire]=useState("coalesce"),[fold,setFold]=useState("first");
 const [grace,setGrace]=useState(300),[timeout,setTimeoutSeconds]=useState(3600);
 const [preview,setPreview]=useState<{spec:Spec;hash:string;pins:{snapshot_hash:string;source_binding:string}}|null>(null),[ack,setAck]=useState(false),[editing,setEditing]=useState<Row|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[unknown,setUnknown]=useState(false),[detail,setDetail]=useState<unknown>(null);
 const pending=useRef<Pending|null>(null),lock=useRef(false),generation=useRef(0);
 const load=useCallback(async(ticket=generation.current)=>{
  if(!workspace)return;
  const [gate,value]=await Promise.all([api<{manager_enabled:boolean;dispatch_enabled:boolean}>(base+`/status?workspace_id=${workspace}`),api<Row[]>(base+`?workspace_id=${workspace}`)]);
  if(ticket===generation.current){setEnabled(gate.manager_enabled);setDispatch(gate.dispatch_enabled);setRows(value)}
 },[api,workspace]);
 useEffect(()=>{const ticket=++generation.current;setRows([]);setPreview(null);setAck(false);setEditing(null);pending.current=null;setUnknown(false);setError("");
  void load(ticket).catch(e=>{if(ticket===generation.current)setError((e as Error).message)});return()=>{generation.current++}
 },[load]);
 function invalidate(){setPreview(null);setAck(false)}
 async function work(fn:(ticket:number)=>Promise<void>){if(lock.current)return;lock.current=true;setBusy(true);setError("");const ticket=generation.current;
  try{await fn(ticket)}catch(e){if(ticket===generation.current)setError((e as Error).message)}finally{lock.current=false;if(ticket===generation.current)setBusy(false)}
 }
 async function send(command:Pending,ticket:number){pending.current=command;setUnknown(true);await api(command.path,command.method,command.body);
  if(ticket!==generation.current)return;pending.current=null;setUnknown(false);invalidate();setEditing(null);await load(ticket)
 }
 async function review(){invalidate();await work(async ticket=>{
  const spec:Spec={template_plan_id:plan.trim(),mode,timezone:zone,cron:mode==="cron"?cron:null,once_at:mode==="once"?new Date(once).toISOString():null,
   misfire,grace_seconds:grace,fold,timeout_seconds:timeout};
  const value=await api<{confirmation_hash:string;spec:{snapshot_hash:string;source_binding:string}}>(base+`/preview?workspace_id=${workspace}`,"POST",spec);
  if(ticket===generation.current)setPreview({spec,hash:value.confirmation_hash,pins:{snapshot_hash:value.spec.snapshot_hash,source_binding:value.spec.source_binding}});
 })}
 async function save(){if(!preview||!ack||!enabled||pending.current)return;
  const command:Pending=editing?{path:base+"/"+editing.id,method:"PATCH",body:{...preview.spec,request_key:crypto.randomUUID(),version:editing.version,confirmation_hash:preview.hash}}
   :{path:base,method:"POST",body:{...preview.spec,workspace_id:workspace,request_key:crypto.randomUUID(),confirmation_hash:preview.hash}};
  await work(ticket=>send(command,ticket));
 }
 async function control(row:Row,action:string){
  if(!window.confirm(action==="enable"?"Bật lịch fixed Echo này? Đến giờ vẫn cần duyệt từng bước; không gọi model hoặc Ads.":action==="archive"?"Lưu trữ lịch, giữ audit? Không hủy execution đã được tạo.":"Tắt các lần chạy tương lai? Execution đã tạo không bị hủy; hãy hủy riêng trong workflow panel nếu cần."))return;
  await work(ticket=>send({path:base+"/"+row.id+"/control",method:"POST",body:{request_key:crypto.randomUUID(),version:row.version,action}},ticket));
 }
 function edit(row:Row){setEditing(row);setPlan(row.spec.template_plan_id);setMode(row.spec.mode);setZone(row.spec.timezone);setCron(row.spec.cron||"");
  if(row.spec.once_at){const date=new Date(row.spec.once_at);setOnce(new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16))}else setOnce("");
  setMisfire(row.spec.misfire);setFold(row.spec.fold);setGrace(row.spec.grace_seconds);setTimeoutSeconds(row.spec.timeout_seconds);invalidate();setDetail(null);
 }
 return <div className="gr-workspace"><section aria-label="Persisted workflow schedules"><h2>Lịch workflow đã lưu</h2>
  <p role="status" aria-label="Schedule readiness">{enabled?"Quản trị lịch đang bật":"Quản trị lịch đang tắt"} · {dispatch?"Dispatcher dry-run bật":"Dispatcher chưa bật, lịch không tự tạo execution"}</p>
  <p>Một owner dùng cron hiện có; UTC slot chống trùng sau restart. Không chạy chồng; chỉ lấy slot hợp lệ mới nhất và bỏ qua khi phiên trước chưa rõ. Mất hơn7ngày cần review, không replay vô hạn.</p>
  <button disabled={busy} onClick={()=>void work(ticket=>load(ticket))}>Cập nhật lịch đã lưu</button>
  {error&&<p role="alert">{error}</p>}{unknown&&<aside><p>Kết quả lệnh chưa rõ. Chỉ thử lại đúng khóa/body; không tạo lệnh mới.</p><button disabled={busy} onClick={()=>void work(ticket=>send(pending.current!,ticket))}>Thử lại lệnh lịch</button></aside>}
  <h3>{editing?"Sửa lịch đã tắt":"Tạo lịch, mặc định tắt"}</h3>
  <label>Plan template ID <input aria-label="Schedule template plan ID" value={plan} disabled={busy||unknown} onChange={e=>{setPlan(e.target.value);invalidate()}}/></label>
  <label>Loại lịch <select aria-label="Saved schedule mode" value={mode} disabled={busy||unknown} onChange={e=>{setMode(e.target.value as "once"|"cron");invalidate()}}><option value="once">Một lần</option><option value="cron">Cron5trường</option></select></label>
  <label>Múi giờ lịch <input aria-label="Saved schedule timezone" value={zone} disabled={busy||unknown} onChange={e=>{setZone(e.target.value);invalidate()}}/></label>
  {mode==="once"?<label>Thời điểm (giờ máy này) <input aria-label="Saved schedule once time" type="datetime-local" value={once} disabled={busy||unknown} onChange={e=>{setOnce(e.target.value);invalidate()}}/></label>
   :<label>Cron <input aria-label="Saved schedule cron" value={cron} disabled={busy||unknown} onChange={e=>{setCron(e.target.value);invalidate()}}/></label>}
  <label>Quá hạn <select aria-label="Saved schedule misfire" value={misfire} disabled={busy||unknown} onChange={e=>{setMisfire(e.target.value);invalidate()}}><option value="coalesce">Gộp lần quá hạn, lấy mới nhất</option><option value="skip">Bỏ quá hạn300giây, lấy hợp lệ mới nhất</option></select></label>
  <label>Giờ DST lặp <select aria-label="Saved schedule fold" value={fold} disabled={busy||unknown} onChange={e=>{setFold(e.target.value);invalidate()}}><option value="first">Lần đầu</option><option value="second">Lần thứ hai</option></select></label>
  <label>Grace khi bỏ quá hạn (giây) <input aria-label="Saved schedule grace" type="number" min="0" max="86400" step="1" value={grace} disabled={busy||unknown} onChange={e=>{setGrace(Number(e.target.value));invalidate()}}/></label>
  <label>Timeout phiên (giây) <input aria-label="Saved schedule timeout" type="number" min="1" max="86400" step="1" value={timeout} disabled={busy||unknown} onChange={e=>{setTimeoutSeconds(Number(e.target.value));invalidate()}}/></label>
  <button disabled={busy||unknown||!enabled||!plan||(mode==="once"&&!once)} onClick={()=>void review()}>Xem trước lịch đã ghim</button>
  {editing&&<button disabled={busy||unknown} onClick={()=>{setEditing(null);invalidate()}}>Bỏ sửa lịch</button>}
  {preview&&<><pre aria-label="Pinned schedule preview">{JSON.stringify(preview,null,2)}</pre><label><input type="checkbox" checked={ack} disabled={busy||unknown} onChange={e=>setAck(e.target.checked)}/>Tôi đã kiểm tra lịch/pins. Chỉ lưu, chưa bật và chưa duyệt bước.</label>
   <button disabled={busy||unknown||!ack||!enabled} onClick={()=>void save()}>{editing?"Lưu sửa lịch ở trạng thái tắt":"Lưu lịch ở trạng thái tắt"}</button></>}
  {!rows.length&&<p>Chưa có lịch được lưu.</p>}
  {rows.map(row=><article key={row.id}><h3>{row.spec.mode} · {row.status}</h3><p>{row.id} · v{row.version} · {row.spec.timezone} · lần sau {row.next_at||"không có"}</p>{row.error_code&&<p>Cần kiểm tra: {row.error_code}</p>}
   {row.status!=="archived"&&<>{row.status!=="enabled"&&<button disabled={busy||unknown||!enabled||row.status==="completed"} onClick={()=>void control(row,"enable")}>Bật lịch</button>}
    <button disabled={busy||unknown||row.status==="disabled"} onClick={()=>void control(row,"disable")}>Tắt lịch tương lai</button>
    <button disabled={busy||unknown||!enabled||!["disabled","manual_review"].includes(row.status)} onClick={()=>edit(row)}>Sửa lịch đã tắt</button>
    <button disabled={busy||unknown} onClick={()=>void control(row,"archive")}>Lưu trữ lịch</button></>}
   <button disabled={busy} onClick={()=>void work(async ticket=>{const value=await api(base+"/"+row.id);if(ticket===generation.current)setDetail(value)})}>Xem slot và audit</button>
  </article>)}
  {detail!==null&&<pre aria-label="Schedule slots and audit">{JSON.stringify(detail,null,2)}</pre>}
 </section></div>;
}
