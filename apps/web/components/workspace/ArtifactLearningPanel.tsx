"use client";
import {useEffect,useMemo,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import "./goal-runner.css";
type Named={id:string;name:string};
type Proposal={id:string;candidate:string;fingerprint:string;source_id:string;source_hash:string;status:string;derivation:string;segments:unknown[];note_id:string|null};
type Input={source_id:string;derivation:string;candidate:string|null;segments:{start:number;end:number}[]};
export default function ArtifactLearningPanel(){
 const {api,me,activeWorkspace}=usePao(),workspace=activeWorkspace?.id;
 const [brains,setBrains]=useState<Named[]>([]),[files,setFiles]=useState<Named[]>([]),[brain,setBrain]=useState(""),[file,setFile]=useState("");
 const [text,setText]=useState(""),[candidate,setCandidate]=useState(""),[mode,setMode]=useState("quote"),[chosen,setChosen]=useState<number[]>([]);
 const [rows,setRows]=useState<Proposal[]>([]),[preview,setPreview]=useState<{input:Input;hash:string;value:unknown}|null>(null),[ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
 const generation=useRef(0),lock=useRef(false);
 function invalidate(){setPreview(null);setAck(false)}
 useEffect(()=>{const ticket=++generation.current;setBrains([]);setBrain("");setFiles([]);setFile("");setRows([]);setText("");setCandidate("");setChosen([]);invalidate();setError("");
  if(workspace)void api<Named[]>(`/v1/brains?workspace_id=${workspace}`).then(v=>{if(ticket===generation.current)setBrains(v)}).catch(e=>{if(ticket===generation.current)setError((e as Error).message)});
  return()=>{generation.current++};
 },[api,workspace]);
 async function work(fn:(ticket:number)=>Promise<void>){if(lock.current)return;lock.current=true;setBusy(true);setError("");const ticket=generation.current;
  try{await fn(ticket)}catch(e){if(ticket===generation.current)setError((e as Error).message)}finally{lock.current=false;setBusy(false)}
 }
 async function selectBrain(id:string){generation.current++;setBrain(id);setFiles([]);setFile("");setRows([]);setText("");setCandidate("");setChosen([]);invalidate();if(!id)return;
  await work(async ticket=>{const list=await api<Named[]>(`/v1/brains/${id}/files`);if(ticket===generation.current)setFiles(list);
   const proposals=await api<Proposal[]>(`/v1/learning/brains/${id}/artifact-proposals`);if(ticket===generation.current)setRows(proposals)});
 }
 async function selectFile(id:string){generation.current++;setFile(id);setText("");setCandidate("");setChosen([]);invalidate();if(!id)return;
  await work(async ticket=>{const value=await api<{content:string}>(`/v1/brains/${brain}/files/${id}/preview`);if(ticket===generation.current)setText(value.content)});
 }
 const parts=useMemo(()=>{let start=0;return text.split('\n').map((value,index)=>{const end=start+Array.from(value).length;const part={value,index,start,end};start=end+1;return part}).filter(p=>p.value.trim())},[text]);
 async function review(){invalidate();await work(async ticket=>{
  const input:Input={source_id:file,derivation:mode,candidate:mode==="quote"?candidate:null,segments:mode==="quote"?[]:parts.filter(p=>chosen.includes(p.index)).map(p=>({start:p.start,end:p.end}))};
  const value=await api<{confirmation_hash:string}>(`/v1/learning/brains/${brain}/artifact-preview`,"POST",input);if(ticket===generation.current)setPreview({input,hash:value.confirmation_hash,value});
 })}
 async function save(){if(!preview||!ack)return;const frozen=preview;await work(async ticket=>{
  const row=await api<Proposal>(`/v1/learning/brains/${brain}/artifact-proposals`,"POST",{...frozen.input,confirmation_hash:frozen.hash});if(ticket===generation.current){setRows(old=>[row,...old.filter(r=>r.id!==row.id)]);invalidate()}
 })}
 async function decide(row:Proposal,decision:string){
  if(!window.confirm(decision==="promote"?"Lưu đề xuất đã kiểm tra thành note dữ liệu? Không sửa policy/code/skill.":decision==="revert"?"Thu hồi note tạo từ đề xuất? Note đã sửa sẽ không bị ghi đè.":"Từ chối đề xuất này?"))return;
  await work(async ticket=>{const value=await api<Proposal>(`/v1/learning/artifact-proposals/${row.id}/review`,"POST",{fingerprint:row.fingerprint,decision});if(ticket===generation.current)setRows(old=>old.map(r=>r.id===value.id?value:r))});
 }
 return <div className="gr-workspace"><section aria-label="Artifact learning"><h2>Học từ tài liệu có duyệt</h2>
  <p>Chỉ .txt/.md trong Brain có quyền truy cập. Trích nguyên văn hoặc ghép các dòng đã chọn thành tóm tắt có nguồn; chưa suy diễn bằng model. Nguồn/tokens/quyền không trở thành instructions thực thi.</p>
  <p>Hai bước: tạo đề xuất, rồi duyệt lưu note riêng. Quota chung với học hội thoại: 10 đề xuất/ngày/người/workspace. Chưa tự sửa code, policy hoặc publish skill.</p>
  {error&&<p role="alert">{error}</p>}
  <label>Brain <select aria-label="Artifact brain" value={brain} disabled={busy} onChange={e=>void selectBrain(e.target.value)}><option value="">Chọn Brain</option>{brains.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label>
  <label>Tài liệu <select aria-label="Artifact file" value={file} disabled={busy||!brain} onChange={e=>void selectFile(e.target.value)}><option value="">Chọn tài liệu</option>{files.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select></label>
  {text&&<details><summary>Nguồn nguyên văn (dữ liệu không tin cậy)</summary><pre aria-label="Artifact source text">{text}</pre></details>}
  <label>Cách tạo <select aria-label="Artifact derivation" value={mode} disabled={busy} onChange={e=>{setMode(e.target.value);invalidate()}}><option value="quote">Trích nguyên văn</option><option value="extractive_summary_v1">Ghép 2–5 dòng có nguồn</option></select></label>
  {mode==="quote"?<label>Trích đoạn (3–2000 ký tự)<textarea aria-label="Artifact candidate" style={{width:"100%",maxWidth:620,boxSizing:"border-box"}} value={candidate} maxLength={2000} disabled={busy} onChange={e=>{setCandidate(e.target.value);invalidate()}}/></label>
   :<fieldset><legend>Chọn 2–5 dòng; backend giữ offset và hash từng đoạn</legend>{parts.slice(0,100).map(p=><label key={p.index}><input type="checkbox" aria-label={`Artifact segment ${p.index}`} checked={chosen.includes(p.index)} disabled={busy||(!chosen.includes(p.index)&&chosen.length>=5)} onChange={e=>{setChosen(old=>e.target.checked?[...old,p.index]:old.filter(i=>i!==p.index));invalidate()}}/>{p.value}</label>)}{parts.length>100&&<p>Chỉ hiển thị 100 dòng đầu; dùng trích nguyên văn cho đoạn khác.</p>}</fieldset>}
  <button disabled={busy||!file||(mode==="quote"?candidate.length<3:chosen.length<2)} onClick={()=>void review()}>Xem trước đề xuất tài liệu</button>
  {preview&&<><pre aria-label="Artifact proposal preview">{JSON.stringify(preview.value,null,2)}</pre><label><input aria-label="Confirm artifact proposal" type="checkbox" checked={ack} disabled={busy} onChange={e=>setAck(e.target.checked)}/>Tôi đã kiểm tra nguồn/diff. Chỉ tạo đề xuất, chưa lưu note.</label><button disabled={busy||!ack} onClick={()=>void save()}>Tạo đề xuất tài liệu</button></>}
  {rows.map(row=><article key={row.id}><h3>{row.derivation} · {row.status}</h3><p>Nguồn {row.source_id} · hash {row.source_hash}</p><pre>{row.candidate}</pre><details><summary>Provenance</summary><pre>{JSON.stringify(row.segments,null,2)}</pre></details>
   {row.status==="pending"&&<><button disabled={busy} onClick={()=>void decide(row,"promote")}>Duyệt note tài liệu</button><button disabled={busy} onClick={()=>void decide(row,"reject")}>Từ chối tài liệu</button></>}
   {row.status==="promoted"&&<button disabled={busy} onClick={()=>void decide(row,"revert")}>Hoàn tác note tài liệu</button>}
  </article>)}
 </section></div>;
}
