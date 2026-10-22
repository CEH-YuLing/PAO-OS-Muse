'use client';
import {useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {chatEffortLabels} from '@/lib/chat-model-catalog.mjs';
import {museStatus, museError, museLogin, type MuseView,type MuseLogin} from '@/lib/muse-client.mjs';

export default function MuseConnect(){
 const {apiRaw,activeWorkspace:workspace,me}=usePao(),epoch=useRef(0);
 const [view,setView]=useState<MuseView|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[refresh,setRefresh]=useState(0);
 const [login,setLogin]=useState<MuseLogin|null>(null);
 const scope=`${workspace?.id||''}:${me?.id||''}`,base=`/v1/muse-client?workspace_id=${workspace?.id||''}`;
 useEffect(()=>{const ticket=++epoch.current,controller=new AbortController();setView(null);setLogin(null);setBusy(false);setError('');
  if(workspace?.id)void apiRaw(base,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])})
   .then(response=>response.json()).then(value=>{if(ticket===epoch.current)setView(museStatus(value))})
   .catch(()=>{if(ticket===epoch.current&&!controller.signal.aborted)setError('Chưa tải được kết nối Muse. Hãy làm mới; PAO chưa tự kết nối hoặc gọi model.');});
  return()=>{epoch.current++;controller.abort()};
 },[apiRaw,base,scope,workspace?.id,refresh]);
 useEffect(()=>{if(login?.status!=='pending')return;let live=true;const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;
  const poll=async()=>{try{const response=await apiRaw(`/v1/muse-client/login?workspace_id=${workspace?.id}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])});const next=museLogin(await response.json());if(!live)return;setLogin(next);if(next.status==='granted'){setError('Đăng nhập Muse thành công. Bấm Kiểm tra lại Muse để lưu danh mục từ profile PAO.');return}if(next.status!=='pending')return;}catch{if(!live)return;setError('Chưa đọc được tiến trình đăng nhập. Không đăng nhập lại nhiều lần; chờ hoặc chủ động hủy.');}if(live)timer=setTimeout(()=>void poll(),2000)};
  timer=setTimeout(()=>void poll(),2000);return()=>{live=false;controller.abort();clearTimeout(timer)};
 },[login?.status,apiRaw,workspace?.id,scope]);
 async function change(disconnect=false){
  if(!view||busy||!view.can_manage)return;
  if(disconnect&&!window.confirm('Ngắt kết nối Muse trong PAO? Tài khoản Muse trên máy và các ứng dụng khác vẫn được giữ nguyên.'))return;
  const ticket=epoch.current;setBusy(true);setError('');
  try{
   if(!disconnect&&view.account_state!=='accountLogin'&&login?.status!=='granted'){
    const response=await apiRaw(`/v1/muse-client/login?workspace_id=${workspace?.id}`,{method:'POST',signal:AbortSignal.timeout(35000)});
    const flow=museLogin(await response.json());if(ticket===epoch.current)setLogin(flow);
    if(flow.status!=='granted')return;
   }
   const response=await apiRaw(base,{method:disconnect?'DELETE':'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(35000),
    body:JSON.stringify({request_key:crypto.randomUUID(),expected_revision:view.revision})});
   const value=museStatus(await response.json());if(ticket===epoch.current){setView(value);window.dispatchEvent(new Event('pao:ai-resources'));}}
  catch(reason){if(ticket===epoch.current)setError(museError((reason as Error).message))}
  finally{if(ticket===epoch.current)setBusy(false)}
 }
 return <div aria-label="Kết nối Muse">
  {!view&&!error&&<p role="status">Đang đọc cấu hình Muse đã lưu…</p>}
  {view&&<><p role="status">{view.inference_enabled?'Muse sẵn sàng để chọn trong PAO AI':view.connected?'Đã kết nối danh mục Muse · chưa bật hội thoại':'Chưa kết nối Muse trong PAO'}</p>
   {view.connected&&<><p>{view.account_state==='accountLogin'?'Client ghi nhận phiên đăng nhập chính chủ.':view.account_state==='loggedOut'?'Client chưa đăng nhập. Mở Muse và đăng nhập chính chủ.':'Client đang dùng API key; PAO chưa xác minh cách tính phí.'} {view.models.length} mô hình.</p>
    <details><summary>Mô hình và mức suy luận từ Muse</summary>{view.models.map(row=><p key={row.model}><strong>{row.display_name}</strong><br/>{row.reasoning_efforts.map(value=>chatEffortLabels[value]||value).join(' · ')||'Chưa công bố mức suy luận'}{row.default_effort?` · Mặc định: ${chatEffortLabels[row.default_effort]||row.default_effort}`:''}</p>)}</details>
    <p>Kiểm tra lần cuối: {view.observed_at?new Date(view.observed_at).toLocaleString('vi-VN'):'Chưa xác minh'}. Đây không phải trạng thái realtime hoặc bằng chứng còn quota.</p></>}
   <button type="button" aria-label="Kết nối Muse" disabled={busy||!view.can_manage||login?.status==='pending'} onClick={()=>void change()}>{busy?'Đang xử lý…':view.connected||login?.status==='granted'?'Kiểm tra lại Muse':'Kết nối Muse'}</button>
   {view.connected&&view.can_manage&&<button type="button" disabled={busy} onClick={()=>void change(true)}>Ngắt Muse khỏi PAO</button>}
   {!view.can_manage&&<small>Quản trị bản cài kết nối một lần; không cần cấp quyền AI riêng cho từng nhân sự.</small>}
  </>}
  {login?.status==='pending'&&<section aria-label="Đăng nhập Muse chính chủ"><p>Đăng nhập một lần cho profile PAO riêng. Không nhập mật khẩu hoặc token vào PAO.</p><p>Mã xác nhận: <strong>{login.user_code}</strong></p><a href={login.verification_url} target="_blank" rel="noreferrer">Mở trang đăng nhập Muse chính chủ</a><button type="button" disabled={busy} onClick={()=>{const ticket=epoch.current;setBusy(true);void apiRaw(`/v1/muse-client/login?workspace_id=${workspace?.id}`,{method:'DELETE'}).then(response=>response.json()).then(value=>{if(ticket===epoch.current)setLogin(museLogin(value))}).catch(()=>{if(ticket===epoch.current)setError('Chưa xác nhận được việc hủy. Hãy đọc lại trạng thái.')}).finally(()=>{if(ticket===epoch.current)setBusy(false)})}}>Hủy đăng nhập Muse</button></section>}
  {login&&['failed','expired','cancelled'].includes(login.status)&&<p role="status">{login.status==='expired'?'Mã đăng nhập đã hết hạn.':login.status==='cancelled'?'Đã hủy đăng nhập Muse.':'Chưa hoàn tất đăng nhập Muse.'} Bạn có thể chủ động kết nối lại.</p>}
  {error&&<p role="alert">{error}</p>}
  <button type="button" disabled={busy} onClick={()=>setRefresh(value=>value+1)}>Đọc lại trạng thái đã lưu</button>
  <details><summary>Hướng dẫn cài đặt và giới hạn hiện tại</summary>
   <p>Muse Code cần được cài trên máy chạy backend PAO, không phải trên từng máy nhân viên. Kết nối dùng profile riêng đã chốt cho PAO; bạn đăng nhập chính chủ một lần. PAO không sao chép token, phiên chat hoặc hook từ profile Muse cũ.</p>
   <p>Kết nối xác thực được công bố vào tài nguyên AI dùng chung, không thay model mặc định cũ. Chọn Muse và mức suy luận trong PAO AI hoặc cấu hình trợ lý/công việc; chỉ gửi yêu cầu mới tiêu hạn mức. Bộ kết nối chỉ xử lý văn bản, không dùng công cụ native hay tạo ảnh trực tiếp. Không tự dùng API trả phí khi quota hết.</p>
   <p>Muse có hướng dẫn native riêng nên tiêu thêm khoảng 14.000 token đầu vào mỗi lần gọi dù nội dung ngắn. Áp dụng Muse trong hội thoại có thông báo nâng giới hạn ngữ cảnh/ngân sách; công việc vẫn phải nằm trong giới hạn đã duyệt. Dừng tác vụ không hoàn lại quota đã tiêu. Token đo được không phải hạn mức thuê bao còn lại.</p>
   <p>Nếu CLI cập nhật, PAO cần kiểm tra phiên bản/chữ ký/schema mới. Nếu hết phiên, đăng nhập lại trong Muse rồi bấm Kiểm tra lại. Ngắt tại đây chỉ ngắt PAO, không đăng xuất Muse hoặc xóa cấu hình khác.</p>
   <p>Gói thuê bao và API key có cách tính phí khác nhau. Contributor mode có thể cho phép Meta dùng nội dung để huấn luyện; kiểm tra lựa chọn trong Muse trước khi gửi dữ liệu doanh nghiệp thật.</p>
  </details>
 </div>;
}
