"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import Link from "next/link";
import {usePao} from "@/lib/PaoRuntimeContext";
import PaoAppShell from "./PaoAppShell";
import WorkflowRunPanel from "./WorkflowRunPanel";
import "./goal-runner.css";
type Goal={id:string;title:string;version:number;workspace_id:string;status:string};
type Plan={plan_id:string;snapshot:{sha256:string;workspace_id:string}};
type Proposal={plan_id:string;snapshot_hash:string;cost_ceiling_microusd:number;max_duration_seconds:number};
type Draft={request_key:string;goal_version:number;proposal:Proposal;policy:{max_iterations:number;max_cost_microusd:number;max_elapsed_seconds:number;deadline_unix_ms:number};success_criteria:{field:string;rule:string;value:string|null}[]};
type Preview={confirmation_hash:string;envelope:{execution_id:string}};
type Execution={execution_id:string;workspace_id:string;goal_id:string;status:string;version:number;sequence:number;implementation:string;reserved_cost_microusd:number;cancel_requested:boolean;state:{iteration?:number;reason?:string;cost_microusd?:number;proposal?:Proposal;proposal_hash?:string;receipt_hash?:string;checks?:{field:string;rule:string;passed:boolean}[]};commands:unknown[];events:unknown[]};
type Pending={path:string;body:unknown;executionId:string};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const terminal=new Set(["completed","cancelled","budget_exhausted","deadline_exceeded","manual_review"]);
export default function GoalRunnerWorkspace(){
 const {api,me,activeWorkspace}=usePao(),workspace=activeWorkspace?.id;
 const [enabled,setEnabled]=useState(false),[goals,setGoals]=useState<Goal[]>([]);
 const [goalId,setGoalId]=useState(""),[planId,setPlanId]=useState("");
 const [iterations,setIterations]=useState(2),[budget,setBudget]=useState(10),[ceiling,setCeiling]=useState(5),[duration,setDuration]=useState(60),[elapsed,setElapsed]=useState(600);
 const [rule,setRule]=useState("non_empty"),[target,setTarget]=useState("");
 const [preview,setPreview]=useState<{draft:Draft;result:Preview}|null>(null),[ack,setAck]=useState(false);
 const [busy,setBusy]=useState(false),[error,setError]=useState(""),[retry,setRetry]=useState(false);
 const [executionId,setExecutionId]=useState(""),[execution,setExecution]=useState<Execution|null>(null),[replanId,setReplanId]=useState("");
 const generation=useRef(0),locked=useRef(false),refreshing=useRef(false),pending=useRef<Pending|null>(null);
 const refresh=useCallback(async(id:string,ticket=generation.current)=>{
  if(!workspace)return;
  const [gate,value]=await Promise.all([api<{execution_enabled:boolean}>(`/v1/goal-runners/status?workspace_id=${workspace}`),api<Execution>(`/v1/goal-executions/${id}`)]);
  if(ticket!==generation.current)return;
  if(value.workspace_id!==workspace)throw new Error("Phiên không thuộc workspace đang mở.");
  setEnabled(gate.execution_enabled);setExecution(value);
 },[api,workspace]);
 useEffect(()=>{
  const ticket=++generation.current;setExecution(null);setPreview(null);setAck(false);setEnabled(false);setGoals([]);setError("");setRetry(false);pending.current=null;
  if(!workspace)return;
  const id=new URL(window.location.href).searchParams.get("execution")||"";setExecutionId(uuid.test(id)?id:"");
  Promise.all([api<{execution_enabled:boolean}>(`/v1/goal-runners/status?workspace_id=${workspace}`),api<Goal[]>(`/v1/goals?workspace_id=${workspace}`)]).then(([gate,rows])=>{
   if(ticket===generation.current){setEnabled(gate.execution_enabled);setGoals(rows.filter(g=>["draft","active"].includes(g.status)))}
  }).catch(e=>{if(ticket===generation.current)setError((e as Error).message)});
  if(uuid.test(id))void refresh(id,ticket).catch(e=>{if(ticket===generation.current)setError((e as Error).message)});
  return()=>{generation.current++};
 },[api,workspace,refresh]);
 useEffect(()=>{
  if(!execution||(terminal.has(execution.status)&&!execution.reserved_cost_microusd))return;
  let alive=true;const timer=setInterval(()=>{
   if(!alive||locked.current||refreshing.current||document.hidden)return;
   refreshing.current=true;void refresh(execution.execution_id).catch(e=>{if(alive)setError((e as Error).message)}).finally(()=>{refreshing.current=false});
  },2000);return()=>{alive=false;clearInterval(timer)};
 },[execution,refresh]);
 function invalidate(){setPreview(null);setAck(false)}
 function pinUrl(id:string){const url=new URL(window.location.href);url.searchParams.set("execution",id);window.history.replaceState(null,"",url);setExecutionId(id)}
 async function work(action:(ticket:number)=>Promise<void>){
  if(locked.current)return;locked.current=true;setBusy(true);setError("");const ticket=generation.current;
  try{await action(ticket)}catch(e){if(ticket===generation.current)setError((e as Error).message)}finally{locked.current=false;if(ticket===generation.current)setBusy(false)}
 }
 async function plan(id:string){
  if(!uuid.test(id.trim()))throw new Error("Plan ID cần là UUID của kế hoạch đã lưu trong Studio.");
  const value=await api<Plan>(`/v1/studio/plans/${id.trim()}`);if(value.snapshot.workspace_id!==workspace)throw new Error("Kế hoạch không thuộc workspace này.");return value;
 }
 function proposal(value:Plan):Proposal{return {plan_id:value.plan_id,snapshot_hash:value.snapshot.sha256,cost_ceiling_microusd:ceiling,max_duration_seconds:duration}}
 async function review(){invalidate();await work(async ticket=>{
  const selected=goals.find(g=>g.id===goalId);if(!selected)throw new Error("Chọn Goal nháp hoặc active.");
  const value=await plan(planId),draft:Draft={request_key:crypto.randomUUID(),goal_version:selected.version,proposal:proposal(value),policy:{max_iterations:iterations,max_cost_microusd:budget,max_elapsed_seconds:elapsed,deadline_unix_ms:Date.now()+elapsed*1000},success_criteria:[{field:"text",rule,value:rule==="equals"?target:null}]};
  const result=await api<Preview>(`/v1/goals/${selected.id}/dry-run-admission-preview`,"POST",draft);if(ticket===generation.current)setPreview({draft,result});
 })}
 async function deliver(command:Pending,ticket:number){
  pending.current=command;setRetry(true);pinUrl(command.executionId);
  // An unknown response is not proof that the command was not committed.
  // Explicit retries retain the same request key/body. No automatic POST retry.
  await api(command.path,"POST",command.body);if(ticket!==generation.current)return;
  pending.current=null;setRetry(false);setAck(false);setPreview(null);await refresh(command.executionId,ticket);
 }
 async function admit(){if(!preview||!ack||!enabled||pending.current)return;const frozen=preview;await work(ticket=>deliver({executionId:frozen.result.envelope.execution_id,path:`/v1/goals/${goalId}/dry-run-runners`,body:{...frozen.draft,confirmation_hash:frozen.result.confirmation_hash}},ticket))}
 async function decision(value:"approve"|"reject"){
  if(!execution?.state.proposal_hash||pending.current||!enabled)return;
  if(!window.confirm(value==="approve"?"Duyệt riêng vòng dry-run này? Mỗi bước child vẫn cần duyệt; không gọi model hoặc Ads.":"Từ chối vòng này và dừng Goal runner?"))return;
  const row=execution;await work(ticket=>deliver({executionId:row.execution_id,path:`/v1/goal-executions/${row.execution_id}/decision`,body:{request_key:crypto.randomUUID(),version:row.version,proposal_hash:row.state.proposal_hash,decision:value}},ticket));
 }
 async function replan(){
  if(!execution||pending.current||!enabled)return;const row=execution;await work(async ticket=>{
   const next=await plan(replanId);if(!window.confirm("Gửi kế hoạch mới? Đây chưa phải approval và chưa chạy child."))return;
   await deliver({executionId:row.execution_id,path:`/v1/goal-executions/${row.execution_id}/proposal`,body:{request_key:crypto.randomUUID(),version:row.version,proposal:proposal(next)}},ticket);
  });
 }
 async function cancel(){
  if(!execution||!window.confirm("Yêu cầu hủy? Ngân sách chỉ được giải phóng sau khi backend xác minh tác vụ đã dừng."))return;
  const row=execution;
  // Safety cancellation remains available with gates off or an unknown decision ACK.
  await work(ticket=>deliver({executionId:row.execution_id,path:`/v1/goal-executions/${row.execution_id}/cancel`,body:{request_key:crypto.randomUUID()}},ticket));
 }
 async function open(){
  if(!uuid.test(executionId.trim()))return;
  generation.current++;setExecution(null);invalidate();pinUrl(executionId.trim());
  if(pending.current?.executionId!==executionId.trim()){pending.current=null;setRetry(false)}
  await work(ticket=>refresh(executionId.trim(),ticket));
 }
 const runner=execution?.implementation==="p63-runner-v1",actionable=runner&&!execution?.cancel_requested&&!pending.current;
 const fields:[string,number,(v:number)=>void,number,number][]=[
  ["Số vòng tối đa",iterations,setIterations,1,20],["Ngân sách tối đa (microUSD)",budget,setBudget,0,1000000000],
  ["Trần mỗi vòng (microUSD)",ceiling,setCeiling,0,1000000000],["Thời gian mỗi vòng (giây)",duration,setDuration,1,120],
  ["Thời gian toàn phiên (giây)",elapsed,setElapsed,1,86400]];
 return <PaoAppShell pageTitle="Goal runner" pageSubtitle="P6.3 · Dry-run có approval; không gọi model hoặc công cụ thật."><div className="gr-workspace">
  <nav><Link href="/automation/review">← Kết quả &amp; duyệt</Link> · <Link href="/automation">Studio và kế hoạch</Link></nav>
  <p role="status" aria-label="Goal runner readiness">{enabled?"Runner được bật — chỉ fixed Echo dry-run":"Runner đang tắt. Có thể xem phiên cũ và yêu cầu hủy; không thể tạo hoặc duyệt vòng mới."}</p>
  <p>Không cần giữ tab mở để runner hoạt động. Hoàn tất Echo không tự hoàn thành Goal kinh doanh.</p>
  {error&&<p role="alert">{error}</p>}
  {retry&&<aside><p>Chưa xác nhận kết quả lệnh. Không gửi lại với khóa mới. Hãy cập nhật trạng thái hoặc thử lại đúng lệnh đã gửi.</p><button disabled={busy} onClick={()=>void work(ticket=>deliver(pending.current!,ticket))}>Thử lại cùng lệnh</button></aside>}
  <section aria-label="Mở Goal execution"><h2>Mở phiên đã lưu</h2><label>Execution ID <input aria-label="Goal execution ID" value={executionId} disabled={busy} onChange={e=>setExecutionId(e.target.value)}/></label>
   <button disabled={busy||!uuid.test(executionId.trim())} onClick={()=>void open()}>Mở phiên Goal</button>{execution&&<button disabled={busy} onClick={()=>void work(ticket=>refresh(execution.execution_id,ticket))}>Cập nhật Goal</button>}
  </section>
  {!execution&&<section><h2>Tạo phiên dry-run</h2><p>1. Chọn Goal. 2. Nhập mã kế hoạch đã lưu từ Studio. 3. Xem trước và xác nhận. Đây chưa phải duyệt thực thi.</p>
   <label>Goal <select aria-label="Goal" value={goalId} disabled={busy||retry} onChange={e=>{setGoalId(e.target.value);invalidate()}}><option value="">Chọn Goal</option>{goals.map(g=><option key={g.id} value={g.id}>{g.title} · v{g.version}</option>)}</select></label>
   <label>Plan ID <input aria-label="Goal plan ID" value={planId} disabled={busy||retry} onChange={e=>{setPlanId(e.target.value);invalidate()}}/></label>
   <div className="gr-fields">{fields.map(([name,value,setter,min,max])=><label key={name}>{name}<input aria-label={name} type="number" min={min} max={max} step="1" value={value} disabled={busy||retry} onChange={e=>{setter(Number(e.target.value));invalidate()}}/></label>)}</div>
   <p>1 USD = 1.000.000 microUSD. Echo có chi phí thực tế bằng 0; trần là khoản giữ chỗ an toàn.</p>
   <label>Tiêu chí dry-run <select aria-label="Tiêu chí dry-run" value={rule} disabled={busy||retry} onChange={e=>{setRule(e.target.value);invalidate()}}><option value="non_empty">Text không rỗng</option><option value="equals">Text khớp chính xác</option></select></label>
   {rule==="equals"&&<label>Text đích <input aria-label="Text đích" maxLength={4096} value={target} disabled={busy||retry} onChange={e=>{setTarget(e.target.value);invalidate()}}/></label>}
   <button disabled={busy||retry||!enabled||!goalId||!uuid.test(planId.trim())} onClick={()=>void review()}>Xem trước Goal dry-run</button>
   {preview&&<><pre aria-label="Goal admission preview">{JSON.stringify(preview,null,2)}</pre><label><input type="checkbox" checked={ack} disabled={busy||retry} onChange={e=>setAck(e.target.checked)}/>Tôi xác nhận fixed Echo, giới hạn và kế hoạch đã ghim; mỗi vòng vẫn phải duyệt.</label><button disabled={busy||retry||!ack||!enabled} onClick={()=>void admit()}>Tạo Goal dry-run</button></>}
  </section>}
  {execution&&<section aria-label="Goal execution"><h2>Phiên Goal dry-run</h2>
   <p aria-label="Goal execution status">{execution.status} · vòng {execution.state.iteration||0} · version {execution.version} · sequence {execution.sequence}</p>
   <p>Mã: {execution.execution_id} · Goal: {execution.goal_id}</p><p aria-label="Goal reservation">Giữ chỗ: {execution.reserved_cost_microusd} microUSD · Đã dùng: {execution.state.cost_microusd||0} microUSD</p>
   <p>Lý do: {execution.state.reason||"—"}. {execution.cancel_requested?"Đã yêu cầu hủy, chờ xác minh dừng bền vững.":""}</p>
   {!runner&&<p>Phiên legacy: chỉ xem hoặc hủy. Không tự nâng cấp sang runner mới.</p>}
   {execution.state.receipt_hash&&<p>Receipt đã ghim: {execution.state.receipt_hash}</p>}
   {execution.state.checks?.map((c,i)=><p key={i}>{c.field}/{c.rule}: {c.passed?"đạt":"chưa đạt"}</p>)}
   {execution.status==="completed"&&<p>Đạt tiêu chí fixed Echo. Không phải bằng chứng hoàn thành nghiệp vụ.</p>}
   {execution.status==="manual_review"&&<p>Kết quả chưa rõ. Không tự retry hoặc giải phóng ngân sách; cần kiểm tra ledger.</p>}
   {actionable&&execution.status==="waiting_approval"&&<><pre aria-label="Goal proposal">{JSON.stringify(execution.state.proposal,null,2)}</pre><button disabled={busy||!enabled} onClick={()=>void decision("approve")}>Duyệt vòng Goal</button><button disabled={busy||!enabled} onClick={()=>void decision("reject")}>Từ chối vòng Goal</button></>}
   {actionable&&execution.status==="waiting_replan"&&<><p>Vòng trước chưa đạt. Cần kế hoạch mới và approval mới; không chạy lại kế hoạch cũ.</p><label>Plan ID mới <input aria-label="Goal replan ID" value={replanId} disabled={busy} onChange={e=>setReplanId(e.target.value)}/></label><button disabled={busy||!enabled||!uuid.test(replanId.trim())} onClick={()=>void replan()}>Gửi kế hoạch mới, chưa duyệt</button></>}
   {(!terminal.has(execution.status)||execution.reserved_cost_microusd>0)&&!execution.cancel_requested&&<button disabled={busy} onClick={()=>void cancel()}>Yêu cầu hủy Goal</button>}
   <details><summary>Lệnh giao nhận và audit</summary><pre>{JSON.stringify({commands:execution.commands,events:execution.events},null,2)}</pre></details>
  </section>}
  {runner&&execution?.status==="running"&&execution.state.proposal&&workspace&&<WorkflowRunPanel key={execution.state.proposal.plan_id} workspace={workspace} initialPlanId={execution.state.proposal.plan_id} parentOwned/>}
 </div></PaoAppShell>;
}
