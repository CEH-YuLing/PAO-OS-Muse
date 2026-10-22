'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';

type Resource={provider:string;installation_resource_id:string;revision:number;enabled:boolean;is_default:boolean;default_model:string;models:string[];model_details?:import('@/lib/chat-model-catalog.mjs').ChatModelDetail[];error:string|null;inference_evidence?:{state:string;model:string|null;observed_at:string|null};catalog_evidence?:{revision:number;observed_at:string|null}};
type View={enabled:boolean;can_manage:boolean;resources:Resource[];provider_calls:false;compatibility_preview?:{read_only:boolean;sessions_by_authority:Record<string,number>;runs_by_authority:Record<string,number>;active_runs:number}|null};
const names:Record<string,string>={openai:'OpenAI',openrouter:'OpenRouter',anthropic:'Anthropic',gemini:'Google Gemini',codex_cli:'Codex'};

export default function InstallationAISettings({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 const {apiRaw,activeWorkspace:workspace,me}=usePao(),epoch=useRef(0);
 const [view,setView]=useState<View|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
 const [drafts,setDrafts]=useState<Record<string,boolean>>({}),scopeRef=useRef('');
 const markDirty=useCallback((id:string,dirty:boolean)=>setDrafts(previous=>previous[id]===dirty?previous:{...previous,[id]:dirty}),[]);
 useEffect(()=>{onDraftChange?.(Object.values(drafts).some(Boolean))},[drafts,onDraftChange]);
 useEffect(()=>()=>onDraftChange?.(false),[onDraftChange]);
 useEffect(()=>{const reload=()=>setRefresh(v=>v+1);window.addEventListener('pao:ai-resources',reload);return()=>window.removeEventListener('pao:ai-resources',reload)},[]);
 useEffect(()=>{const ticket=++epoch.current,controller=new AbortController(),scope=`${workspace?.id}:${me?.id}`;if(scopeRef.current!==scope){scopeRef.current=scope;setView(null);setDrafts({})}setError('');setBusy(false);
  if(workspace?.id)void apiRaw(`/v1/installation-ai?workspace_id=${workspace.id}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])})
   .then(async response=>{const value=await response.json();if(typeof value.enabled!=='boolean'||typeof value.can_manage!=='boolean'||!Array.isArray(value.resources)||value.provider_calls!==false)throw Error();if(ticket===epoch.current)setView(value)})
   .catch(()=>{if(ticket===epoch.current&&!controller.signal.aborted)setError('Chưa đọc được cấu hình AI dùng chung. Không suy ra kết nối cũ đã hỏng hoặc đã được chia sẻ.');});
  return()=>{epoch.current++;controller.abort()};
 },[apiRaw,workspace?.id,me?.id,refresh]);
 async function save(row:Resource,enabled:boolean,is_default:boolean,model:string){
  const ticket=epoch.current;setBusy(true);setError('');
  try{await apiRaw(`/v1/installation-ai/${row.installation_resource_id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_key:crypto.randomUUID(),expected_revision:row.revision,enabled,is_default,default_model:model})});if(ticket===epoch.current){setRefresh(v=>v+1);window.dispatchEvent(new Event('pao:chat-config'));}}
  catch{if(ticket===epoch.current)setError('Chưa lưu được. Hãy làm mới để kiểm tra phiên bản, quyền quản trị bản cài và trạng thái kết nối. PAO không tự chuyển sang API khác.');}
  finally{if(ticket===epoch.current)setBusy(false)}
 }
 return <section className="installation-ai-settings" aria-label="Tài nguyên AI dùng chung">
  <header><h3>Tài nguyên AI dùng chung</h3><p>Quản trị bản cài kết nối một lần; người dùng hợp lệ kế thừa quyền dùng AI theo vai trò ứng dụng. Không cần cấp quyền AI riêng cho từng nhân sự. Khóa và dữ liệu doanh nghiệp không hiển thị cho người dùng khác.</p></header>
  {error&&<p role="alert">{error}</p>}
  {!view&&!error&&<p role="status">Đang đọc cấu hình đã lưu, không gọi model…</p>}
  {view&&!view.enabled&&<p>Cổng tài nguyên chung chưa được bật trên backend này. Các kết nối cũ vẫn được giữ nguyên; chưa tự chia sẻ phiên cá nhân.</p>}
  {view?.enabled&&!view.resources.length&&<p>Chưa có tài nguyên chung. Quản trị bản cài kết nối nhà cung cấp và đọc danh mục model, sau đó lưu cấu hình dùng chung tại đây.</p>}
  {view?.resources.map(row=><ResourceCard key={row.installation_resource_id+':'+row.revision} row={row} canManage={view.can_manage} busy={busy} save={save} onDirty={markDirty}/>)}
  {view?.compatibility_preview&&<details><summary>Đối chiếu cấu hình cũ · chỉ xem, không thay đổi</summary><p>Chỉ thống kê hội thoại của bạn trong doanh nghiệp đang chọn. Không chuyển tài khoản cá nhân thành tài nguyên chung, không sao chép khóa, không đổi tác vụ đã chốt và không xóa lịch sử.</p><p>{Object.values(view.compatibility_preview.sessions_by_authority).reduce((a,b)=>a+b,0)} hội thoại · {Object.values(view.compatibility_preview.runs_by_authority).reduce((a,b)=>a+b,0)} lượt chạy · {view.compatibility_preview.active_runs} lượt đang chờ hoặc xử lý.</p><p>Cấu hình mới dùng nguồn bạn chọn; cấu hình cũ được giữ để đối chiếu và phục hồi. Chỉ dọn cấu hình cũ sau khi kiểm tra lịch sử và phạm vi sử dụng.</p></details>}
  <button type="button" disabled={busy} onClick={()=>setRefresh(v=>v+1)}>Đọc lại cấu hình dùng chung</button>
  <details><summary>Phạm vi, lưu cấu hình và xử lý lỗi</summary><p>Chủ một doanh nghiệp không tự động là quản trị bản cài. Chỉ quản trị bản cài được đổi kết nối chung. Lưu cấu hình không gọi suy luận, không chứng minh còn hạn mức và không cấp quyền chạy công cụ.</p><p>Đổi model mặc định chỉ áp dụng cho lựa chọn mới; tác vụ đã chốt giữ nguyên lịch sử. Tắt tài nguyên hoặc đổi khóa sẽ được kiểm tra lại trước khi gửi công việc đang chờ. Không tự chuyển sang API trả phí. Nếu đổi tài khoản, hãy đọc lại danh mục và lưu lại cấu hình; không gửi khóa trong hội thoại.</p></details>
 </section>;
}

function ResourceCard({row,canManage,busy,save,onDirty}:{row:Resource;canManage:boolean;busy:boolean;save:(row:Resource,enabled:boolean,is_default:boolean,model:string)=>Promise<void>;onDirty:(id:string,dirty:boolean)=>void}){
 const [model,setModel]=useState(row.default_model),[enabled,setEnabled]=useState(row.enabled),[makeDefault,setMakeDefault]=useState(row.is_default);
 const dirty=model!==row.default_model||enabled!==row.enabled||makeDefault!==row.is_default;
 useEffect(()=>{onDirty(row.installation_resource_id,dirty)},[dirty,row.installation_resource_id,onDirty]);
 useEffect(()=>()=>onDirty(row.installation_resource_id,false),[row.installation_resource_id,onDirty]);
 return <article><h4>{names[row.provider]||row.provider}</h4><p>{row.enabled&&!row.error?'Đã bật trong PAO':'Chưa sẵn sàng sử dụng'}{row.is_default?' · Mặc định bản cài':''}</p>
  <p>{row.inference_evidence?.state==='observed_success'?`Đã có lần chạy thành công trong doanh nghiệp này với ${row.inference_evidence.model}. Đây là lịch sử, không phải kiểm tra kết nối hiện tại.`:'Chưa có bằng chứng chạy model thành công với phiên bản cấu hình này trong doanh nghiệp đang chọn.'} Hạn mức còn lại: chưa xác minh.</p>
  <label>Model mặc định<select aria-label="Model mặc định" value={model} disabled={!canManage||busy} onChange={event=>setModel(event.target.value)}>{row.models.map(value=><option key={value} value={value} disabled={row.model_details?.find(v=>v.model===value)?.model_capabilities?.chat_supported===false}>{value}</option>)}</select></label>
  {canManage&&<><label><input type="checkbox" checked={enabled} disabled={busy} onChange={event=>setEnabled(event.target.checked)}/>Bật tài nguyên dùng chung</label><label><input type="checkbox" checked={makeDefault} disabled={busy||!enabled} onChange={event=>setMakeDefault(event.target.checked)}/>Dùng làm mặc định cho hội thoại mới</label><button type="button" disabled={busy||!model} onClick={()=>void save(row,enabled,makeDefault,model)}>Lưu cấu hình dùng chung</button></>}
  {row.error&&<p>{row.error==='installation_ai_cli_adapter_pending'?'Adapter dùng chung của Client chưa đạt điều kiện nghiệm thu. Chưa tự sử dụng hồ sơ cá nhân.':row.error==='installation_ai_resource_disabled'?'Tài nguyên chưa được bật.':'Kết nối cần được quản trị bản cài kiểm tra lại.'}</p>}
 </article>;
}
