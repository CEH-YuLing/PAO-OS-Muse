"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import Link from "next/link";
import {usePao} from "@/lib/PaoRuntimeContext";
import "./goal-runner.css";

type Goal={id:string;title:string;version:number;status:string};
type Spec={goal_id:string;goal_version:number;template_plan_id:string;mode:"once"|"cron";timezone:string;cron:string|null;once_at:string|null;misfire:string;grace_seconds:number;fold:string;timeout_seconds:number;max_iterations:number;max_cost_microusd:number;max_elapsed_seconds:number;cost_ceiling_microusd:number;max_duration_seconds:number;success_criteria:{field:string;rule:string;value:string|null}[]};
type Row={id:string;version:number;status:string;spec:Spec;next_at:string|null;error_code:string|null};
type Detail=Row&{slots:{slot_key:string;execution_id:string;spec_hash:string}[];events:unknown[]};
type Pending={path:string;method:string;body:unknown};
const base="/v1/schedules/goals";
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const initial:Spec={goal_id:"",goal_version:1,template_plan_id:"",mode:"once",timezone:"Asia/Ho_Chi_Minh",cron:null,once_at:null,misfire:"coalesce",grace_seconds:300,fold:"first",timeout_seconds:3600,max_iterations:2,max_cost_microusd:0,max_elapsed_seconds:300,cost_ceiling_microusd:0,max_duration_seconds:60,success_criteria:[{field:"text",rule:"non_empty",value:null}]};

export default function GoalSchedulePanel(){
 const {api,me,activeWorkspace}=usePao(),workspace=activeWorkspace?.id;
 const manage=["owner","admin"].includes(activeWorkspace?.role||"");
 const [rows,setRows]=useState<Row[]>([]),[goals,setGoals]=useState<Goal[]>([]);
 const [manager,setManager]=useState(false),[dispatch,setDispatch]=useState(false),[loaded,setLoaded]=useState(false);
 const [spec,setSpec]=useState<Spec>(initial),[once,setOnce]=useState(""),[cron,setCron]=useState("0 9 * * *");
 const [preview,setPreview]=useState<{input:Spec;hash:string;pinned:unknown;next_at:string|null}|null>(null);
 const [ack,setAck]=useState(false),[editing,setEditing]=useState<Row|null>(null),[detail,setDetail]=useState<Detail|null>(null);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[unknown,setUnknown]=useState(false);
 const generation=useRef(0),lock=useRef(false),pending=useRef<Pending|null>(null);
 const load=useCallback(async(ticket=generation.current)=>{
  if(!workspace)return;
  const [gate,list,catalog]=await Promise.all([
   api<{manager_enabled:boolean;dispatch_enabled:boolean}>(base+`/status?workspace_id=${workspace}`),
   api<Row[]>(base+`?workspace_id=${workspace}`),api<Goal[]>(`/v1/goals?workspace_id=${workspace}`)]);
  if(ticket===generation.current){setManager(gate.manager_enabled);setDispatch(gate.dispatch_enabled);setRows(list);setGoals(catalog);setLoaded(true)}
 },[api,workspace]);
 useEffect(()=>{
  const ticket=++generation.current;setLoaded(false);setManager(false);setDispatch(false);setRows([]);setGoals([]);setSpec(initial);setOnce("");setCron("0 9 * * *");setPreview(null);setAck(false);setEditing(null);setDetail(null);pending.current=null;setUnknown(false);setError("");
  void load(ticket).catch(e=>{if(ticket===generation.current)setError((e as Error).message)});
  return()=>{generation.current++};
 },[load]);
 function invalidate(){setPreview(null);setAck(false)}
 function change(patch:Partial<Spec>){setSpec(old=>({...old,...patch}));invalidate()}
 async function work(fn:(ticket:number)=>Promise<void>){
  if(lock.current)return;lock.current=true;setBusy(true);setError("");const ticket=generation.current;
  try{await fn(ticket)}catch(e){if(ticket===generation.current)setError((e as Error).message)}finally{lock.current=false;setBusy(false)}
 }
 async function send(command:Pending,ticket:number){
  pending.current=command;setUnknown(true);await api(command.path,command.method,command.body);
  if(ticket!==generation.current)return;
  pending.current=null;setUnknown(false);invalidate();setEditing(null);setDetail(null);await load(ticket);
 }
 async function review(){invalidate();await work(async ticket=>{
  const input:Spec={...spec,template_plan_id:spec.template_plan_id.trim(),once_at:spec.mode==="once"?new Date(once).toISOString():null,cron:spec.mode==="cron"?cron:null};
  const result=await api<{spec:unknown;confirmation_hash:string;next_at:string|null}>(base+`/preview?workspace_id=${workspace}`,"POST",input);
  if(ticket===generation.current)setPreview({input,hash:result.confirmation_hash,pinned:result.spec,next_at:result.next_at});
 })}
 async function save(){
  if(!preview||!ack||!manager||!manage||pending.current)return;
  const command:Pending=editing?{path:base+"/"+editing.id,method:"PATCH",body:{...preview.input,version:editing.version,request_key:crypto.randomUUID(),confirmation_hash:preview.hash}}
   :{path:base,method:"POST",body:{...preview.input,workspace_id:workspace,request_key:crypto.randomUUID(),confirmation_hash:preview.hash}};
  await work(ticket=>send(command,ticket));
 }
 async function control(row:Row,action:string){
  if(pending.current||!manage)return;
  const message=action==="enable"?"Bật lịch Goal fixed Echo? Mỗi vòng Goal và từng bước vẫn cần duyệt riêng. Không gọi model, Ads hoặc gửi ra ngoài.":action==="archive"?"Lưu trữ lịch và giữ audit? Phiên Goal đã tạo không bị hủy.":"Tắt lịch tương lai? Phiên Goal đã tạo vẫn tồn tại. Mở phiên Goal để yêu cầu hủy riêng và chờ xác minh dừng.";
  if(!window.confirm(message))return;
  await work(ticket=>send({path:base+"/"+row.id+"/control",method:"POST",body:{version:row.version,request_key:crypto.randomUUID(),action}},ticket));
 }
 function edit(row:Row){
  const {spec:s}=row;
  // Copy only client DTO fields: server pins must never become writable inputs.
  const input:Spec={...initial};for(const key of Object.keys(initial) as (keyof Spec)[])Object.assign(input,{[key]:s[key]});
  setSpec(input);setEditing(row);setCron(s.cron||"0 9 * * *");
  if(s.once_at){const d=new Date(s.once_at);setOnce(new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16))}else setOnce("");
  invalidate();setDetail(null);
 }
 const blocked=busy||unknown||!manage;
 const choices=goals.filter(g=>["draft","active"].includes(g.status)||g.id===spec.goal_id);
 const fields: {key:"grace_seconds"|"timeout_seconds"|"max_iterations"|"max_cost_microusd"|"max_elapsed_seconds"|"cost_ceiling_microusd"|"max_duration_seconds";label:string;min:number;max:number}[]=[
  {key:"max_iterations",label:"Số vòng tối đa",min:1,max:20},{key:"max_cost_microusd",label:"Ngân sách mỗi phiên (microUSD)",min:0,max:1000000000},
  {key:"max_elapsed_seconds",label:"Thời gian mỗi phiên (giây)",min:1,max:86400},{key:"cost_ceiling_microusd",label:"Trần mỗi vòng (microUSD)",min:0,max:1000000000},
  {key:"max_duration_seconds",label:"Thời gian mỗi vòng (giây)",min:1,max:120},{key:"timeout_seconds",label:"Timeout lịch (giây)",min:1,max:86400},
  {key:"grace_seconds",label:"Grace quá hạn (giây)",min:0,max:86400}];
 return <div className="gr-workspace"><section aria-label="Goal schedules"><h2>Lịch Goal đã lưu</h2>
  <p role="status" aria-label="Goal schedule readiness">{loaded?(manager?"Quản trị lịch đang bật":"Quản trị lịch đang tắt"):"Đang đọc trạng thái backend"} · {dispatch?"Dispatcher dry-run bật":"Dispatcher chưa bật, lịch không tự tạo phiên"}</p>
  <p>Chỉ fixed Echo, không gọi model. Bật lịch không phải duyệt vòng Goal hay duyệt bước. Ngân sách áp dụng cho từng phiên, không phải tổng ngân sách cron. 1 USD = 1.000.000 microUSD.</p>
  <p>Không chạy chồng cùng Goal; slot quá hạn chỉ lấy lần hợp lệ mới nhất. Lịch completed chỉ nghĩa là đã hết thời điểm chạy, không chứng minh Goal hoàn thành.</p>
  {!manage&&<p>Bạn có quyền xem. Chỉ owner/admin được tạo, sửa hoặc điều khiển lịch; backend kiểm tra lại quyền với mỗi lệnh.</p>}
  <button disabled={busy} onClick={()=>void work(ticket=>load(ticket))}>Cập nhật lịch Goal</button>
  {error&&<p role="alert">{error}</p>}{unknown&&<aside><p>Kết quả lệnh chưa rõ hoặc backend từ chối. Giữ nguyên khóa và nội dung; không tự tạo lệnh mới. Chưa reload hoặc đổi tab: lệnh retry chỉ được giữ trong màn hình này. Nếu xung đột, kiểm tra audit trước khi rời màn hình.</p><button disabled={busy} onClick={()=>void work(ticket=>send(pending.current!,ticket))}>Thử lại đúng lệnh Goal</button></aside>}
  <h3>{editing?"Sửa lịch Goal đã tắt":"Tạo lịch Goal, mặc định tắt"}</h3>
  <p>Chọn Goal rồi nhập mã kế hoạch đã lưu trong <Link href="/automation">Studio</Link>. Backend kiểm tra quyền, phiên bản Goal và ghim kế hoạch; không lấy bản nháp chưa lưu.</p>
  <label>Goal <select aria-label="Scheduled Goal" value={spec.goal_id} disabled={blocked||!!editing} onChange={e=>{const goal=goals.find(g=>g.id===e.target.value);change({goal_id:goal?.id||"",goal_version:goal?.version||1})}}><option value="">Chọn Goal</option>{choices.map(g=><option key={g.id} value={g.id}>{g.title} · v{g.version}</option>)}</select></label>
  {!goals.length&&loaded&&<p>Chưa có Goal. Tạo Goal trước; không tự sinh Goal khi tạo lịch.</p>}
  <label>Plan template ID <input aria-label="Goal schedule plan ID" value={spec.template_plan_id} disabled={blocked} onChange={e=>change({template_plan_id:e.target.value})}/></label>
  <label>Loại lịch <select aria-label="Goal schedule mode" value={spec.mode} disabled={blocked} onChange={e=>change({mode:e.target.value as "once"|"cron"})}><option value="once">Một lần</option><option value="cron">Cron 5 trường</option></select></label>
  <label>Múi giờ IANA <input aria-label="Goal schedule timezone" value={spec.timezone} disabled={blocked} onChange={e=>change({timezone:e.target.value})}/></label>
  {spec.mode==="once"?<label>Thời điểm (giờ máy này, không phải múi giờ nhập phía trên) <input aria-label="Goal schedule once time" type="datetime-local" value={once} disabled={blocked} onChange={e=>{setOnce(e.target.value);invalidate()}}/></label>
   :<label>Cron <input aria-label="Goal schedule cron" value={cron} disabled={blocked} onChange={e=>{setCron(e.target.value);invalidate()}}/></label>}
  <label>Quá hạn <select aria-label="Goal schedule misfire" value={spec.misfire} disabled={blocked} onChange={e=>change({misfire:e.target.value})}><option value="coalesce">Gộp, lấy lần mới nhất</option><option value="skip">Bỏ lần ngoài grace</option></select></label>
  <label>Giờ DST lặp <select aria-label="Goal schedule fold" value={spec.fold} disabled={blocked} onChange={e=>change({fold:e.target.value})}><option value="first">Lần đầu</option><option value="second">Lần thứ hai</option></select></label>
  {fields.map(f=><label key={f.key}>{f.label}<input aria-label={`Goal schedule ${f.key}`} type="number" step="1" min={f.min} max={f.max} value={spec[f.key]} disabled={blocked} onChange={e=>change({[f.key]:Number(e.target.value)})}/></label>)}
  <label>Tiêu chí text <select aria-label="Goal schedule criterion" value={spec.success_criteria[0].rule} disabled={blocked} onChange={e=>change({success_criteria:[{field:"text",rule:e.target.value,value:e.target.value==="equals"?"":null}]})}><option value="non_empty">Không rỗng</option><option value="equals">Khớp chính xác</option></select></label>
  {spec.success_criteria[0].rule==="equals"&&<label>Text cần khớp <textarea aria-label="Goal schedule target" value={spec.success_criteria[0].value||""} maxLength={4096} disabled={blocked} onChange={e=>change({success_criteria:[{field:"text",rule:"equals",value:e.target.value}]})}/></label>}
  <button disabled={blocked||!manager||!loaded||!spec.goal_id||!uuid.test(spec.template_plan_id.trim())||(spec.mode==="once"&&!once)} onClick={()=>void review()}>Xem trước lịch Goal</button>
  {editing&&<button disabled={blocked} onClick={()=>{setEditing(null);setSpec(initial);setOnce("");invalidate()}}>Bỏ sửa lịch Goal</button>}
  {preview&&<><pre aria-label="Goal schedule pinned preview">{JSON.stringify({spec:preview.pinned,next_at:preview.next_at,confirmation_hash:preview.hash},null,2)}</pre>
   <label><input type="checkbox" aria-label="Confirm Goal schedule" checked={ack} disabled={blocked} onChange={e=>setAck(e.target.checked)}/>Tôi đã kiểm tra nguồn, giới hạn và thời điểm. Chỉ lưu lịch tắt, chưa duyệt thực thi.</label>
   <button disabled={blocked||!ack||!manager} onClick={()=>void save()}>{editing?"Lưu sửa lịch Goal tắt":"Lưu lịch Goal tắt"}</button></>}
  {!rows.length&&loaded&&<p>Chưa có lịch Goal được lưu.</p>}
  {rows.map(row=><article key={row.id}><h3>{row.spec.mode} · {row.status}</h3><p>Goal: {goals.find(g=>g.id===row.spec.goal_id)?.title||row.spec.goal_id} · v{row.spec.goal_version}</p><p>{row.id} · lịch v{row.version} · {row.spec.timezone} · lần sau {row.next_at||"không có"}</p>
   {row.error_code&&<p>Cần kiểm tra: {row.error_code}</p>}
   {row.status!=="archived"&&<>{row.status!=="enabled"&&<button disabled={blocked||!manager||row.status==="completed"} onClick={()=>void control(row,"enable")}>Bật lịch Goal</button>}
    <button disabled={blocked||row.status==="disabled"} onClick={()=>void control(row,"disable")}>Tắt lịch Goal tương lai</button>
    <button disabled={blocked||!manager||!["disabled","manual_review"].includes(row.status)} onClick={()=>edit(row)}>Sửa lịch Goal đã tắt</button>
    <button disabled={blocked} onClick={()=>void control(row,"archive")}>Lưu trữ lịch Goal</button></>}
   <button disabled={busy} onClick={()=>void work(async ticket=>{const value=await api<Detail>(base+"/"+row.id);if(ticket===generation.current)setDetail(value)})}>Xem slot và audit Goal</button>
  </article>)}
  {detail&&<section aria-label="Goal schedule detail"><h3>Slot và audit lịch Goal</h3><p>Tắt hoặc lưu trữ lịch không hủy phiên đã tạo. Mở từng phiên để xem approval hoặc yêu cầu hủy.</p>
   {detail.slots.map(slot=><p key={slot.slot_key}>{slot.slot_key} · {uuid.test(slot.execution_id)?<Link href={`/automation/goals?execution=${encodeURIComponent(slot.execution_id)}`}>Mở phiên Goal từ slot</Link>:"Mã phiên không hợp lệ"}</p>)}
   <pre aria-label="Goal schedule slots and audit">{JSON.stringify(detail,null,2)}</pre></section>}
 </section></div>;
}
