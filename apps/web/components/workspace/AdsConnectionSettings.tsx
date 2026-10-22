"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {settingsLabel} from '@/lib/settings-vi';
import {usePao} from '@/lib/PaoRuntimeContext';
import {adsHelp,adsStatus,adsOAuthUrl,adsAccounts,adsJobs,adsSettingsError,type AdsProvider,type AdsConnection,type AdsAccount,type AdsJob} from '@/lib/ads-settings.mjs';
import ConnectionEvidence from './ConnectionEvidence';
import './ads-settings.css';
const providers:AdsProvider[]=['meta','google'];
const metaOnly:AdsProvider[]=['meta'],googleOnly:AdsProvider[]=['google'];
type Action='oauth'|'disconnect'|'accounts'|'jobs';
export default function AdsConnectionSettings({provider:selectedProvider}:{provider?:AdsProvider}){
 const selectedProviders=selectedProvider==='meta'?metaOnly:selectedProvider==='google'?googleOnly:providers;
 const {apiRaw,activeWorkspace:member}=usePao(),workspace=member?.id||'',manage=member?.role==='owner'||member?.role==='admin';
 const epoch=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null),popup=useRef<Window|null>(null);
 const [rows,setRows]=useState<Partial<Record<AdsProvider,AdsConnection>>>({}),[busy,setBusy]=useState(false),[opened,setOpened]=useState(false);
 const [oauthAck,setOauthAck]=useState<Partial<Record<AdsProvider,boolean>>>({}),[removeAck,setRemoveAck]=useState<Partial<Record<AdsProvider,boolean>>>({});
 const [accounts,setAccounts]=useState<Partial<Record<AdsProvider,AdsAccount[]>>>({}),[selection,setSelection]=useState<Partial<Record<AdsProvider,string>>>({}),[jobs,setJobs]=useState<Partial<Record<AdsProvider,AdsJob[]>>>({});
 const [errors,setErrors]=useState<Partial<Record<AdsProvider,string>>>({}),[notice,setNotice]=useState('');
 const clear=useCallback(()=>{setOauthAck({});setRemoveAck({});setAccounts({});setSelection({});setJobs({})},[]);
 const close=useCallback(()=>{try{popup.current?.close()}catch{}popup.current=null;setOpened(false)},[]);
 const read=useCallback(async(ticket:number,controller:AbortController)=>{
  const results=await Promise.allSettled(selectedProviders.map(async provider=>adsStatus(provider,await (await apiRaw(adsHelp[provider].base+'/connection?workspace_id='+workspace,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])})).json())));
  if(ticket!==epoch.current||controller.signal.aborted)return false;
  const fresh:Partial<Record<AdsProvider,AdsConnection>>={},failed:Partial<Record<AdsProvider,string>>={};
  results.forEach((result,index)=>{const provider=selectedProviders[index];if(result.status==='fulfilled')fresh[provider]=result.value;else failed[provider]=adsSettingsError(result.reason?.message||'')});setRows(fresh);setErrors(failed);return true;
 },[apiRaw,workspace,selectedProviders]);
 const refresh=useCallback(async()=>{
  if(lock.current||!workspace)return;lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  close();clear();setRows({});setErrors({});setNotice('');setBusy(true);
  try{await read(ticket,controller)}finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[workspace,read,close,clear]);
 useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=lock,currentPopup=popup;void refresh();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false;try{currentPopup.current?.close()}catch{}currentPopup.current=null}},[refresh]);
 useEffect(()=>{const hide=()=>{if(document.hidden){setOauthAck({});setRemoveAck({});setSelection({})}},leave=()=>{setOauthAck({});setRemoveAck({});setSelection({})};document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',leave);return()=>{document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',leave)}},[]);
 async function work(provider:AdsProvider,action:Action){
  const row=rows[provider];if(lock.current||!manage||!row||opened)return;
  if(action==='oauth'&&(!row.configured||!oauthAck[provider])||action==='disconnect'&&(!removeAck[provider]||row.status==='disconnected'))return;
  if(action==='disconnect'&&!window.confirm('Ngắt '+adsHelp[provider].name+' của tài khoản này trong '+member?.name+'? Xóa token PAO và hủy các công việc đang chờ/chạy; không thu hồi tại nhà cung cấp.'))return;
  let target:Window|null=null;
  if(action==='oauth'){
   target=window.open('about:blank','pao-oauth-'+crypto.randomUUID(),'popup,width=720,height=780');
   if(!target){setOauthAck({});setErrors(old=>({...old,[provider]:adsSettingsError('ads_popup_blocked')}));return}
   try{target.opener=null;const meta=target.document.createElement('meta');meta.name='referrer';meta.content='no-referrer';target.document.head.appendChild(meta)}catch{target.close();setErrors(old=>({...old,[provider]:adsSettingsError('ads_popup_blocked')}));return}
   popup.current=target;setOpened(true);
  }
  lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setBusy(true);setErrors(old=>({...old,[provider]:undefined}));setNotice('');
  const base=adsHelp[provider].base,query='?workspace_id='+workspace;
  try{
   const path=action==='oauth'?base+'/oauth/start'+query:action==='disconnect'?base+'/connection'+query:action==='jobs'?base+'/jobs'+query:provider==='meta'?base+'/snapshots'+query+'&kind=accounts':base+'/accounts'+query;
   const response=await apiRaw(path,{method:action==='oauth'?'POST':action==='disconnect'?'DELETE':'GET',signal:AbortSignal.any([controller.signal,AbortSignal.timeout(20000)])});
   const value=response.status===204?undefined:await response.json();
   if(ticket!==epoch.current||controller.signal.aborted)return;
   if(action==='oauth'){
    const url=adsOAuthUrl(provider,value,window.location.origin);if(!target||target.closed)throw new Error('ads_popup_closed');target.location.replace(url);
    setNotice('Đã mở OAuth; chưa xác nhận kết nối. Hoàn tất trong popup rồi bấm Đọc lại trạng thái Ads. Đóng popup không hủy địa chỉ nhận kết quả đã chạy hoặc phiên máy chủ còn hạn.');return;
   }
   if(action==='accounts'){setAccounts({[provider]:adsAccounts(provider,value)});setNotice(provider==='meta'&&value.has_more?'danh mục Meta còn trang khác; đây chỉ tối đa50 tài khoản đã lưu, không phải toàn bộ tài sản.':'Đã đọc tài khoản đã lưu của kết nối này, không gọi nhà cung cấp. Chọn tài khoản chỉ để xem ID; không lưu đích hoặc cấp quyền được cấp.')}
   if(action==='jobs'){setJobs({[provider]:adsJobs(value)});setNotice('20 công việc gần nhất của kết nối tài khoản này; thông tin mô tả cũ không chứng minh nhà cung cấp hoạt động ổn định. chưa rõ kết quả không được tự chạy lại.')}
   if(action==='disconnect'){close();if(await read(ticket,controller))setNotice('Đã ngắt bản lưu PAO và hủy native công việc. thu hồi quyền ứng dụng tại Meta/Google riêng; quyền được cấp/công việc cũ không tự sống lại.')}
  }catch(reason){if(ticket===epoch.current){close();clear();setRows(old=>{const next={...old};delete next[provider];return next});setErrors(old=>({...old,[provider]:adsSettingsError((reason as Error).message)}))}}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 }
 return <section className="ads-settings" aria-label="Cài đặt kết nối quảng cáo">
  <h2>Kết nối {selectedProvider?adsHelp[selectedProvider].name:'Ads'} · {member?.name}</h2><p>Kết nối OAuth riêng của tài khoản đang đăng nhập trong doanh nghiệp, dùng ứng dụng PAO hoặc ứng dụng riêng đã chọn ở trên. Sau khi đổi ứng dụng, đọc lại trạng thái rồi kết nối OAuth mới. Không nhập access/refresh token tại đây, không bật quyền ghi quảng cáo.</p>
  <button type="button" disabled={busy} onClick={()=>void refresh()}>Đọc lại trạng thái Ads</button>
  {opened&&<button type="button" disabled={busy} onClick={close}>Đóng cửa sổ OAuth</button>}
  {notice&&<p role="status">{notice}</p>}
  <div className="ads-settings-grid">{selectedProviders.map(provider=>{const row=rows[provider],help=adsHelp[provider];return <article key={provider} aria-label={help.name+' connection status'}>
   <h3>{help.name}</h3><span>{row?settingsLabel(row.status):'Chưa xác minh'}</span><ConnectionEvidence kind={provider} record={row||null}/>
   <p>Ứng dụng được chọn cho doanh nghiệp {row?row.configured?'đủ cấu hình và chốt nền tảng':'chưa sẵn sàng':'chưa xác minh'} · {row?row.scopes.length:'—'} quyền đã lưu{row?.expires_at?' · thời điểm hết hạn khóa đã lưu: '+row.expires_at:''}.</p>
   <details><summary>Hướng dẫn {help.name}</summary><p>{help.text}</p><p>OAuth cần địa chỉ nhận kết quả khớp chính xác địa chỉ PAO đang mở và URI đăng ký tại nhà cung cấp; localhost và127.0.0.1 không tự thay thế nhau. Chọn đúng tài khoản/tài sản trước cấp quyền. Không dùng khóa bí mật từng gửi qua chat.</p><a href={help.url} target="_blank" rel="noopener noreferrer">Tài liệu chính thức {help.name}</a>{provider==='google'&&<><p>API access hiện quản lý tại Google Cloud project; API Center/developer token cũ không phải hướng dẫn đăng ký mới. Danh sách accessible customers là quyền trực tiếp, không toàn bộ manager hierarchy.</p><a href="https://developers.google.com/google-ads/api/docs/api-policy/developer-token" target="_blank" rel="noopener noreferrer">API access / developer-token migration</a></>}</details>
   {errors[provider]&&<p role="alert">{errors[provider]}</p>}
   {manage?<fieldset disabled={busy||opened||!row}><legend>Quản lý kết nối của chính mình</legend>
    <label><input aria-label={'Đồng ý OAuth '+help.name} type="checkbox" checked={Boolean(oauthAck[provider])} onChange={e=>setOauthAck(old=>({...old,[provider]:e.target.checked}))}/>Tôi chọn đúng doanh nghiệp/tài khoản và muốn mở OAuth; phạm vi không thay quyền chỉ đọc backend hoặc quyền được cấp.</label>
    <button type="button" disabled={!row?.configured||!oauthAck[provider]} onClick={()=>void work(provider,'oauth')}>{row?.status==='connected'?'Kết nối lại':'Kết nối'}</button>
    <label><input aria-label={'Đồng ý ngắt '+help.name} type="checkbox" checked={Boolean(removeAck[provider])} onChange={e=>setRemoveAck(old=>({...old,[provider]:e.target.checked}))}/>Ngắt bản lưu PAO của doanh nghiệp này, xóa phần lưu token và hủy đang chờ/đang chạy công việc; không thu hồi quyền tại nhà cung cấp.</label>
    <button type="button" disabled={!removeAck[provider]||!row||row.status==='disconnected'} onClick={()=>void work(provider,'disconnect')}>Ngắt bản lưu {help.name}</button>
    <button type="button" disabled={row?.status!=='connected'} onClick={()=>void work(provider,'accounts')}>Đọc tài khoản đã lưu {help.name}</button>
    <button type="button" onClick={()=>void work(provider,'jobs')}>Đọc công việc {help.name}</button>
    {accounts[provider]&&<label>Tài khoản đã lưu {help.name}<select aria-label={'Tài khoản đã lưu '+help.name} value={selection[provider]||''} onChange={e=>setSelection({[provider]:e.target.value})}><option value="">Chọn để xem ID, không cấp quyền</option>{accounts[provider]?.map(account=><option key={account.id} value={account.id}>{account.name} · {account.id} · {account.currency}</option>)}</select></label>}
    {selection[provider]&&<p>Mã tài khoản đang xem: {selection[provider]}. Đích thực thi do quyền được cấp được duyệt ở phần bên dưới quyết định.</p>}
    {jobs[provider]?.map(job=><p key={job.id}>{settingsLabel(job.kind)} · {settingsLabel(job.status)} · {job.row_count} dòng · {job.id}</p>)}
   </fieldset>:<p>Chỉ chủ doanh nghiệp/quản trị viên quản lý OAuth. Nhân viên dùng quyền quảng cáo đã được cấp; không kế thừa quyền chủ ở doanh nghiệp khác.</p>}
  </article>})}</div>
  <p>Refresh/đã lưu accounts/công việc chỉ đọc PAO, không tự tìm danh mục hoặc kiểm tra thử nhà cung cấp. Phiên OAuth state/cookie/phiên bản do backend kiểm; biểu mẫu không thêm client đối chiếu phiên bản/mã một lần vào API không hỗ trợ. Lỗi bỏ dữ liệu vừa đọc của nhà cung cấp, khóa thao tác tới manual refresh; không tự gửi lại. Kết nối/quyền được cấp/kỹ năng/mô hình/kho tri thức không thay thế nhau.</p>
 </section>;
}
