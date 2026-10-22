"use client";
import {useCallback,useEffect,useRef,useState} from "react";
import {usePao} from "@/lib/PaoRuntimeContext";
import type {components} from "../../../../../packages/contracts/schema";
import "./brains.css";
import BrainContent from "./BrainContent";

type Brain=components["schemas"]["BrainOut"];
export default function BrainManager({workspace,brand}:{workspace:string;brand:string}){
  const runtime=usePao(),epoch=useRef(0);
  const [enabled,setEnabled]=useState(false),[rows,setRows]=useState<Brain[]>([]),[id,setId]=useState("");
  const [name,setName]=useState(""),[archived,setArchived]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const selected=rows.find(row=>row.id===id),session=runtime.sessions.find(row=>row.id===runtime.sessionId);
  const writable=runtime.me?.workspaces.find(row=>row.id===workspace)?.role!=="viewer",owned=selected?.owner_id===runtime.me?.id;
  const load=useCallback(async()=>{
    if(!workspace)return;
    const ticket=++epoch.current;
    try{
      const state=await runtime.api<{enabled:boolean}>(`/v1/brains/status?workspace_id=${workspace}`);
      if(ticket!==epoch.current)return;
      setEnabled(state.enabled);
      if(!state.enabled){setRows([]);return;}
      const data=await runtime.api<Brain[]>(`/v1/brains?workspace_id=${workspace}&archived=${archived}`);
      if(ticket!==epoch.current)return;
      setRows(data);setId(old=>data.some(row=>row.id===old)?old:data[0]?.id||"");
    }catch(reason){if(ticket===epoch.current)setError((reason as Error).message);}
  },[workspace,archived,runtime.api]);
  useEffect(()=>{void load()},[load]);
  async function act(action:()=>Promise<unknown>){setBusy(true);setError("");setNotice("");try{await action();await load();}catch(reason){setError((reason as Error).message);await load();}finally{setBusy(false);}}
  return <section className="brain-manager" aria-label="Brain Manager">
    <header><div><strong>Brain Manager</strong><p>Kho tri thức riêng trong workspace. Files/Notes không tự đưa vào chat; bật nguồn trong từng hội thoại để dùng P2.</p></div><span>{enabled?"LOCAL MVP":"CHƯA BẬT"}</span></header>
    {!enabled?<p>Brain giữ tắt cho đến nghiệm thu local. Memory/Brands hiện có vẫn giữ quyền cũ.</p>:<>
<div className="brain-controls"><label>Chọn Brain<select disabled={busy} aria-label="Chọn Brain" value={id} onChange={e=>setId(e.target.value)}><option value="">Chưa có Brain</option>{rows.map(row=><option value={row.id} key={row.id}>{row.name}{row.legacy_default?" · Legacy private":""}{row.archived_at?" · Archived":""}</option>)}</select></label><label><input type="checkbox" disabled={busy} checked={archived} onChange={e=>setArchived(e.target.checked)}/>Hiện cả archived</label><button disabled={busy} onClick={()=>void load()}>Tải lại Brain</button></div>
      <form onSubmit={e=>{e.preventDefault();void act(async()=>{const row=await runtime.api<Brain>("/v1/brains","POST",{workspace_id:workspace,brand_id:brand||null,name});setId(row.id);setName("");setNotice("Đã tạo Brain riêng tư.");})}}><label>Tên Brain<input aria-label="Tên Brain" value={name} onChange={e=>setName(e.target.value)} maxLength={120} required/></label><button disabled={busy||!writable||!name.trim()}>Tạo Brain</button><button type="button" disabled={busy||!writable} onClick={()=>void act(async()=>{const row=await runtime.api<Brain>("/v1/brains/default","POST",{workspace_id:workspace,brand_id:brand||null});setId(row.id);setNotice("Legacy Brain giữ ACL memory cũ.");})}>Mở Brain mặc định</button></form>
      {selected&&<div className="brain-details"><p>Revision {selected.revision} · {owned?"Owner":"Được cấp quyền"} · {selected.legacy_default?"Legacy facts chỉ owner được đọc":"Không kế thừa legacy memory"}</p><div className="brain-controls"><button disabled={busy||!owned||!writable||!name.trim()} onClick={()=>void act(async()=>{await runtime.api(`/v1/brains/${id}`,"PATCH",{revision:selected.revision,name});setName("");})}>Đổi tên bằng tên nhập trên</button><button disabled={busy||!owned||!writable} onClick={()=>void act(async()=>{await runtime.api(`/v1/brains/${id}`,"PATCH",{revision:selected.revision,archived:!selected.archived_at});setNotice("Đã cập nhật archive; dữ liệu không bị xóa.");})}>{selected.archived_at?"Phục hồi Brain":"Archive Brain"}</button><button disabled={busy||!writable||!session||runtime.active||Boolean(selected.archived_at)} onClick={()=>void act(async()=>{const association=await runtime.api<{version:number}>(`/v1/sessions/${session!.id}/brain`);await runtime.api(`/v1/sessions/${session!.id}/brain`,"PUT",{brain_id:id,version:association.version});setNotice("Đã gắn Brain; run cũ không đổi.");})}>Gắn với hội thoại đang chọn</button></div><small>{session?`Hội thoại: ${session.title}`:"Chọn/tạo hội thoại trong Chat trước khi gắn Brain."}</small></div>}
    </>}
    {enabled&&selected&&<BrainContent brainId={selected.id} archived={Boolean(selected.archived_at)} writable={writable&&(owned||selected.effective_role==='editor')} onChange={load} onBusy={setBusy}/>}
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  </section>;
}
