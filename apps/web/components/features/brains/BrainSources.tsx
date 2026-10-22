"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import type {components} from "../../../../../packages/contracts/schema";
type S=components["schemas"];type Source=S["KnowledgeSourceOut"];type Preview=S["SourcePreview"];
export default function BrainSources({brainId,files,notes,writable,busy,onBusy}:{brainId:string;files:S["BrainFileOut"][];notes:S["BrainNoteOut"][];writable:boolean;busy:boolean;onBusy:(value:boolean)=>void}){
  const runtime=usePao(),epoch=useRef(0),base=`/v1/brains/${brainId}`;
  const [enabled,setEnabled]=useState(false),[rows,setRows]=useState<Source[]>([]),[kind,setKind]=useState<"file"|"note">("file"),[origin,setOrigin]=useState("");
  const [selected,setSelected]=useState<Source|null>(null),[version,setVersion]=useState(1),[preview,setPreview]=useState<Preview|null>(null),[error,setError]=useState("");
  const load=useCallback(async()=>{const ticket=++epoch.current;try{
    const state=await runtime.api<{enabled:boolean}>(`${base}/sources/status`);
    if(ticket!==epoch.current)return;setEnabled(state.enabled);
    if(!state.enabled){setRows([]);return;}
    const data=await runtime.api<Source[]>(`${base}/sources?archived=true`);
    if(ticket===epoch.current)setRows(data);
  }catch(reason){if(ticket===epoch.current)setError((reason as Error).message)}},[base,runtime.api]);
  useEffect(()=>{setSelected(null);setPreview(null);setOrigin("");setError("");void load();return()=>{epoch.current++}},[load]);
  useEffect(()=>{void load()},[files,notes,load]);
  async function act(action:()=>Promise<void>){onBusy(true);setError("");try{await action();await load()}catch(reason){setError((reason as Error).message)}finally{onBusy(false)}}
  const origins=kind==="file"?files.filter(row=>!row.trashed_at).map(row=>({id:row.id,name:row.name})):notes.filter(row=>!row.trashed_at).map(row=>({id:row.id,name:row.title}));
  return <section aria-label="Brain Sources"><hr/><strong>Sources · P2.1</strong>
    <p>Đăng ký file/note thành nguồn có hash và phiên bản. Sau parse, P2 (nếu bật) tự index; chat chỉ đọc nguồn khi bạn bật opt-in.</p>
    {!enabled?<p>Sources chưa bật; Files/Notes vẫn dùng được.</p>:<>
      <form onSubmit={event=>{event.preventDefault();void act(async()=>{const row=await runtime.api<Source>(`${base}/sources`,"POST",{kind,origin_id:origin});setSelected(row);setVersion(row.current_version);setPreview(null)})}}>
        <label>Loại nguồn<select aria-label="Loại nguồn" value={kind} disabled={busy} onChange={event=>{setKind(event.target.value as "file"|"note");setOrigin("")}}><option value="file">File</option><option value="note">Note</option></select></label>
        <label>File/note nguồn<select aria-label="Origin nguồn" value={origin} disabled={busy} onChange={event=>setOrigin(event.target.value)}><option value="">Chọn nguồn đã lưu</option>{origins.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <button disabled={busy||!writable||!origin}>Đăng ký nguồn</button>
      </form>
      <button disabled={busy} onClick={()=>void load()}>Tải lại Sources</button><small> Hiển thị tối đa100 nguồn đầu; API hỗ trợ phân trang.</small>
      <ul>{rows.map(row=><li key={row.id}><strong>{row.title}</strong> · v{row.current_version} · <span>{row.parse_status}</span> · {row.source_sha256.slice(0,12)}{row.stale?" · Stale: origin đã đổi":""}{row.origin_trashed?" · Origin ở trash":""}{row.archived_at?" · Archived":""}
        <button disabled={busy||Boolean(row.archived_at)||row.origin_trashed} onClick={()=>{setSelected(row);setVersion(row.current_version);setPreview(null)}}>Chọn source {row.title}</button>
        <button disabled={busy||!writable||Boolean(row.archived_at)||row.origin_trashed} onClick={()=>void act(async()=>{const next=await runtime.api<Source>(`${base}/sources/${row.id}/refresh`,"POST");setSelected(next);setVersion(next.current_version);setPreview(null)})}>Refresh source {row.title}</button>
        <button disabled={busy||!writable} onClick={()=>void act(async()=>{await runtime.api(`${base}/sources/${row.id}`,"PATCH",{revision:row.revision,archived:!row.archived_at});setSelected(null);setPreview(null)})}>{row.archived_at?"Restore source":"Archive source"} {row.title}</button>
        {row.parse_status==="failed"&&<button disabled={busy||!writable||Boolean(row.archived_at)||row.origin_trashed} onClick={()=>void act(async()=>{await runtime.api(`${base}/ingestion-jobs/${row.job_id}/retry`,"POST")})}>Retry parse {row.title}</button>}
      </li>)}</ul>
      {selected&&<div><p>Source đang chọn: {selected.title}</p><label>Source version<input aria-label="Source version" type="number" min={1} max={100} value={version} disabled={busy} onChange={event=>setVersion(Number(event.target.value))}/></label><button disabled={busy||version<1||!Number.isInteger(version)} onClick={()=>void act(async()=>{setPreview(await runtime.api<Preview>(`${base}/sources/${selected.id}/versions/${version}/preview`))})}>Preview source version</button></div>}
      {preview&&<div><small>v{preview.version} · lines {preview.start_line}–{preview.end_line} · {preview.parser_version} · source hash {preview.source_sha256}{preview.truncated?" · Chỉ đoạn đầu; dùng origin download để đọc toàn bộ":""}</small><pre className="brain-preview" aria-label="Source plain preview">{preview.content}</pre></div>}
    </>}{error&&<p role="alert">{error}</p>}
  </section>;
}
