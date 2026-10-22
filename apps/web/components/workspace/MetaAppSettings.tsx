"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {metaAppStatus,metaAppPayload,metaAppError,type MetaHostStatus} from '@/lib/meta-app-settings.mjs';
import './meta-app-settings.css';
export default function MetaAppSettings({workspace}:{workspace:string}){
 const {apiRaw,activeWorkspace:member}=usePao(),scope=member?.id===workspace&&member?.role==='owner';
 const epoch=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null);
 const [status,setStatus]=useState<MetaHostStatus|null>(null),[appId,setAppId]=useState(''),[version,setVersion]=useState(''),[callback,setCallback]=useState(''),[secret,setSecret]=useState('');
 const [confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
 const clear=useCallback(()=>{setSecret('');setConfirmed(false);setAppId('');setVersion('');setCallback('')},[]);
 const populate=useCallback((value:MetaHostStatus)=>{setAppId(value.app_id);setVersion(value.api_version);setCallback(!value.app_id&&!value.secret_present?window.location.origin+'/v1/integrations/meta/callback':value.redirect_uri);setSecret('');setConfirmed(false)},[]);
 const read=useCallback(async(ticket:number,controller:AbortController)=>{
  const response=await apiRaw('/v1/integrations/meta/app-config?workspace_id='+encodeURIComponent(workspace),{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
  const value=metaAppStatus(await response.json());if(ticket!==epoch.current||controller.signal.aborted)return false;
  setStatus(value);populate(value);return true;
 },[apiRaw,workspace,populate]);
 const load=useCallback(async()=>{
  if(lock.current)return;clear();setStatus(null);setError('');setMessage('');if(!scope)return;
  lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;setBusy(true);
  try{await read(ticket,controller)}catch(reason){if(ticket===epoch.current)setError(metaAppError((reason as Error).message))}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[scope,clear,read]);
 useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=lock;void load();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false}},[load]);
 useEffect(()=>{const wipe=()=>{if(status)populate(status);else clear()},hide=()=>{if(document.hidden)wipe()};document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',wipe);return()=>{document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',wipe)}},[status,populate,clear]);
 async function save(event:React.FormEvent){
  event.preventDefault();if(lock.current||!scope||!status||!confirmed)return;
  let body:ReturnType<typeof metaAppPayload>;
  try{body=metaAppPayload(status,{appId,version,callback,secret})}catch(reason){populate(status);setError(metaAppError((reason as Error).message));setMessage('');return}
  lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setBusy(true);setError('');setMessage('');
  try{
   const response=await apiRaw('/v1/integrations/meta/app-config?workspace_id='+encodeURIComponent(workspace),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.any([controller.signal,AbortSignal.timeout(30000)])});
   const value=metaAppStatus(await response.json());
   if(value.app_id!==body.app_id||value.api_version!==body.api_version||value.redirect_uri!==body.redirect_uri||!value.secret_present||value.write_enabled||value.autopilot_enabled)throw new Error('meta_app_response_invalid');
   if(ticket!==epoch.current||controller.signal.aborted)return;
   setStatus(value);populate(value);setMessage(value.restart_required?'Đã lưu trên máy chủ. Cần quản trị viên nạp lại API và tiến trình xử lý trước khi kết nối Meta; PAO không tự restart.':'Đã lưu cấu hình máy chủ; chưa gọi Meta, OAuth hoặc đồng bộ dữ liệu.');
  }catch(reason){if(ticket===epoch.current){clear();setStatus(null);setError(metaAppError((reason as Error).message))}}
  finally{delete body.app_secret;if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 }
 const edit=()=>{setConfirmed(false);setMessage('');setError('')};
 return <section className="st-meta-app" aria-label="Cấu hình Meta App">
  <header><div><h2>Cấu hình Meta App</h2><p>Ứng dụng dùng chung cho bản cài máy chủ, không phải App của riêng {member?.name}. Native API chỉ cho chủ doanh nghiệp của bản cài một doanh nghiệp/một chủ doanh nghiệp; bản SaaS nhiều doanh nghiệp quản trị máy chủ riêng, BYO App ở S4.</p></div><button type="button" disabled={busy||!scope} onClick={()=>void load()}>Tải lại cấu hình</button></header>
  {error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  {!status&&<p>Chưa có dữ liệu vừa đọc máy chủ được xác nhận; biểu mẫu lưu bị khóa. Đọc lại chỉ lấy thông tin mô tả, bỏ bản nháp và không gọi Meta. lần đọc GET khi yêu cầu cũ còn chạy chưa bảo đảm kết quả cuối; không tự gửi lại.</p>}
  {status&&scope&&<form noValidate onSubmit={event=>void save(event)}>
   <p>Khóa máy chủ: {status.secret_present?'đã lưu, không trả lại':'chưa có'} · chế độ write/autopilot: {status.write_enabled||status.autopilot_enabled?'đang bật — không cho lưu':'đang tắt'}. Đây không phải kết nối OAuth, hoạt động ổn định hoặc nghiệm thu nhà cung cấp.</p>
   <fieldset disabled={busy||status.write_enabled||status.autopilot_enabled}><legend>Cấu hình bản cài máy chủ · installation_local</legend>
    <div className="st-meta-app-grid">
     <label>App ID<input aria-label="Meta App ID" value={appId} onChange={event=>{edit();setAppId(event.target.value);setSecret('')}} maxLength={64} inputMode="numeric" autoComplete="off"/></label>
     <label>Phiên bản Graph API<input aria-label="Phiên bản Meta Graph API" value={version} onChange={event=>{edit();setVersion(event.target.value)}} maxLength={16} placeholder="vNN.N" autoComplete="off"/></label>
     <label className="wide">App Secret<input aria-label="Meta App Secret" type="password" autoComplete="new-password" spellCheck={false} value={secret} onChange={event=>{edit();setSecret(event.target.value)}} maxLength={256} placeholder={status.secret_present?'Để trống giữ khóa cùng App ID; đổi App cần khóa mới':'Nhập khóa mới tại biểu mẫu này'}/></label>
     <label className="wide">Địa chỉ nhận kết quả OAuth<input aria-label="Meta Địa chỉ nhận kết quả OAuth" type="url" value={callback} onChange={event=>{edit();setCallback(event.target.value)}} maxLength={512} autoComplete="off"/></label>
    </div>
    <button type="button" onClick={()=>{edit();setCallback(window.location.origin+'/v1/integrations/meta/callback')}}>Dùng địa chỉ PAO đang mở</button>
    <p>địa chỉ nhận kết quả phải khớp URI đăng ký trong Meta App và máy chủ/cổng mở PAO. phiên bản lấy từ cấu hình App; biểu mẫu không tự chọn phiên bản mới nhất. Không dùng khóa từng gửi qua chat.</p>
    <label className="st-meta-app-confirm"><input aria-label="Đồng ý lưu ứng dụng Meta máy chủ" type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>Tôi hiểu cấu hình này áp dụng cho bản cài hiện tại và chỉ bật Meta đọc dữ liệu.</label>
    <button type="submit" disabled={busy||!confirmed||status.write_enabled||status.autopilot_enabled}>Lưu Meta App chỉ đọc</button>
   </fieldset>
   {status.restart_required&&<p role="note">Bản lưu khác cấu hình vận hành. Cần quản trị viên nạp lại API và tiến trình xử lý; chưa sẵn sàng OAuth. Không nạp lại chỉ vì một lần đọc GET lỗi.</p>}
   <small>khóa bí mật chỉ ở bộ nhớ password biểu mẫu, xóa khi bắt đầu thao tác, validation lỗi, đọc lại, đổi App ID, rời trang/ẩn tab hoặc đổi doanh nghiệp/role. Không bộ nhớ trình duyệt/URL/log; không hứa zeroize mọi bản sao JS/network. Backend lưu .env riêng và giữ quyền/đối chiếu phiên bản/key hiện có; không đưa .env vào Git/backup source chia sẻ.</small>
  </form>}
  <p>Không tự disconnect, OAuth, đồng bộ, đổi master encryption key hoặc restart để làm xanh. Thao tác lưu có thể bật META_ENABLED và đặt các write/autopilot flags về false theo contract native; chỉ sau xác nhận. Google/Telegram máy chủ config không được thêm biểu mẫu khóa bí mật giả ở bước này.</p>
 </section>;
}
