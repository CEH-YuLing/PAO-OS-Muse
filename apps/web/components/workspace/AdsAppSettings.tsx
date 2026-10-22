"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {appStatus,appPayload,appError,type AppStatus} from '@/lib/ads-app-settings.mjs';
import {adsHelp,type AdsProvider} from '@/lib/ads-settings.mjs';

export default function AdsAppSettings({provider:selectedProvider}:{provider?:AdsProvider}){
 const {activeWorkspace:member}=usePao();
 return <section className="ads-settings" aria-label="Ứng dụng quảng cáo theo doanh nghiệp"><h2>Ứng dụng {selectedProvider?adsHelp[selectedProvider].name:'Meta/Google'} của {member?.name}</h2>
 <p>Dùng ứng dụng PAO là mặc định. Chế độ nâng cao dùng ứng dụng riêng của doanh nghiệp; token cấp bởi người dùng vẫn tách theo từng doanh nghiệp và tài khoản PAO.</p>
 <div className="ads-settings-grid">{member&&(selectedProvider?[selectedProvider]:['meta','google'] as AdsProvider[]).map(provider=><AppForm key={member.id+':'+member.role+':'+provider} workspace={member.id} provider={provider} manage={member.role==='owner'||member.role==='admin'}/>)}</div></section>;
}

function AppForm({workspace,provider,manage}:{workspace:string;provider:AdsProvider;manage:boolean}){
 const {apiRaw}=usePao(),name=adsHelp[provider].name,base=adsHelp[provider].base+'/tenant-app?workspace_id='+workspace;
 const epoch=useRef(0),lock=useRef(false),controller=useRef<AbortController|null>(null),secret=useRef<HTMLInputElement>(null),developer=useRef<HTMLInputElement>(null);
 const [status,setStatus]=useState<AppStatus|null>(null),[mode,setMode]=useState<'managed'|'byo'>('managed'),[clientId,setId]=useState(''),[version,setVersion]=useState(''),[login,setLogin]=useState(''),[ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const wipe=useCallback(()=>{if(secret.current)secret.current.value='';if(developer.current)developer.current.value='';setAck(false)},[]);
 const fill=useCallback((value:AppStatus)=>{setStatus(value);setMode(value.mode);setId(value.mode==='byo'?value.client_id:'');setVersion(value.api_version);setLogin(value.mode==='byo'?value.login_customer_id:'');wipe()},[wipe]);
 const read=useCallback(async()=>{
  if(lock.current)return;lock.current=true;const ticket=++epoch.current,abort=new AbortController();controller.current=abort;wipe();setStatus(null);setBusy(true);setError('');setNotice('');
  try{const r=await apiRaw(base,{signal:AbortSignal.any([abort.signal,AbortSignal.timeout(15000)])});const value=appStatus(await r.json(),workspace,provider);if(ticket===epoch.current&&!abort.signal.aborted)fill(value)}
  catch(reason){if(ticket===epoch.current)setError(appError((reason as Error).message))}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[apiRaw,base,workspace,provider,fill,wipe]);
 useEffect(()=>{const e=epoch,c=controller,l=lock;void read();return()=>{e.current++;c.current?.abort();l.current=false}},[read]);
 useEffect(()=>{const hidden=()=>{if(document.hidden)wipe()};document.addEventListener('visibilitychange',hidden);window.addEventListener('pagehide',wipe);return()=>{document.removeEventListener('visibilitychange',hidden);window.removeEventListener('pagehide',wipe)}},[wipe]);
 async function save(event:React.FormEvent){
  event.preventDefault();if(lock.current||!manage||!status||!ack)return;
  let payload:Record<string,unknown>;
  try{payload=appPayload(status,{mode,clientId,secret:secret.current?.value||'',apiVersion:version,developerToken:developer.current?.value||'',loginId:login})}
  catch(reason){wipe();setError(appError((reason as Error).message));return}
  if(!window.confirm('Đổi ứng dụng '+name+' của doanh nghiệp này? Toàn bộ kết nối '+name+' trong doanh nghiệp sẽ bị ngắt, phiên OAuth và công việc cũ bị vô hiệu. Cần kết nối và cấp quyền lại. Không ảnh hưởng doanh nghiệp khác.')){wipe();return}
  lock.current=true;const ticket=++epoch.current,abort=new AbortController();controller.current=abort;wipe();setBusy(true);setError('');setNotice('');
  try{const r=await apiRaw(base,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.any([abort.signal,AbortSignal.timeout(20000)])});const value=appStatus(await r.json(),workspace,provider);if(ticket===epoch.current&&!abort.signal.aborted){fill(value);setNotice('Đã lưu cấu hình, chưa xác thực tài khoản thật. Bấm Đọc lại trạng thái Ads ở dưới rồi kết nối OAuth mới. Không tự bật quảng cáo hoặc khởi chạy công việc.')}}
  catch(reason){if(ticket===epoch.current){setStatus(null);setError(appError((reason as Error).message))}}
  finally{payload={};if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 }
 return <article data-testid={'ads-app-'+provider} aria-label={'Ứng dụng '+name}><h3>{name}</h3>
 <button type="button" disabled={busy} onClick={()=>void read()}>Đọc lại cấu hình {name}</button>
 <p>{status?`Phiên bản ${status.revision} · ${status.mode==='managed'?'Ứng dụng PAO':'Ứng dụng riêng'} · ${status.secret_present?'Có khóa được lưu':'Chưa có khóa'} · ${status.platform_enabled?'Chốt nền tảng đang bật':'Chốt nền tảng đang tắt'}`:'Chưa xác minh cấu hình'}</p>
 <p>Lưu không gọi nhà cung cấp, không xác nhận ứng dụng đã được xét duyệt. Chốt nền tảng do quản trị máy chủ quyết định; lựa chọn doanh nghiệp không vượt chốt này.</p>
 {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 <details><summary>Hướng dẫn ứng dụng {name}</summary><ol>
 <li>Chọn đúng doanh nghiệp. Chỉ chủ doanh nghiệp/quản trị viên đổi cấu hình; quyền dùng tài khoản quảng cáo và quyền chi tiền là các quyền riêng.</li>
 <li>Mặc định chọn ứng dụng PAO, không nhập App Secret. Nếu chưa sẵn sàng, nhờ quản trị máy chủ cấu hình và kiểm xét duyệt.</li>
 <li>Nâng cao: {provider==='meta'?'lấy App ID và App Secret trong Meta for Developers, cài Facebook Login và Marketing API theo use case được phép.':'tạo OAuth Client kiểu Web application trong Google Cloud, bật Google Ads API và hoàn tất OAuth consent/API access. Client ID kết thúc bằng .apps.googleusercontent.com; không dùng Gemini key.'}</li>
 <li>Đăng ký chính xác địa chỉ nhận kết quả ở dưới tại nhà cung cấp. Do máy chủ quản lý, không nhập URL khác; localhost khác 127.0.0.1. Production cần HTTPS và domain hợp lệ.</li>
 <li>Nhập khóa mới trong trường bí mật và chọn phiên bản API được hỗ trợ; không sao chép token người dùng. Lưu làm ngắt các kết nối hiện tại của doanh nghiệp, không gọi OAuth tự động.</li>
 <li>Đọc lại trạng thái Ads, mở OAuth, chọn đúng tài khoản nhà cung cấp, rồi đồng bộ danh mục/chọn tài khoản và cấp quyền nhãn hàng/nhân viên bên dưới. Google dùng phạm vi adwords, PAO vẫn giới hạn thao tác theo quyền; ưu tiên cấp tài khoản Google Ads chỉ đọc.</li>
 <li>Đổi khóa/chế độ cần nhập lại đầy đủ thông tin, kết nối OAuth và cấp quyền phiên bản mới. Ngắt bản lưu PAO không thu hồi ứng dụng tại Meta/Google; muốn thu hồi tại nhà cung cấp phải thực hiện riêng.</li>
 </ol><a href={adsHelp[provider].url} target="_blank" rel="noopener noreferrer">Tài liệu chính thức {name}</a></details>
 {status&&<p>Địa chỉ nhận kết quả cố định: <code style={{overflowWrap:'anywhere'}}>{status.redirect_uri}</code></p>}
 {manage?<form onSubmit={save}><fieldset disabled={busy||!status}><legend>Thiết lập ứng dụng {name}</legend>
 <label>Phương thức <select aria-label={'Phương thức ứng dụng '+name} value={mode} onChange={e=>{wipe();setMode(e.target.value as 'managed'|'byo');setId('');setLogin('')}}><option value="managed">Dùng ứng dụng PAO — mặc định</option><option value="byo">Ứng dụng riêng — nâng cao</option></select></label>
 {mode==='byo'&&<><label>{provider==='meta'?'App ID':'OAuth Client ID'}<input aria-label={'Mã ứng dụng '+name} value={clientId} maxLength={256} autoComplete="off" onChange={e=>setId(e.target.value)}/></label>
 <label>{provider==='meta'?'App Secret mới':'OAuth Client Secret mới'}<input ref={secret} aria-label={'Khóa ứng dụng '+name} type="password" autoComplete="new-password" maxLength={512}/></label>
 <label>Phiên bản API<input aria-label={'Phiên bản API '+name} value={version} maxLength={16} placeholder={provider==='meta'?'v26.0':'v25'} onChange={e=>setVersion(e.target.value)}/></label>
 {provider==='google'&&<><label>Developer token — tùy điều kiện API access<input ref={developer} aria-label="Developer token Google Ads" type="password" autoComplete="new-password" maxLength={512}/></label><p>Giữ trống nếu Cloud project được phép gọi API không cần developer token; không có nghĩa bỏ qua kiểm duyệt. Không lấy token chung máy chủ để dự phòng cho ứng dụng riêng.</p>
 <label>Mã tài khoản quản lý — tùy chọn<input aria-label="Mã quản lý Google Ads" value={login} maxLength={10} inputMode="numeric" onChange={e=>setLogin(e.target.value)}/></label><p>10 chữ số, không dấu gạch; là manager root, không phải customer đích.</p></>}
 </>}
 <label><input type="checkbox" aria-label={'Đồng ý đổi ứng dụng '+name} checked={ack} onChange={e=>setAck(e.target.checked)}/>Tôi hiểu thay đổi sẽ ngắt các kết nối {name} của doanh nghiệp này, vô hiệu phiên/công việc cũ và cần kết nối lại.</label>
 <button type="submit" disabled={!ack}>Lưu ứng dụng {name}</button></fieldset></form>:<p>Bạn không có quyền thay ứng dụng. Nhờ chủ doanh nghiệp/quản trị viên cấu hình; không cần chia sẻ khóa cho nhân viên.</p>}
 </article>;
}
