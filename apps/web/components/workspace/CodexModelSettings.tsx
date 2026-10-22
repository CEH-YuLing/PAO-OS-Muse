'use client';
import {useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {cliProfilesPath,cliProfileRows} from '@/lib/model-provider-tabs.mjs';
import {codexModelPath,codexModels,type CodexModels} from '@/lib/codex-model-choice.mjs';
export default function CodexModelSettings({connection}:{connection:string}){
 const {activeWorkspace,me,apiRaw}=usePao(),wid=activeWorkspace?.id||'',uid=me?.id||'';
 const [value,setValue]=useState<CodexModels|null>(null),[model,setModel]=useState(''),[busy,setBusy]=useState(false),[ack,setAck]=useState(false),[uncertain,setUncertain]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const generation=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null);
 useEffect(()=>()=>{generation.current++;abort.current?.abort()},[]);
 async function act(save=false){
  if(lock.current||!connection||save&&(!value||!ack||uncertain))return;
  const ticket=++generation.current,controller=new AbortController();abort.current=controller;lock.current=true;setBusy(true);setError('');setNotice('');
  const request=async(path:string,method='GET',body?:unknown)=>{const response=await apiRaw(path,{method,signal:AbortSignal.any([controller.signal,AbortSignal.timeout(60000)]),...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});return response.json()};
  try{
   let version=value?.version;
   if(!save){const rows=cliProfileRows(await request(cliProfilesPath(wid)),wid,uid);const selected=rows.find(row=>row.id===connection&&row.authentication_ready&&!row.profile_operation_pending);if(!selected)throw Error('source');version=selected.version;}
   const raw=await request(codexModelPath(wid,connection,save?'model':'models'),'POST',{version,...(save?{model,confirm_model_change:ack}:{})});
   if(ticket!==generation.current||controller.signal.aborted)return;
   const next=codexModels(raw,wid,uid,connection);setValue(next);setModel(next.current_model);setAck(false);setUncertain(false);
   if(save){setNotice('Đã đổi model. Lưu lại thiết lập Codex cá nhân bên dưới rồi mở hội thoại mới. Job và hội thoại cũ không tự đổi.');window.dispatchEvent(new Event('pao:codex-profile'));}
   else setNotice('Đã đọc danh mục từ Client. Chưa gọi model; danh mục không bảo đảm quota hoặc kết quả suy luận.');
  }catch{if(ticket===generation.current&&!controller.signal.aborted){setUncertain(true);setError('Chưa xác nhận được thao tác model. Đọc lại danh mục trước khi tiếp tục; không tự gửi lại.');}}
  finally{if(ticket===generation.current){lock.current=false;setBusy(false)}}
 }
 return <section aria-label="Model Codex của tôi"><h4>Chọn model từ Codex</h4>
  <p>Đọc danh mục bằng hồ sơ của bạn trong {activeWorkspace?.name}. Không nhập token, không đổi tài khoản và không gọi suy luận khi đọc hoặc lưu. Chỉ chủ sở hữu/quản trị viên cấu hình hồ sơ của chính mình.</p>
  <button type="button" disabled={!connection||busy} onClick={()=>void act()}>{busy?'Đang xử lý…':'Đọc danh mục model từ Codex'}</button>
  {value&&<fieldset disabled={busy||uncertain}><legend>Model của hồ sơ đã chọn</legend><p>Đang lưu: {value.current_model}{!value.models.some(row=>row.model===value.current_model)?' · Không có trong danh mục vừa đọc':''}</p>
   <label>Model Codex<select aria-label="Model Codex từ Client" value={model} onChange={e=>{setModel(e.target.value);setAck(false)}}><option value="">Chọn model…</option>{value.models.map(row=><option value={row.model} key={row.model}>{row.model}{row.is_default?' · Mặc định Client':''}</option>)}</select></label>
   <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>Tôi xác nhận đổi model; thiết lập và công việc đã ghim cần được chọn, duyệt lại, không tự chuyển.</label>
   <button type="button" disabled={!ack||!value.models.some(row=>row.model===model)||model===value.current_model} onClick={()=>void act(true)}>Lưu model Codex</button>
  </fieldset>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <details><summary>Hướng dẫn và xử lý lỗi model</summary><p>Nếu HTTP400 hoặc model không được hỗ trợ, đọc lại danh mục rồi chọn đúng mã Client liệt kê. Lưu sẽ kiểm tra lại danh mục, tăng phiên bản hồ sơ và làm pin cũ hết hiệu lực. Tiếp theo xác nhận và Lưu thiết lập Codex cá nhân; chỉ chat mới nhận mặc định mới. Không tự sửa lịch sử, retry hoặc fallback trả phí. Khi chưa xác nhận được Lưu, đọc lại trước. Ngắt hồ sơ tại Kết nối Codex để dừng sử dụng; không xóa đăng nhập của ứng dụng khác.</p></details>
 </section>;
}
