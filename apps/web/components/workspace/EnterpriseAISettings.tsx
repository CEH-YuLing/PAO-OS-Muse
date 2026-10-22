'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {workspaceAiPolicy,workspaceAiDraft,workspaceAiSave,workspaceAiSettingsUrl,type WorkspaceAiPolicy,type WorkspaceAiDraft} from '@/lib/workspace-ai-setup.mjs';
import './model-access.css';

const names:Record<string,string>={openai:'OpenAI',anthropic:'Claude API',gemini:'Google Gemini',openrouter:'OpenRouter'};
const emptyDraft:WorkspaceAiDraft={selected:[],defaultId:'',enabled:false,suggested:false};
export default function EnterpriseAISettings({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 const {activeWorkspace,me}=usePao();
 return <WorkspaceAISetup key={`${activeWorkspace?.id}:${me?.id}:${activeWorkspace?.role}`} onDraftChange={onDraftChange}/>;
}
function WorkspaceAISetup({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 const {apiRaw,activeWorkspace,me}=usePao(),wid=activeWorkspace?.id||'',uid=me?.id||'';
 const manage=activeWorkspace?.role==='owner'||activeWorkspace?.role==='admin';
 const [policy,setPolicy]=useState<WorkspaceAiPolicy|null>(null),[draft,setDraft]=useState(emptyDraft);
 const [ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState(''),[uncertain,setUncertain]=useState(false);
 const epoch=useRef(0),controller=useRef<AbortController|null>(null),working=useRef(false);
 const draftNotice=useRef(onDraftChange);draftNotice.current=onDraftChange;
 const accept=useCallback((raw:unknown)=>{
  const value=workspaceAiPolicy(raw,wid);setPolicy(value);setDraft(workspaceAiDraft(value));setAck(false);draftNotice.current?.(false);
 },[wid]);
 const read=useCallback(async()=>{
  if(!wid||!uid||working.current)return;
  const ticket=++epoch.current,abort=new AbortController();controller.current?.abort();controller.current=abort;working.current=true;
  setBusy(true);setError('');setMessage('');
  try{
   const response=await apiRaw(`/v1/workspaces/${wid}/enterprise-ai`,{signal:AbortSignal.any([abort.signal,AbortSignal.timeout(15000)])});
   const value=await response.json();if(ticket!==epoch.current||abort.signal.aborted)return;
   accept(value);setUncertain(false);
  }catch{if(ticket===epoch.current&&!abort.signal.aborted){setUncertain(true);setError('Chưa tải được thiết lập AI. Kiểm tra đăng nhập rồi bấm Tải lại; PAO không tự bật kết nối.')}}
  finally{if(ticket===epoch.current){working.current=false;setBusy(false)}}
 },[wid,uid,apiRaw,accept]);
 useEffect(()=>{
  void read();const generation=epoch,abort=controller,lock=working;
  return()=>{generation.current++;abort.current?.abort();lock.current=false;draftNotice.current?.(false)};
 },[read]);
 async function save(){
  if(!policy||!manage||!policy.can_manage||working.current||uncertain)return;
  let body;
  try{body=workspaceAiSave(policy,draft,crypto.randomUUID(),ack)}catch{setError('Chọn kết nối hợp lệ, AI mặc định và xác nhận trước khi lưu.');return}
  const ticket=++epoch.current,abort=new AbortController();controller.current=abort;working.current=true;setBusy(true);setError('');setMessage('');
  try{
   const response=await apiRaw(`/v1/workspaces/${wid}/enterprise-ai`,{method:'PUT',signal:AbortSignal.any([abort.signal,AbortSignal.timeout(30000)]),headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   const value=await response.json();if(ticket!==epoch.current||abort.signal.aborted)return;
   accept(value);setMessage('Đã lưu thiết lập AI. Hội thoại mới nhận AI mặc định; hội thoại cũ giữ nguyên. Chưa gửi yêu cầu tới nhà cung cấp.');
  }catch{if(ticket===epoch.current&&!abort.signal.aborted){setUncertain(true);setError('Chưa xác nhận được kết quả lưu. Bấm Tải lại trước khi lưu tiếp; có thể yêu cầu đã được xử lý. PAO không tự gửi lại.')}}
  finally{if(ticket===epoch.current){working.current=false;setBusy(false)}}
 }
 function change(next:Partial<WorkspaceAiDraft>){setDraft(old=>({...old,...next,suggested:false}));setAck(false);setMessage('');draftNotice.current?.(true)}
 const primary=policy?.connections.find(row=>row.id===policy.default_connection_id);
 const canSave=Boolean(policy&&manage&&policy.can_manage&&!busy&&!uncertain&&(!draft.enabled||ack&&draft.defaultId&&draft.selected.length));
 const link=(section:'access'|'providers'|'members',method:'client'|'api'='client')=>wid?workspaceAiSettingsUrl(wid,section,method):'#';
 return <section className="pao-model-access enterprise-ai-settings" aria-label="Thiết lập AI cho không gian làm việc">
  <header className="solo-ai-heading"><div><h2>AI cho bạn và nhóm nhỏ</h2><p>{activeWorkspace?.name} · Một người sử dụng được ngay; thêm 1–2 cộng sự khi cần.</p></div><span className="solo-ai-state">{!policy?'Chưa đọc được trạng thái':policy.enabled&&primary?.available?'Đã bật trong PAO':'Chưa sẵn sàng hoặc đang tắt'}</span></header>
  <ol className="solo-ai-steps" aria-label="Ba bước bắt đầu với AI">
   <li><strong>1. Kết nối AI</strong><span>Đăng nhập Client hoặc nhập khóa API một lần.</span></li>
   <li><strong>2. Chọn AI mặc định</strong><span>Lưu thiết lập cho không gian đang chọn.</span></li>
   <li><strong>3. Bắt đầu làm việc</strong><span>Mở hội thoại mới, giao việc và duyệt kết quả.</span></li>
  </ol>
  <p>Bạn làm một mình: không cần tạo nhân sự hoặc mời thêm tài khoản. Với kết nối dùng chung được hỗ trợ, thành viên hoạt động kế thừa quyền AI; không phải nhập khóa riêng.</p>
  <div className="solo-ai-links"><a href={link('providers')}>Kết nối qua Client</a><a href={link('providers','api')}>Kết nối qua API</a><button type="button" disabled={busy} onClick={()=>void read()}>{busy?'Đang tải…':'Tải lại thiết lập AI'}</button></div>
  {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {policy&&<>
   <p className="solo-ai-saved">Đã lưu: {policy.enabled&&primary?`${names[primary.provider]||primary.provider} · ${primary.model}`:'Chưa bật AI mặc định'} · phiên bản {policy.revision}. Đây là trạng thái trong PAO, không phải kiểm thử dịch vụ thật.</p>
   <fieldset disabled={busy||!manage||!policy.can_manage||uncertain}>
    <legend>AI mặc định</legend>
    <label><input type="checkbox" checked={draft.enabled} onChange={e=>change({enabled:e.target.checked})}/>Bật AI cho không gian làm việc này</label>
    {!policy.connections.length?<div className="solo-ai-empty"><strong>Chưa có API được cấu hình</strong><p>Bạn vẫn có thể kết nối Codex riêng cho mình ở tab Client. Kết nối API là tùy chọn, không bắt buộc mua thêm gói hoặc tạo tài khoản dịch vụ. Codex dùng chung cho nhóm chưa hoàn tất.</p></div>:<>
     <label>Chọn AI dùng mặc định<select aria-label="AI mặc định" value={draft.defaultId} onChange={e=>{const id=e.target.value;change({defaultId:id,selected:id&&!draft.selected.includes(id)?[...draft.selected,id]:draft.selected})}}><option value="">Chọn kết nối…</option>{policy.connections.map(row=><option key={row.id} value={row.id} disabled={row.status!=='connected'}>{names[row.provider]||row.provider} · {row.model}{row.status!=='connected'?' · Cần kiểm tra':''}</option>)}</select></label>
     {draft.suggested&&<p role="note">PAO đề xuất kết nối duy nhất hiện có. Đây chỉ là lựa chọn trên biểu mẫu, chưa được bật hoặc lưu.</p>}
     {draft.defaultId&&<p>{policy.connections.find(row=>row.id===draft.defaultId)?.available?'Kết nối đã được bật trong PAO; chưa kiểm thử provider.':'Lựa chọn mới hoặc cấu hình đã đổi: cần xác nhận và lưu trước khi dùng.'}</p>}
    </>}
    <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>Tôi đồng ý dùng các AI đã chọn trong không gian này; có thể tiêu hạn mức thuê bao hoặc chi phí API.</label>
    <button type="button" disabled={!canSave} onClick={()=>void save()}>Lưu thiết lập AI</button>
    <details className="solo-ai-advanced"><summary>Nâng cao: thêm AI được phép sử dụng</summary><p>Chỉ cần mở nếu muốn dùng nhiều kết nối. Đổi AI theo từng công việc vẫn được giữ; không gắn cứng nhà cung cấp với vai trò.</p>{policy.connections.map(row=><label key={row.id}><input type="checkbox" checked={draft.selected.includes(row.id)} disabled={row.status!=='connected'&&!draft.selected.includes(row.id)} onChange={e=>change({selected:e.target.checked?[...draft.selected,row.id]:draft.selected.filter(id=>id!==row.id),defaultId:!e.target.checked&&draft.defaultId===row.id?'':draft.defaultId})}/>{names[row.provider]||row.provider} · {row.model} · {row.available?'Đã bật trong PAO':row.status==='connected'?'Có cấu hình':'Cần kiểm tra'}</label>)}</details>
   </fieldset>
  </>}
  {!manage&&<p>Người quản lý cấu hình AI một lần; bạn không cần nhập khóa hoặc xin quyền từng model. Vai trò của bạn vẫn quyết định dữ liệu và hành động được phép.</p>}
  <details><summary>Nhóm nhỏ và quyền sử dụng</summary><p>Chủ sở hữu hoặc quản trị viên quản lý kết nối. Chỉ mời thêm người khi cần; không yêu cầu tối thiểu số thành viên. Người xem chỉ có chat văn bản chỉ đọc, chưa gắn kho tri thức. Dùng chung AI không chia sẻ hội thoại riêng hoặc mở quyền đăng bài, chạy công cụ, sửa quảng cáo và chi tiền.</p>{manage&&<a href={link('members')}>Quản lý cộng sự · tùy chọn</a>}</details>
  <details><summary>Ngắt kết nối, đổi khóa và xử lý lỗi</summary><p>Lưu không phải kiểm thử AI thật. Khi đổi hoặc xóa khóa, tải lại và lưu lựa chọn hợp lệ. Tắt rồi lưu để ngừng quyền dùng chung; quyền cá nhân cũ cần kiểm tra riêng trong mục nâng cao. Chính sách mới không tự thay model hội thoại hoặc ghim lại công việc cũ. PAO không tự chuyển sang API trả phí khi Client lỗi.</p><p>Codex hiện dùng hồ sơ đăng nhập riêng của bạn; chưa chia sẻ cho cộng sự. Không cần tài khoản dịch vụ cho luồng cá nhân. Claude Code và Antigravity chưa có adapter hoạt động. Không gửi token hoặc mật khẩu trong chat.</p></details>
 </section>;
}
