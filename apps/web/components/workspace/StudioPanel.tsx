"use client";
import {useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import WorkflowPlanPanel from "./WorkflowPlanPanel";
import WorkflowRunPanel from "./WorkflowRunPanel";
import "./organization.css";
const kindLabels={agents:"Trợ lý chuyên môn",skills:"Kỹ năng",workflows:"Quy trình"};
const actionLabels:Record<string,string>={validate:"Kiểm tra",review:"Duyệt",publish:"Công bố",rollback:"Khôi phục phiên bản"};

type Kind="agents"|"skills"|"workflows";
type Definition={id:string;kind:Kind;slug:string;name:string;revision:number;seed:boolean;archived:boolean;published_version_id:string|null};
type Version={id:string;ordinal:number;status:string;hash:string;payload:Record<string,unknown>};
type Detail={definition:Definition;versions:Version[];events:unknown[]};
const objectSchema={type:"object",properties:{text:{type:"string",maxLength:80}},required:["text"],additionalProperties:false};
function template(kind:Kind){
  if(kind==="agents")return {instruction:"Viết câu trả lời ngắn gọn, nêu rõ khi thiếu dữ liệu.",model_preference:null,brain_id:null};
  if(kind==="skills")return {mode:"llm_text",instruction:"Trả về JSON chứa text dựa trên dữ liệu đầu vào.",agent_version_id:"UUID phiên bản agent đã công bố",input_schema:objectSchema,output_schema:objectSchema,allowed_tools:[],timeout_seconds:45,token_budget:4096,output_tokens:256,generation_cap:1,exit_criteria:[]};
  return {input_schema:objectSchema,output_schema:objectSchema,steps:[{id:"first",skill_version_id:"UUID phiên bản skill đã công bố",depends_on:[],inputs:{text:{source:"workflow",field:"text"}}}],outputs:{text:{source:"step",step:"first",field:"text"}}};
}
export default function StudioPanel(){
  const runtime=usePao();const workspace=runtime.activeWorkspace?.id;
  const [kind,setKind]=useState<Kind>("agents"),[rows,setRows]=useState<Definition[]>([]),[detail,setDetail]=useState<Detail|null>(null);
  const [editor,setEditor]=useState(JSON.stringify(template("agents"),null,2)),[slug,setSlug]=useState(""),[name,setName]=useState("");
  const [selected,setSelected]=useState(""),[ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[result,setResult]=useState("");
  const [fixture,setFixture]=useState(JSON.stringify({input:{text:"Dữ liệu thử"},expected_output:{text:"Dữ liệu thử"}},null,2));
  const [portable,setPortable]=useState(""),[confirmation,setConfirmation]=useState("");
  const generation=useRef(0);
  async function load(){if(!workspace)return;const current=generation.current;const data=await runtime.api<{definitions:Definition[]}>(`/v1/studio/definitions?workspace_id=${workspace}&kind=${kind}`);if(current===generation.current)setRows(data.definitions)}
  useEffect(()=>{generation.current++;setDetail(null);setSelected("");setRows([]);setError("");setEditor(JSON.stringify(template(kind),null,2));setConfirmation("");
    const current=generation.current; if(workspace)runtime.api<{definitions:Definition[]}>(`/v1/studio/definitions?workspace_id=${workspace}&kind=${kind}`).then(data=>{if(current===generation.current)setRows(data.definitions)}).catch(reason=>{if(current===generation.current)setError((reason as Error).message)});
    return()=>{generation.current++}
  },[workspace,kind,runtime.api]);
  async function work(task:()=>Promise<void>){if(busy)return;setBusy(true);setError("");const current=generation.current;try{await task()}catch(reason){if(current===generation.current)setError((reason as Error).message)}finally{if(current===generation.current)setBusy(false)}}
  async function open(id:string){const current=generation.current;const value=await runtime.api<Detail>(`/v1/studio/definitions/${id}`);if(current!==generation.current)return;setDetail(value);setSelected(value.versions[0]?.id||"");let payload=value.versions[0]?.payload||{};if(value.definition.seed){payload=template(value.definition.kind);if(value.definition.kind==="agents"){const config=value.versions[0]?.payload.config as {instruction?:string}|undefined;payload={instruction:config?.instruction||"Viết câu trả lời dựa trên dữ liệu."}}}setEditor(JSON.stringify(payload,null,2));setSlug(value.definition.slug+"-copy");setName(value.definition.name+" (bản sao)");setAck(false)}
  async function save(clone=false){if(!workspace)return;const payload=JSON.parse(editor);let path="/v1/studio/definitions";let body:unknown={workspace_id:workspace,kind,slug,name,payload};
    if(detail&&!clone){path=`/v1/studio/definitions/${detail.definition.id}/versions`;body={revision:detail.definition.revision,payload}}
    else if(detail&&clone)path=`/v1/studio/definitions/${detail.definition.id}/clone`;
    const value=await runtime.api<{definition:Definition}>(path,"POST",body);await load();await open(value.definition.id)
  }
  async function action(action:string){if(!detail||!selected)return;await runtime.api(`/v1/studio/definitions/${detail.definition.id}/versions/${selected}/actions/${action}`,"POST",{revision:detail.definition.revision,self_review:ack});await open(detail.definition.id);await load()}
  const version=detail?.versions.find(row=>row.id===selected);
  return <section aria-label="Agent Skill Workflow Studio" style={{padding:20,border:"1px solid var(--pao-border,#333)",borderRadius:12,marginBottom:20}}>
    <h2>Quản lý phiên bản nâng cao</h2>
    <p>Phiên bản bất biến, duyệt trước khi công bố. Không cấp quyền công cụ. Quy trình mô phỏng chỉ lặp lại dữ liệu khi worker được cấu hình; không gọi mô hình. Điều kiện kết thúc: non_empty:text (text không rỗng) hoặc equals_input:text (text bằng đầu vào).</p>
    {workspace&&<WorkflowRunPanel key={workspace} workspace={workspace}/>}
    <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>{(["agents","skills","workflows"] as Kind[]).map(value=><button key={value} disabled={busy} onClick={()=>setKind(value)} aria-pressed={kind===value}>{kindLabels[value]}</button>)}
      <button disabled={busy||!workspace} onClick={()=>work(async()=>{setResult(JSON.stringify(await runtime.api("/v1/studio/bootstrap","POST",{workspace_id:workspace})));await load()})}>Nhập mẫu hệ thống (chỉ đọc)</button>
      <button disabled={busy} onClick={()=>{setDetail(null);setSelected("");setSlug("");setName("");setEditor(JSON.stringify(template(kind),null,2))}}>Soạn bản nháp mới</button>
    </div>
    {error&&<p role="alert">{error}</p>}
    <div className="studio-editor-grid" style={{display:"grid",gridTemplateColumns:"minmax(150px,1fr) minmax(0,3fr)",gap:16,marginTop:16}}>
      <nav aria-label="Studio definitions">{rows.map(row=><button key={row.id} style={{display:"block",marginBottom:8}} disabled={busy} onClick={()=>work(()=>open(row.id))}>{row.name} {row.seed?"[mẫu hệ thống]":row.archived?"[đã lưu trữ]":row.published_version_id?"[đã công bố]":"[bản nháp]"}</button>)}</nav>
      <div><label>Mã gọi <input value={slug} onChange={e=>{setSlug(e.target.value);setConfirmation("")}} /></label> <label>Tên hiển thị <input value={name} onChange={e=>{setName(e.target.value);setConfirmation("")}} /></label>
        <label style={{display:"block"}}>Nội dung định nghĩa (JSON)<textarea aria-label="Studio definition JSON" rows={16} value={editor} onChange={e=>{setEditor(e.target.value);setConfirmation("")}} style={{width:"100%",fontFamily:"monospace"}} /></label>
        <button disabled={busy||detail?.definition.seed||detail?.definition.archived} onClick={()=>work(()=>save())}>{detail?"Lưu phiên bản mới":"Tạo bản nháp"}</button>
        {detail&&<button disabled={busy} onClick={()=>work(()=>save(true))}>Sao chép thành bản nháp</button>}
        {detail&&<><p>Phiên bản quản lý {detail.definition.revision} · {detail.definition.id}</p>
          <label>Các phiên bản <select aria-label="Versions" value={selected} onChange={e=>{setSelected(e.target.value);const v=detail.versions.find(row=>row.id===e.target.value);if(v)setEditor(JSON.stringify(v.payload,null,2));setAck(false)}}>{detail.versions.map(row=><option key={row.id} value={row.id}>v{row.ordinal} — {row.status}</option>)}</select></label>
          <p style={{overflowWrap:"anywhere"}}>Mã phiên bản: {selected}<br/>Mã kiểm chứng: {version?.hash}</p>
          <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} /> Tôi xác nhận tự duyệt; đây không phải kiểm tra bởi người thứ hai.</label>
          <div>{["validate","review","publish","rollback"].map(value=><button key={value} disabled={busy||detail.definition.seed||detail.definition.archived} onClick={()=>work(()=>action(value))}>{actionLabels[value]}</button>)}
            <button disabled={busy||detail.definition.seed} onClick={()=>work(async()=>{await runtime.api(`/v1/studio/definitions/${detail.definition.id}/archive`,"POST",{revision:detail.definition.revision});await open(detail.definition.id);await load()})}>Lưu trữ (giữ lịch sử)</button>
          </div>
          {kind==="skills"&&!detail.definition.seed&&<p>Lệnh chat: /{detail.definition.slug} {`{"text":"Dữ liệu thử"}`}. Chỉ phiên bản đã công bố được gọi.</p>}
          {kind!=="agents"&&!detail.definition.seed&&<><label>Dữ liệu mẫu (JSON)<textarea rows={4} value={fixture} onChange={e=>setFixture(e.target.value)} style={{width:"100%"}} /></label><button disabled={busy} onClick={()=>work(async()=>setResult(JSON.stringify(await runtime.api(`/v1/studio/definitions/${detail.definition.id}/versions/${selected}/fixture`,"POST",JSON.parse(fixture)),null,2)))}>Kiểm tra lược đồ — không gọi mô hình</button></>}
          <button disabled={busy||detail.definition.seed} onClick={()=>work(async()=>{const data=await runtime.api(`/v1/studio/definitions/${detail.definition.id}/export`);setPortable(JSON.stringify(data,null,2));setConfirmation("")})}>Xuất JSON</button>
          {kind==="workflows"&&version?.status==="published"&&workspace&&<WorkflowPlanPanel key={`${detail.definition.id}:${selected}`} definitionId={detail.definition.id} versionId={selected} workspace={workspace}/>}
          <details><summary>Nhật ký thay đổi</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(detail.events,null,2)}</pre></details>
        </>}
        <label style={{display:"block"}}>Nhập / Xuất JSON<textarea aria-label="Studio import JSON" rows={5} value={portable} onChange={e=>{setPortable(e.target.value);setConfirmation("")}} style={{width:"100%"}} /></label>
        <button disabled={busy||!portable} onClick={()=>work(async()=>{const data=JSON.parse(portable);data.definition.workspace_id=workspace;const preview=await runtime.api<{confirmation_hash:string}>("/v1/studio/import","POST",{definition:data.definition});setConfirmation(preview.confirmation_hash);setResult(JSON.stringify(preview,null,2))})}>Xem trước dữ liệu nhập</button>
        <button disabled={busy||!confirmation} onClick={()=>work(async()=>{const data=JSON.parse(portable);data.definition.workspace_id=workspace;const imported=await runtime.api<{definition:Definition}>("/v1/studio/import","POST",{definition:data.definition,confirmation_hash:confirmation});setConfirmation("");await load();await open(imported.definition.id)})}>Xác nhận nhập thành bản nháp</button>
        {result&&<pre aria-label="Studio test result" style={{whiteSpace:"pre-wrap"}}>{result}</pre>}
      </div>
    </div>
  </section>
}
