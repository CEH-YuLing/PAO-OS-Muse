'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import CodexModelSettings from './CodexModelSettings';
import {personalCodexPath,personalCodexView,personalCodexSave,type PersonalCodexView} from '@/lib/personal-codex-setup.mjs';
export default function PersonalCodexSettings({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 const {activeWorkspace,me}=usePao();
 if(!['owner','admin'].includes(activeWorkspace?.role||''))return null;
 return <OwnCodex key={`${activeWorkspace?.id}:${me?.id}:${activeWorkspace?.role}`} onDraftChange={onDraftChange}/>;
}
function OwnCodex({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 const {activeWorkspace,me,apiRaw}=usePao(),wid=activeWorkspace?.id||'',uid=me?.id||'';
 const [value,setValue]=useState<PersonalCodexView|null>(null),[enabled,setEnabled]=useState(false),[makeDefault,setDefault]=useState(true),[connection,setConnection]=useState('');
 const [ack,setAck]=useState(false),[busy,setBusy]=useState(false),[uncertain,setUncertain]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const epoch=useRef(0),controller=useRef<AbortController|null>(null),working=useRef(false),draft=useRef(onDraftChange);draft.current=onDraftChange;
 const accept=useCallback((raw:unknown)=>{
  const next=personalCodexView(raw,wid,uid);setValue(next);setEnabled(next.enabled);setDefault(next.revision===0?true:next.make_default);
  const ready=next.connections.filter(row=>row.authentication_ready&&!row.operation_pending);
  setConnection(next.connection_id||(ready.length===1?ready[0].id:''));setAck(false);draft.current?.(false);
 },[wid,uid]);
 const read=useCallback(async()=>{
  if(!wid||!uid||working.current)return;
  const ticket=++epoch.current,abort=new AbortController();controller.current?.abort();controller.current=abort;working.current=true;setBusy(true);setError('');setNotice('');
  try{const response=await apiRaw(personalCodexPath(wid),{signal:AbortSignal.any([abort.signal,AbortSignal.timeout(15000)])});const raw=await response.json();if(ticket!==epoch.current||abort.signal.aborted)return;accept(raw);setUncertain(false)}
  catch{if(ticket===epoch.current&&!abort.signal.aborted){setUncertain(true);setError('Chưa tải được thiết lập Codex. Bấm Tải lại; không tự tạo quyền hoặc gọi AI.')}}
  finally{if(ticket===epoch.current){working.current=false;setBusy(false)}}
 },[wid,uid,apiRaw,accept]);
 useEffect(()=>{void read();const event=()=>void read();window.addEventListener('pao:codex-profile',event);const generation=epoch,abort=controller,lock=working;return()=>{generation.current++;abort.current?.abort();lock.current=false;draft.current?.(false);window.removeEventListener('pao:codex-profile',event)}},[read]);
 function changed(){setAck(false);setNotice('');draft.current?.(true)}
 async function save(){
  if(!value||working.current||uncertain)return;
  let body;try{body=personalCodexSave(value,{enabled,makeDefault,connection},crypto.randomUUID(),ack)}catch{setError('Chọn hồ sơ đã đăng nhập và xác nhận sử dụng trước khi lưu.');return}
  const ticket=++epoch.current,abort=new AbortController();controller.current=abort;working.current=true;setBusy(true);setError('');setNotice('');
  try{const response=await apiRaw(personalCodexPath(wid),{method:'PUT',headers:{'Content-Type':'application/json'},signal:AbortSignal.any([abort.signal,AbortSignal.timeout(30000)]),body:JSON.stringify(body)});const raw=await response.json();if(ticket!==epoch.current||abort.signal.aborted)return;accept(raw);setNotice('Đã lưu. Không tạo grant hoặc gọi AI. Mở hội thoại mới để nhận mặc định mới; hội thoại cũ giữ nguyên.');window.dispatchEvent(new Event('pao:personal-cli'))}
  catch{if(ticket===epoch.current&&!abort.signal.aborted){setUncertain(true);setError('Chưa xác nhận được kết quả lưu. Bấm Tải lại trước khi thử tiếp; PAO không tự gửi lại.')}}
  finally{if(ticket===epoch.current){working.current=false;setBusy(false)}}
 }
 return <section className="pao-model-access pao-personal-codex" aria-label="Dùng Codex cho tôi">
  <h4>Dùng Codex cho tôi</h4><p>Chỉ tài khoản của bạn trong {activeWorkspace?.name}. Không cần chọn nhân sự, cấp grant hoặc đặt thời hạn. Không chia sẻ cho cộng sự.</p>
  <button type="button" disabled={busy} onClick={()=>void read()}>{busy?'Đang tải…':'Tải lại thiết lập Codex'}</button>
  {connection&&<CodexModelSettings key={`${wid}:${uid}:${connection}`} connection={connection}/>}
  {value&&<><p>Phiên bản {value.revision} · {value.ready?'Đã bật trong PAO, chưa kiểm thử model':value.enabled?'Cần đọc và lưu lại thiết lập':'Đang tắt'}.</p>
   <fieldset disabled={busy||uncertain}><legend>Thiết lập Codex cá nhân</legend>
    <label><input type="checkbox" checked={enabled} onChange={e=>{setEnabled(e.target.checked);changed()}}/>Dùng Codex của tôi trong không gian này</label>
    {value.connections.length?<label>Hồ sơ của tôi<select aria-label="Hồ sơ Codex sử dụng" value={connection} onChange={e=>{setConnection(e.target.value);changed()}}><option value="">Chọn hồ sơ…</option>{value.connections.map(row=><option key={row.id} value={row.id} disabled={!row.authentication_ready||row.operation_pending}>{row.model}{!row.authentication_ready?' · Chưa đăng nhập':row.operation_pending?' · Đang thiết lập':''}</option>)}</select></label>:<p>Chưa có hồ sơ riêng. Bấm Kết nối Codex phía trên và hoàn tất đăng nhập chính thức, sau đó Tải lại.</p>}
    <label><input type="checkbox" checked={makeDefault} onChange={e=>{setDefault(e.target.checked);changed()}}/>Dùng cho các hội thoại mới của tôi</label>
    <p>Mặc định này ưu tiên hơn API dùng chung, chỉ cho bạn. Khi nguồn lỗi, PAO báo lỗi thay vì tự chuyển sang API khác. Không gửi lịch sử local cũ hoặc nguồn tri thức ngầm.</p>
    <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>Tôi cho phép gửi nội dung hội thoại mới tới Codex của tôi, có thể tiêu hạn mức thuê bao; không cấp quyền công cụ.</label>
    <button type="button" disabled={enabled&&(!ack||!connection||!value.connections.some(row=>row.id===connection&&row.authentication_ready&&!row.operation_pending))} onClick={()=>void save()}>Lưu thiết lập Codex</button>
   </fieldset></>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <details><summary>Ngừng dùng và quyền cũ</summary><p>Không hết hạn theo phút. Tắt rồi lưu để ngừng thiết lập này; ngắt hồ sơ để chặn cả các quyền dùng hồ sơ đó. Quyền grant cũ vẫn riêng biệt, không tự bị xóa hoặc sống lại. Đổi đăng nhập, vai trò hoặc thành viên có thể yêu cầu xác nhận lại. Chọn model trong hội thoại cũ không tự mở quyền gửi dữ liệu ra ngoài.</p></details>
 </section>;
}
