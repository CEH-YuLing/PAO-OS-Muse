"use client";
import {useEffect,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import ChatControlPopover from './ChatControlPopover';
type Policy={token_mode?:'provider'|'bounded';privacy:"local_only"|"cloud_allowed";cloud_references:boolean;context_tokens:number;max_bytes:number;max_output_tokens:number;max_run_tokens:number;max_calls:number;require_reported_usage:boolean;version?:string;pricing?:{input_per_million:string;output_per_million:string;version:string}|null};
type Profile={available:boolean;version:number;pinned:boolean;group:string;policy:Policy};
export default function ChatManagement({onBusy,placement='inline'}:{onBusy:(value:boolean)=>void;placement?:'inline'|'header'}){
  const runtime=usePao(),[profile,setProfile]=useState<Profile|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[result,setResult]=useState(""),[query,setQuery]=useState(""),[rows,setRows]=useState<{id:string;title:string;pinned:boolean;group:string}[]>([]);
  const base=`/v1/sessions/${runtime.sessionId}`,workspace=runtime.activeWorkspace?.id,runId=runtime.runId||runtime.messages.at(-1)?.run_id;
  useEffect(()=>{let live=true;setProfile(null);if(runtime.sessionId)void runtime.api<Profile>(`${base}/chat`).then(value=>{if(live)setProfile(value)}).catch(()=>{});return()=>{live=false}},[base,runtime.api,runtime.sessionId]);
  useEffect(()=>()=>onBusy(false),[onBusy]);
  async function act(action:()=>Promise<void>){setBusy(true);onBusy(true);setError("");try{await action()}catch(reason){setError((reason as Error).message)}finally{setBusy(false);onBusy(false)}}
  async function download(){await runtime.download(`${base}/export`,`pao-${runtime.sessionId}.md`)}
  async function save(){if(!profile)return;const {version:_,pricing:price,...policy}=profile.policy;const pricing=price?{input_per_million:price.input_per_million,output_per_million:price.output_per_million,version:price.version}:null;try{setProfile(await runtime.api<Profile>(`${base}/chat`,"PUT",{version:profile.version,pinned:profile.pinned,group:profile.group,policy:{...policy,token_mode:'provider'},pricing}));window.dispatchEvent(new Event("pao:chat-config"))}catch(reason){setProfile(await runtime.api<Profile>(`${base}/chat`));throw reason}}
  function change(key:keyof Policy,value:Policy[keyof Policy]){if(profile)setProfile({...profile,policy:{...profile.policy,[key]:value}})}
  if(!profile?.available)return null;
  const locked=busy||runtime.active;
  const content=<>
    <label><input aria-label="Ghim hội thoại" type="checkbox" checked={profile.pinned} disabled={locked} onChange={e=>setProfile({...profile,pinned:e.target.checked})}/>Ghim hội thoại</label>
    <label>Nhóm<input aria-label="Nhóm hội thoại" value={profile.group} maxLength={60} disabled={locked} onChange={e=>setProfile({...profile,group:e.target.value})}/></label>
    <label><input aria-label="Cho phép cloud" type="checkbox" checked={profile.policy.privacy==="cloud_allowed"} disabled={locked} onChange={e=>change("privacy",e.target.checked?"cloud_allowed":"local_only")}/>Cho phép gửi yêu cầu mới tới cloud đã cấu hình</label>
    <label><input aria-label="Cho phép tham chiếu cloud" type="checkbox" checked={profile.policy.cloud_references} disabled={locked||profile.policy.privacy!=="cloud_allowed"} onChange={e=>change("cloud_references",e.target.checked)}/>Cho phép tham chiếu của các run đã cấp quyền cloud</label>
    <p>Memory, Knowledge và lịch sử local cũ không được tự gửi cloud. Không tự fallback.</p>
    <p role="note">Ngữ cảnh, đầu ra và token suy luận theo khả năng của mô hình. PAO không áp trần token riêng cho lượt mới. Nhà cung cấp vẫn có giới hạn và hạn mức; dữ liệu quá lớn cần chia nhỏ. Lượt cũ giữ nguyên cấu hình đã ghim.</p>
    <label>Số lần gọi tối đa để tránh vòng lặp<input aria-label="Số lần gọi tối đa" type="number" min={1} max={16} value={profile.policy.max_calls} disabled={locked} onChange={e=>change('max_calls',Number(e.target.value))}/></label>
    <label><input aria-label="Bắt buộc usage reported" type="checkbox" checked={profile.policy.require_reported_usage} disabled={locked} onChange={e=>change("require_reported_usage",e.target.checked)}/>Bắt buộc usage reported (planner chưa báo sẽ bị chặn)</label>
    <button type="button" disabled={locked} onClick={()=>void act(save)}>Lưu cấu hình chat</button>
    <label>Tìm toàn văn<input aria-label="Tìm hội thoại" value={query} onChange={e=>setQuery(e.target.value)} maxLength={120}/></label>
    <button type="button" disabled={busy} onClick={()=>void act(async()=>setRows(await runtime.api(`/v1/chat/sessions?workspace_id=${workspace}&q=${encodeURIComponent(query)}`)))}>Tìm hội thoại</button>
    {rows.map(row=><button key={row.id} type="button" disabled={runtime.active||busy} onClick={()=>void runtime.selectSession(row.id)}>{row.pinned?"★ ":""}{row.group} · {row.title}</button>)}
    <button type="button" disabled={busy} onClick={()=>void act(download)}>Xuất Markdown</button>
    <button type="button" disabled={locked} onClick={()=>void act(async()=>setResult(JSON.stringify(await runtime.api(`${base}/compactions`,"POST"),null,2)))}>Compact hội thoại</button>
    <button type="button" disabled={busy} onClick={()=>void act(async()=>setResult(JSON.stringify(await runtime.api(`${base}/compactions`),null,2)))}>Xem phiên bản compact</button>
    <button type="button" disabled={busy} onClick={()=>void act(async()=>setResult(JSON.stringify(await runtime.api(`/v1/chat/usage?workspace_id=${workspace}`),null,2)))}>Xem usage</button>
    {runId&&<><button type="button" disabled={busy} onClick={()=>void act(async()=>setResult(JSON.stringify(await runtime.api(`/v1/runs/${runId}/context`),null,2)))}>Xem context trace</button><button type="button" disabled={locked} onClick={()=>void act(async()=>{await runtime.api(`/v1/runs/${runId}/retry`,"POST",{request_key:crypto.randomUUID()});await runtime.selectSession(runtime.sessionId!)})}>Thử lại bằng run mới</button></>}
    <p>Token estimated không phải reported. Thiếu usage/giá là chưa biết, không phải 0. Chi phí nếu có chỉ là ước tính; không phải hóa đơn hay quota thuê bao.</p>
    {result&&<pre style={{maxHeight:200,overflow:"auto",whiteSpace:"pre-wrap"}} aria-label="Kết quả quản lý chat">{result}</pre>}{error&&<p role="alert">{error}</p>}
  </>;
  return placement==='header'?<ChatControlPopover label="Hội thoại và quyền riêng tư" title="Hội thoại, quyền riêng tư và thống kê">{content}</ChatControlPopover>:<details className="pao-engine-picker" aria-label="Quản lý hội thoại P3"><summary>Hội thoại · quyền riêng tư và usage</summary>{content}</details>;
}
