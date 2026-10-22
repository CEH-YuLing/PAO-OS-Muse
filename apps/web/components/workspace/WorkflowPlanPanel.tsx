"use client";
import {useEffect,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
type Snapshot={sha256:string;steps:{step_id:string;depends_on:string[];model:{provider:string;model:string}}[];execution_enabled:boolean};
export default function WorkflowPlanPanel({definitionId,versionId,workspace}:{definitionId:string;versionId:string;workspace:string}){
 const {api}=usePao();const [enabled,setEnabled]=useState(false),[input,setInput]=useState('{"text":"Dữ liệu thử local"}'),[preview,setPreview]=useState<Snapshot|null>(null),[key,setKey]=useState(""),[ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[result,setResult]=useState("");
 useEffect(()=>{let alive=true;api<{enabled:boolean}>(`/v1/studio/planning/status?workspace_id=${workspace}`).then(v=>{if(alive)setEnabled(v.enabled)}).catch(()=>{if(alive)setEnabled(false)});return()=>{alive=false}},[api,workspace]);
 useEffect(()=>{setPreview(null);setKey("");setAck(false);setResult("");setError("")},[definitionId,versionId]);
 async function review(){setBusy(true);setError("");setAck(false);setPreview(null);try{const requestKey=crypto.randomUUID();const value=await api<Snapshot>(`/v1/studio/definitions/${definitionId}/plan-preview`,"POST",{version_id:versionId,request_key:requestKey,input:JSON.parse(input)});setKey(requestKey);setPreview(value)}catch(reason){setError((reason as Error).message)}finally{setBusy(false)}}
 async function save(){if(!preview||!ack)return;setBusy(true);setError("");try{const value=await api<{plan_id:string;task_ids:string[]}>(`/v1/studio/definitions/${definitionId}/plans`,"POST",{version_id:versionId,request_key:key,input:JSON.parse(input),confirmation_hash:preview.sha256});setResult(`Đã lưu kế hoạch ${value.plan_id}: ${value.task_ids.length} task nháp, chưa chạy.`);setAck(false)}catch(reason){setError((reason as Error).message);setPreview(null);setAck(false)}finally{setBusy(false)}}
 if(!enabled)return null;
 return <section aria-label="P6.1 workflow planning" style={{border:"1px solid #385363",borderRadius:12,padding:16,marginTop:16}}>
  <h3>P6.1 — Lập kế hoạch workflow, không chạy</h3><p>Chỉ phiên bản publish/review. Tạo task nháp và snapshot bất biến; không gọi model, Ads hay scheduler.</p>
  <label>Workflow input JSON<textarea aria-label="Workflow plan input" value={input} rows={4} style={{width:"100%"}} onChange={e=>{setInput(e.target.value);setPreview(null);setAck(false);setResult("")}} disabled={busy}/></label>
  <button disabled={busy} onClick={()=>void review()}>Kiểm tra và xem kế hoạch</button>
  {error&&<p role="alert">{error}</p>}
  {preview&&<><ol>{preview.steps.map(step=><li key={step.step_id}>{step.step_id} — phụ thuộc: {step.depends_on.join(", ")||"không"} — {step.model.provider}/{step.model.model}</li>)}</ol><p>Hash: {preview.sha256}</p>
   <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} disabled={busy}/>Tôi đồng ý tạo task nháp; chưa cho phép thực thi.</label>
   <button disabled={busy||!ack} onClick={()=>void save()}>Lưu kế hoạch task nháp</button></>}
  {result&&<p role="status">{result}</p>}
 </section>
}
