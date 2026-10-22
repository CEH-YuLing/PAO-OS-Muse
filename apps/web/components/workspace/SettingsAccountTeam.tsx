"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {settingsLabel} from '@/lib/settings-vi';
import {usePao} from '@/lib/PaoRuntimeContext';
import {settingsTeam,type SettingsTeam} from '@/lib/settings-team.mjs';


export default function SettingsAccountTeam({onConnections,view='account'}:{onConnections:()=>void;view?:'account'|'permissions'}){
 const {apiRaw,me,activeWorkspace:member}=usePao(),workspace=member?.id||'',managing=member?.role==='owner'||member?.role==='admin';
 const epoch=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null);
 const [snapshot,setSnapshot]=useState<SettingsTeam|null>(null),[busy,setBusy]=useState(false),[failed,setFailed]=useState(false),[observed,setObserved]=useState('');
 const load=useCallback(async()=>{
  if(lock.current)return;
  setSnapshot(null);setFailed(false);setObserved('');if(!workspace||!managing||view!=='permissions')return;
  const ticket=++epoch.current,controller=new AbortController();abort.current=controller;lock.current=true;setBusy(true);
  try{
   const response=await apiRaw(`/v1/workspaces/${workspace}/connection-inventory/options`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
   const value=settingsTeam(await response.json());if(ticket!==epoch.current||controller.signal.aborted)return;
   setSnapshot(value);setObserved(new Date().toLocaleString('vi-VN'));
  }catch{if(ticket===epoch.current)setFailed(true)}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[apiRaw,workspace,managing,view]);
 useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=lock;void load();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false}},[load]);
 return <section className="st-account-team" aria-label="Tài khoản và đội ngũ doanh nghiệp">
  <header><h2>{view==='account'?'Tài khoản của tôi':'Quyền truy cập kết nối'}</h2>{managing&&view==='permissions'&&<button type="button" onClick={()=>void load()} disabled={busy}>Đọc lại đội ngũ</button>}</header>
  {view==='account'&&<div className="st-account-grid">
   <section aria-label="Tài khoản cá nhân"><h3>Tài khoản cá nhân</h3><dl><div><dt>Email đăng nhập</dt><dd>{me?.email}</dd></div><div><dt>Mã tài khoản</dt><dd>{me?.id}</dd></div><div><dt>doanh nghiệp trong phiên đăng nhập</dt><dd>{me?.workspaces.length||0}</dd></div></dl><p>Một tài khoản có thể thuộc nhiều doanh nghiệp. Danh sách này là dữ liệu vừa đọc phiên đăng nhập, không gộp dữ liệu, bộ nhớ hoặc quyền của các doanh nghiệp.</p></section>
   <section aria-label="Vai trò trong doanh nghiệp"><h3>doanh nghiệp đang làm việc</h3><dl><div><dt>Doanh nghiệp</dt><dd>{member?.name}</dd></div><div><dt>Mã doanh nghiệp</dt><dd>{workspace}</dd></div><div><dt>Vai trò trong phiên</dt><dd>{settingsLabel(member?.role||'')}</dd></div></dl><p>Vai trò có thể khác ở từng doanh nghiệp. Máy chủ kiểm tra lại quyền tại mỗi yêu cầu; dữ liệu vừa đọc phiên không bảo đảm quyền hiện tại. chủ doanh nghiệp/quản trị viên cũng không mặc nhiên đọc kho tri thức riêng hoặc kết nối của người khác.</p></section>
  </div>}
  {view==='permissions'&&(managing?<>
   <h3>Danh sách đủ điều kiện cấp quyền kết nối</h3><p>Bộ lọc này chỉ trả thành viên đang hiệu lực ở vai trò chủ doanh nghiệp/quản trị viên/người thực thi/người phân tích và nhãn hàng; không phải danh bạ đầy đủ. Chủ doanh nghiệp dùng khu vực quản lý tài khoản bên dưới để mời, đổi vai trò hoặc gỡ thành viên.</p>
   {busy&&<p role="status">Đang đọc thông tin mô tả đội ngũ…</p>}
   {failed&&<p role="alert">Chưa xác minh đội ngũ. dữ liệu vừa đọc cũ đã bỏ; kiểm tra quyền/API rồi bấm Đọc lại đội ngũ. Không hiển thị dữ liệu của doanh nghiệp trước hoặc tự thử lại.</p>}
   {snapshot&&<><p role="note">Đọc lúc {observed} · {snapshot.members.length} thành viên / {snapshot.brands.length} nhãn hàng trong kết quả. {snapshot.has_more?'Kết quả bị giới hạn tối đa 100 mỗi nhóm; has_more chung không chỉ ra nhóm thiếu, API này chưa có phân trang. Không coi là danh sách đầy đủ.':'Chỉ đầy đủ trong bộ lọc đủ điều kiện của API ở lần đọc này.'}</p>
    <ul aria-label="Thành viên đủ điều kiện">{snapshot.members.map(row=><li key={row.id}><strong>{row.email}</strong><span>{settingsLabel(row.role)}{row.id===me?.id?' · bạn':''}</span><small>{row.id}</small></li>)}</ul>
    {!snapshot.members.length&&<p>Không có thành viên đủ điều kiện trong kết quả.</p>}
    <ul aria-label="Nhãn hàng trong kết quả">{snapshot.brands.map(row=><li key={row.id}><strong>{row.name}</strong><small>{row.id}</small></li>)}</ul>
    {!snapshot.brands.length&&<p>Chưa có nhãn hàng trong kết quả; không tự tạo nhãn hàng.</p>}
   </>}
  </>:<p role="note">Vai trò {settingsLabel(member?.role||'')} không có quyền đọc danh sách quản lý đội ngũ qua API này. Chỉ hiển thị tài khoản/vai trò của bạn; không gọi API quản lý hoặc dùng quyền chủ doanh nghiệp của doanh nghiệp khác.</p>)}

  <h3>Quyền kết nối không phải quyền toàn bộ doanh nghiệp</h3><p>Mapping chờ kích hoạt, consent đã ghi, phiên bản kết nối, thời hạn, thành viên, nhãn hàng và đúng tài khoản Ads là các chốt riêng. Consent đã ghi không chứng minh quyền được cấp vẫn dùng được; backend kiểm tra lại lúc chạy. Quyền mô hình không cấp quyền công cụ, Ads, kho tri thức hoặc chi tiền. Không gắn nhãn hàng không phải quyền cho mọi nhãn hàng.</p>
  <button type="button" onClick={onConnections}>Xem kết nối và quyền theo doanh nghiệp</button><p>Thao tác này chỉ đổi tab. Chỉ xem hoặc thao tác quyền được cấp trong các panel hiện có sau khi kiểm tra đúng ngữ cảnh và xác nhận; không tự kích hoạt.</p>
 </section>;
}
