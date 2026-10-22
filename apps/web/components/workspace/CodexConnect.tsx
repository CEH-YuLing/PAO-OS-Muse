'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {Plug,ExternalLink,X} from 'lucide-react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {cliProfileRows,type CliProfile} from '@/lib/model-provider-tabs.mjs';
import {codexLoginPath,codexLoginCapability,codexLoginView,codexLoginLabels,type CodexLogin} from '@/lib/codex-login.mjs';
import {codexModels,codexModelPath} from '@/lib/codex-model-choice.mjs';
import {connectPersonalCodex} from '@/lib/personal-codex-setup.mjs';
import './codex-connect.css';

export default function CodexConnect(){
 const {apiRaw,activeWorkspace,me}=usePao(),workspace=activeWorkspace?.id||'',actor=me?.id||'',manage=['owner','admin'].includes(activeWorkspace?.role||'');
 const [enabled,setEnabled]=useState(false),[open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [rows,setRows]=useState<CliProfile[]>([]),[chosen,setChosen]=useState(''),[model,setModel]=useState(''),[state,setState]=useState<CodexLogin|null>(null);
 const [catalog,setCatalog]=useState<string[]>([]);
 const [chatReady,setChatReady]=useState(false);
 const epoch=useRef(0),revision=useRef(0),abort=useRef<AbortController|null>(null),lock=useRef(false),dialog=useRef<HTMLDialogElement>(null),button=useRef<HTMLButtonElement>(null);
 const current=useRef(state);current.current=state;
 useEffect(()=>{if(state?.status==='connected')window.dispatchEvent(new Event('pao:codex-profile'))},[state?.status]);
 const request=useCallback(async(path:string,method='GET',body?:unknown)=>{
  const controller=abort.current||new AbortController();abort.current=controller;
  const response=await apiRaw(path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,
   signal:AbortSignal.any([controller.signal,AbortSignal.timeout(120000)])});return response.status===204?null:response.json();
 },[apiRaw]);
 useEffect(()=>{
  const generations=epoch,ticket=++generations.current,controller=new AbortController();abort.current=controller;setEnabled(false);
  setState(null);setRows([]);setCatalog([]);setChosen('');setModel('');setOpen(false);setError('');setBusy(false);setChatReady(false);lock.current=false;
  if(manage&&workspace)void request(codexLoginPath(workspace,'','login-capabilities')).then(value=>{if(epoch.current===ticket)setEnabled(codexLoginCapability(value))}).catch(()=>{});
  return()=>{generations.current++;controller.abort()};
 },[workspace,actor,manage,request]);
 useEffect(()=>{if(!open)return;const element=dialog.current,returnFocus=button.current;element?.showModal();return()=>{element?.close();returnFocus?.focus()}},[open]);
 useEffect(()=>{const hide=()=>{if(document.hidden)setState(old=>old?{...old,user_code:null}:old)};document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide)},[]);
 const profiles=async()=>{
  const value=cliProfileRows(await request(codexLoginPath(workspace)),workspace,actor);setRows(value);if(value.length===1)setChosen(value[0].id);return value;
 };
 async function observe(connection:string){const value=codexLoginView(await request(codexLoginPath(workspace,connection,'login')),connection);setState(value);return value}
 async function connectChat(value:CodexLogin){
  const ticket=epoch.current,flow=revision.current;setState(value);setChatReady(false);
  await connectPersonalCodex(request,workspace,actor,value.connection_id,crypto.randomUUID(),()=>ticket===epoch.current&&flow===revision.current);
  if(ticket!==epoch.current||flow!==revision.current)return;
  setChatReady(true);window.dispatchEvent(new Event('pao:ai-resources'));
  try{
   const result=codexModels(await request(codexModelPath(workspace,value.connection_id,'models'),'POST',{version:value.version}),workspace,actor,value.connection_id);
   if(ticket===epoch.current&&flow===revision.current){setCatalog(result.models.map(row=>row.model));window.dispatchEvent(new Event('pao:ai-resources'))}
  }catch{if(ticket===epoch.current&&flow===revision.current)setError('Đã nối hồ sơ Codex nhưng chưa đọc được toàn bộ danh mục. Bấm Đọc danh mục model để thử lại; không tự đổi model hoặc dùng API dự phòng.')}
 }
 async function start(row:CliProfile){
  if(row.status==='connected'&&row.authentication_ready){await connectChat({connection_id:row.id,operation_id:null,version:row.version,status:'connected',expires_in:0,user_code:null,verification_url:null});return}
  if(row.profile_operation_pending){await observe(row.id);return}
  if(!window.confirm(`Đăng nhập Codex riêng cho bạn trong ${activeWorkspace?.name}? Chỉ dùng tài khoản của bạn, không chia thuê bao cho nhân viên. PAO sẽ mở luồng chính thức của OpenAI; chưa chạy AI hoặc cấp quyền công cụ.`))return;
  const ticket=epoch.current;
  const ready=cliProfileRows({items:[await request(codexLoginPath(workspace,row.id,'prepare'),'POST',{version:row.version})],external_calls:false},workspace,actor)[0];
  if(ticket!==epoch.current)return;
  const value=await request(codexLoginPath(workspace,row.id,'login'),'POST',{version:ready.version,request_key:crypto.randomUUID(),allow_personal_login:true});
  if(ticket!==epoch.current)return;
  setState(codexLoginView(value,row.id));
 }
 async function action(fn:()=>Promise<void>){
  if(lock.current||!enabled||!manage)return false;revision.current++;lock.current=true;setBusy(true);setError('');const ticket=epoch.current;
  try{await fn();return true}catch{if(epoch.current===ticket){setState(old=>old?{...old,user_code:null,verification_url:null}:old);setError('Chưa xác nhận được kết quả. Bấm Đọc lại để đối chiếu trước khi thử tiếp; PAO không tự gửi lại. Kiểm tra quyền hoặc Docker nếu lỗi vẫn còn.')}return false}
  finally{if(epoch.current===ticket){lock.current=false;setBusy(false)}}
 }
 async function connect(){setOpen(true);setCatalog([]);setChatReady(false);await action(async()=>{setState(null);const list=await profiles();if(list.length===1)await start(list[0])})}
 async function register(){await action(async()=>{
  let row=rows.find(x=>x.id===chosen);
  if(!row){
   if(rows.length)throw new Error('choose_profile');
   if(!/^[a-zA-Z0-9][a-zA-Z0-9._:/+-]{0,119}$/.test(model)){setError('Nhập mã mô hình Codex hợp lệ trước khi tạo hồ sơ.');return}
   if(!window.confirm(`Tạo hồ sơ Codex riêng trong ${activeWorkspace?.name} với mô hình ${model}? Chưa đăng nhập hoặc cấp quyền.`))return;
   row=cliProfileRows({items:[await request(codexLoginPath(workspace),'POST',{model,request_key:crypto.randomUUID()})],external_calls:false},workspace,actor)[0];setChosen(row.id);setRows([row]);
  }
  await start(row);
 })}
 async function cancel(){return action(async()=>{
  const value=current.current;if(!value?.operation_id)return;
  const result=await request(codexLoginPath(workspace,value.connection_id,'login/cancel'),'POST',{version:value.version,operation_id:value.operation_id});
  if(result?.cleanup_verified!==true||result?.connection_id!==value.connection_id)throw new Error('cleanup_unknown');
  setState(null);await profiles();
 })}
 async function close(){
  if(busy)return;
  if(current.current?.operation_id&&['starting','awaiting_user','interrupted','cleanup_required','another_session'].includes(current.current.status)){
   if(!window.confirm('Hủy phiên đăng nhập Codex này trước khi đóng? Không đăng xuất Codex của ứng dụng khác.'))return;
   if(!await cancel())return;
  }
  setState(null);setOpen(false);
 }
 const pending=Boolean(state&&['starting','awaiting_user'].includes(state.status)),connection=state?.connection_id||'';
 useEffect(()=>{
  if(!open||!pending||!connection)return;
  const ticket=epoch.current;let reading=false;
  const tick=async()=>{if(reading||lock.current||document.hidden)return;reading=true;const flow=revision.current;try{const value=codexLoginView(await request(codexLoginPath(workspace,connection,'login')),connection);if(ticket===epoch.current&&flow===revision.current){if(value.status==='connected')await action(()=>connectChat(value));else setState(value)}}catch{if(ticket===epoch.current&&flow===revision.current){setState(old=>old?{...old,user_code:null,verification_url:null}:old);setError('Chưa đọc được phiên đăng nhập. Không suy ra đã kết nối; bấm Đọc lại để đối chiếu.')}}finally{reading=false}};
  const timer=setInterval(()=>void tick(),2000);return()=>clearInterval(timer);
 },[open,pending,connection,workspace,request]);
 return <>
  <button ref={button} type="button" aria-label="Kết nối Codex" disabled={!enabled||busy} onClick={()=>void connect()}><Plug size={15}/>Kết nối</button>
  <small>{enabled?'Kết nối để dùng trong PAO AI · gửi chat sẽ sử dụng hạn mức Codex của bạn.':'Chưa bật đăng nhập Codex trên máy chủ này.'}</small>
  {open&&<dialog ref={dialog} className="cx-login" aria-labelledby="cx-login-title" onCancel={e=>{e.preventDefault();void close()}}>
   <header><div><h2 id="cx-login-title">Kết nối Codex</h2><p>{activeWorkspace?.name} · Tài khoản PAO hiện tại</p></div><button type="button" aria-label="Đóng đăng nhập Codex" disabled={busy} onClick={()=>void close()}><X size={18}/></button></header>
   <p>Không nhập lại mật khẩu PAO. Bạn sẽ xác nhận tài khoản tại OpenAI; không gửi mã hoặc token qua chat.</p>
   {error&&<p role="alert">{error}</p>}
   {busy&&<p role="status">Đang xử lý…</p>}
   {state?<section className="cx-status" aria-label="Phiên đăng nhập Codex">
    <strong role="status">{codexLoginLabels[state.status]}</strong>
    {state.status==='connected'&&<><button type="button" disabled={busy} onClick={()=>void action(async()=>{
      const ticket=epoch.current;
      const value=codexModels(await request(codexModelPath(workspace,state.connection_id,'models'),'POST',{version:state.version}),workspace,actor,state.connection_id);
      if(ticket!==epoch.current)return;
      setCatalog(value.models.map(row=>row.model));window.dispatchEvent(new Event('pao:ai-resources'));
    })}>Đọc danh mục model</button>{catalog.length>0&&<details><summary>{catalog.length} model từ Codex — chưa xác minh hạn mức</summary><ul>{catalog.map(value=><li key={value}>{value}</li>)}</ul><p>Đọc danh mục không đổi model của hồ sơ hoặc tác vụ cũ. Tài nguyên dùng chung chỉ được bật sau khi adapter đạt các điều kiện tài khoản và thực thi.</p></details>}</>}
    {state.status==='awaiting_user'&&state.user_code&&<><label>Mã xác nhận một lần<output aria-label="Mã xác nhận Codex">{state.user_code}</output></label><a href={state.verification_url!} target="_blank" rel="noopener noreferrer"><ExternalLink size={16}/>Mở trang đăng nhập OpenAI</a><p>Mở trang trên, đăng nhập tài khoản của bạn và nhập mã. PAO tự cập nhật kết quả. Phiên còn tối đa {state.expires_in} giây.</p></>}
    {state.status==='connected'&&<><p role="status">{chatReady?'Đã kết nối để chọn trong PAO AI. Chưa chạy suy luận hoặc kiểm tra hạn mức. Mô hình mặc định của bạn được giữ nguyên.':'Đã đăng nhập Codex. Bấm Kết nối lại nếu PAO AI chưa dùng được hồ sơ mới.'}</p>{!chatReady&&<button type="button" disabled={busy} onClick={()=>void action(()=>connectChat(state))}>Kết nối vào PAO AI</button>}<p>Không cần chọn nhân sự hoặc cấp quyền AI riêng. Kết nối local này chỉ dùng tài khoản của bạn; chưa chia thuê bao cho người khác.</p><button type="button" disabled={busy} onClick={()=>{if(window.confirm('Ngắt kết nối Codex trong PAO? Không đăng xuất Codex của ứng dụng khác.'))void action(async()=>{const result=await request(codexLoginPath(workspace,state.connection_id,'disconnect'),'POST',{version:state.version});cliProfileRows({items:[result],external_calls:false},workspace,actor);setState(null);setChatReady(false);window.dispatchEvent(new Event('pao:ai-resources'));await profiles()})}}>Ngắt kết nối PAO</button></>}
    {state.operation_id&&['starting','awaiting_user','interrupted','cleanup_required','another_session'].includes(state.status)&&<button type="button" disabled={busy} onClick={()=>{if(window.confirm('Hủy/phục hồi phiên đăng nhập này? Không xóa profile hoặc đăng xuất ứng dụng khác.'))void cancel()}}>Hủy / phục hồi phiên</button>}
   </section>:<>
    {rows.length>1&&<label>Hồ sơ Codex<select aria-label="Hồ sơ Codex" value={chosen} onChange={e=>setChosen(e.target.value)}><option value="">Chọn hồ sơ của bạn</option>{rows.map(row=><option key={row.id} value={row.id}>{row.model} · phiên bản {row.version}</option>)}</select></label>}
    {!rows.length&&<label>Mã mô hình Codex<input aria-label="Mã mô hình Codex" value={model} maxLength={120} autoComplete="off" onChange={e=>setModel(e.target.value)}/><small>Nhập mã model bạn được phép dùng. Lưu mã chưa xác nhận quyền truy cập; không tự chọn model mới hoặc fallback API.</small></label>}
    <button type="button" disabled={busy||rows.length>1&&!chosen} onClick={()=>void register()}>Đăng nhập Codex</button>
   </>}
   <details><summary>Chuẩn bị và xử lý lỗi đăng nhập</summary><p>Máy chủ PAO cần Docker và runtime Codex đã được quản trị viên cài đặt. Trong cài đặt bảo mật ChatGPT, bật đăng nhập bằng mã thiết bị; tài khoản tổ chức có thể cần quản trị viên cấp quyền.</p><p>Codex trên Windows và hồ sơ PAO trong Docker là hai phạm vi riêng. Kết nối này dành cho local cá nhân, chưa được nghiệm thu SaaS/hosted. Quota, quyền model và quyền công cụ không được cấp tự động.</p><p>Nếu bị gián đoạn, bấm Đọc lại rồi Hủy / phục hồi phiên; không tạo hàng loạt hồ sơ mới. Ngắt PAO không đăng xuất ứng dụng Codex khác; thu hồi quyền đăng nhập tại OpenAI riêng.</p><a href="https://learn.chatgpt.com/docs/auth" target="_blank" rel="noopener noreferrer">Hướng dẫn đăng nhập OpenAI</a></details>
   <footer><button type="button" disabled={busy} onClick={()=>void action(async()=>{const list=await profiles();const row=list.find(x=>x.id===(state?.connection_id||chosen))||list[0];if(row){setChosen(row.id);await observe(row.id)}})}>Đọc lại</button><button type="button" disabled={busy} onClick={()=>void close()}>Đóng</button></footer>
  </dialog>}
 </>;
}
