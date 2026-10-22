"use client";
import {useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";

type Run={execution_id:string;workspace_id:string;status:string;version:number;sequence:number;cancel_requested:boolean;state:{current_step?:string;completed_steps?:string[];reason?:string};commands:{id:string;operation:string;status:string;error_code?:string}[]};
type Gates={admission_enabled:boolean;dispatch_enabled:boolean;arq_bridge_ready:boolean;dry_run_only:boolean};
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export default function WorkflowRunPanel({workspace,initialPlanId,parentOwned=false}:{workspace:string;initialPlanId?:string;parentOwned?:boolean}){
 const {api}=usePao();
 const [id,setId]=useState(""),[plan,setPlan]=useState<{plan_id:string;snapshot:{sha256:string;workspace_id:string}}|null>(null),[run,setRun]=useState<Run|null>(null),[gates,setGates]=useState<Gates|null>(null);
 const [busy,setBusy]=useState(false),[ack,setAck]=useState(false),[error,setError]=useState("");
 const generation=useRef(0),pending=useRef<{operation:string;path:string;body:unknown}|null>(null);
 useEffect(()=>{generation.current++;setPlan(null);setRun(null);setGates(null);setAck(false);pending.current=null;setBusy(false);setError("")},[workspace]);
 async function refresh(planId=plan?.plan_id){
  const current=generation.current;
  const status=await api<Gates>(`/v1/studio/durable/status?workspace_id=${workspace}`);
  if(current!==generation.current)return;
  setGates(status);
  if(planId){try{const value=await api<Run>(`/v1/studio/executions/${planId}`);if(current===generation.current&&value.workspace_id===workspace)setRun(value)}catch(reason){if(!String((reason as Error).message).includes("durable_execution_not_found"))throw reason; if(current===generation.current)setRun(null)}}
 }
 useEffect(()=>{let alive=true;const timer=setInterval(()=>{if(alive&&!busy&&plan)void refresh().catch(reason=>{if(alive)setError((reason as Error).message)})},2000);return()=>{alive=false;clearInterval(timer)}},[plan,busy,api,workspace]);
 async function load(planId=id.trim()){if(busy||!uuid.test(planId))return;const current=++generation.current;setBusy(true);setError("");setPlan(null);setRun(null);setAck(false);pending.current=null;
  try{const value=await api<{plan_id:string;snapshot:{sha256:string;workspace_id:string}}>(`/v1/studio/plans/${planId}`);if(current!==generation.current)return;if(value.snapshot.workspace_id!==workspace)throw new Error("Kế hoạch không thuộc workspace đang mở.");setPlan(value);await refresh(value.plan_id)}catch(reason){if(current===generation.current)setError((reason as Error).message)}finally{if(current===generation.current)setBusy(false)}
 }
 // Embedded child review never starts a standalone execution.
 useEffect(()=>{if(initialPlanId){setId(initialPlanId);void load(initialPlanId)}},[initialPlanId,workspace]); // eslint-disable-line react-hooks/exhaustive-deps
 async function send(operation:string){if(!plan||busy)return;const current=generation.current;setBusy(true);setError("");
  try{
   if(pending.current&&pending.current.operation!==operation)throw new Error("Hãy thử lại lệnh trước để xác định kết quả; không gửi quyết định khác khi chưa rõ.");
   if(!pending.current){const key=crypto.randomUUID();let path=`/v1/studio/executions/${plan.plan_id}/cancel`,body:unknown={request_key:key};
    if(operation==="start"){path=`/v1/studio/plans/${plan.plan_id}/execution`;body={request_key:key,confirmation_hash:plan.snapshot.sha256}}
    else if(operation!=="cancel"){if(!run?.state.current_step)throw new Error("Chưa có bước đang chờ duyệt.");path=`/v1/studio/executions/${plan.plan_id}/decision`;body={request_key:key,version:run.version,step_id:run.state.current_step,decision:operation}}
    pending.current={operation,path,body};
   }
   const command=pending.current;await api(command.path,"POST",command.body);if(current!==generation.current)return;pending.current=null;setAck(false);await refresh();
  }catch(reason){if(current===generation.current)setError((reason as Error).message)}finally{if(current===generation.current)setBusy(false)}
 }
 const ready=gates?.admission_enabled&&gates?.dispatch_enabled&&gates?.arq_bridge_ready;
 const terminal=run&&["completed","cancelled","manual_review"].includes(run.status);
 return <section aria-label="P6.2 workflow runner" style={{border:"1px solid #385363",borderRadius:12,padding:16,marginTop:16}}>
  <h3>P6.2 — Chạy thử workflow có kiểm soát</h3><p>Chỉ echo giả lập: không gọi model, Ads hay công cụ bên ngoài. Task kế hoạch vẫn là nháp.</p>
  <label>Plan ID đã lưu <input aria-label="Workflow runner plan ID" value={id} disabled={busy||parentOwned} onChange={e=>{generation.current++;setId(e.target.value);setPlan(null);setRun(null);pending.current=null;setAck(false)}}/></label>
  <button disabled={busy||!uuid.test(id.trim())} onClick={()=>void load()}>Mở kế hoạch chạy thử</button>
  {error&&<p role="alert">{error}</p>}
  {plan&&<><p aria-label="Workflow runner readiness">{ready?"Worker sẵn sàng — chỉ chạy giả lập":"Runner đang tắt hoặc worker chưa sẵn sàng"}</p><p style={{overflowWrap:"anywhere"}}>Snapshot: {plan.snapshot.sha256}</p>
   {!run&&parentOwned&&<p>Child do Goal runner khởi động. Không tạo standalone execution từ giao diện này.</p>}
   {!run&&!parentOwned&&<><label><input type="checkbox" checked={ack} disabled={busy} onChange={e=>setAck(e.target.checked)}/>Tôi xác nhận chỉ chạy giả lập, không gọi model hay Ads.</label><button disabled={busy||!ready||!ack} onClick={()=>void send("start")}>Bắt đầu chạy giả lập</button></>}
   <button disabled={busy} onClick={()=>void refresh().catch(reason=>setError((reason as Error).message))}>Cập nhật trạng thái</button>
   {run&&<><p role="status" aria-label="Workflow execution status">{run.status} · bước {run.state.current_step||"—"} · sequence {run.sequence}</p>
    <p>Đã xong: {run.state.completed_steps?.join(", ")||"chưa có"}. {run.cancel_requested?"Đã yêu cầu hủy; chờ xác nhận bền vững.":""}</p>
    {run.status==="waiting_approval"&&!run.cancel_requested&&<><button disabled={busy||!ready} onClick={()=>void send("approve")}>Duyệt bước hiện tại</button><button disabled={busy||!ready} onClick={()=>void send("reject")}>Từ chối bước hiện tại</button></>}
    {!terminal&&<button disabled={busy||run.cancel_requested} onClick={()=>void send("cancel")}>Yêu cầu hủy workflow</button>}
    {run.status==="manual_review"&&<p>Không tự chạy lại kết quả không rõ. Cần kiểm tra ledger trước khi xử lý tiếp.</p>}
    <details><summary>Lệnh và kết quả giao nhận</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(run.commands,null,2)}</pre></details>
   </>}
  </>}
 </section>
}
