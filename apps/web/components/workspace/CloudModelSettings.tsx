"use client";
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {KeyRound,Trash2,Save} from 'lucide-react';
import {modelHelp,providerRows,cleanModelKey,modelIds,modelRequest,modelSettingsError,modelKeyState,modelSaveConsent,type CloudProvider,type CloudRecord,type ModelAction} from '@/lib/cloud-model-settings.mjs';
import ConnectionEvidence from './ConnectionEvidence';
import './cloud-model-settings.css';

export default function CloudModelSettings({onDraftChange}:{onDraftChange?:(dirty:boolean)=>void}){
 const {apiRaw,activeWorkspace:member}=usePao(),workspace=member?.id||'',manage=member?.role==='owner'||member?.role==='admin';
 const epoch=useRef(0),lock=useRef(false),abort=useRef<AbortController|null>(null);
 const [rows,setRows]=useState<CloudRecord[]>([]),[confirmed,setConfirmed]=useState(false),[busy,setBusy]=useState(false);
 const [keys,setKeys]=useState<Partial<Record<CloudProvider,string>>>({}),[catalogues,setCatalogues]=useState<Partial<Record<CloudProvider,string[]>>>({}),[models,setModels]=useState<Partial<Record<CloudProvider,string>>>({});
 const [metadataAck,setMetadataAck]=useState<Partial<Record<CloudProvider,boolean>>>({}),[probeAck,setProbeAck]=useState<Partial<Record<CloudProvider,boolean>>>({});
 const [error,setError]=useState(''),[notice,setNotice]=useState('');
 const draft=Object.values(keys).some(Boolean)||rows.some(row=>Boolean(models[row.provider])&&models[row.provider]!==row.model);
 useEffect(()=>{onDraftChange?.(draft)},[draft,onDraftChange]);
 useEffect(()=>()=>onDraftChange?.(false),[onDraftChange]);
 const clear=useCallback(()=>{setKeys({});setCatalogues({});setModels({});setMetadataAck({});setProbeAck({})},[]);
 const read=useCallback(async(ticket:number,controller:AbortController)=>{
  const response=await apiRaw(`/v1/model-providers?workspace_id=${workspace}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
  const result=providerRows(await response.json());if(ticket!==epoch.current||controller.signal.aborted)return false;
  setRows(result);setConfirmed(true);return true;
 },[apiRaw,workspace]);
 const refresh=useCallback(async()=>{
  if(lock.current||!workspace)return;lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setBusy(true);setConfirmed(false);setRows([]);setError('');setNotice('');
  try{await read(ticket,controller)}catch(reason){if(ticket===epoch.current)setError(modelSettingsError((reason as Error).message))}
  finally{if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 },[workspace,clear,read]);
 useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=lock;void refresh();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false}},[refresh]);
 useEffect(()=>{const hide=()=>{if(document.hidden){setKeys({});setMetadataAck({});setProbeAck({})}};const leave=()=>{setKeys({});setMetadataAck({});setProbeAck({})};document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',leave);return()=>{document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',leave)}},[]);
 async function work(row:CloudRecord,action:ModelAction){
  if(lock.current||!confirmed||!manage)return;
  if(['catalogue','select','default'].includes(action)&&!metadataAck[row.provider])return;
  if(action==='probe'&&!probeAck[row.provider])return;
  if(action==='disconnect'&&!window.confirm(`Xóa khóa ${row.name} đã lưu trong ${member?.name}? PAO sẽ ngắt bản lưu này; công việc đang dùng kết nối có thể bị chặn. Khóa tại nhà cung cấp không tự bị thu hồi.`))return;
  const chosen=models[row.provider]||row.model;let secret='';
  try{if(action==='connect')secret=cleanModelKey(keys[row.provider]||'')}catch(reason){clear();setError(modelSettingsError((reason as Error).message));return}
  if(action==='connect'&&!window.confirm(modelSaveConsent(row.name,member?.name||'doanh nghiệp đang chọn')))return;
  if(action==='select'&&(!chosen||!catalogues[row.provider]?.includes(chosen)))return;
  lock.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  const body=action==='connect'?{api_key:secret}:action==='select'?{model:chosen}:undefined;
  const request=modelRequest(row.provider,action,workspace,body,['connect','catalogue','select'].includes(action)?crypto.randomUUID():undefined);
  // Preserve other providers' drafts in this SME; discard this operation's key.
  setKeys(old=>{const next={...old};delete next[row.provider];return next});setCatalogues({});setModels({});setMetadataAck({});setProbeAck({});setBusy(true);setError('');setNotice('');
  try{
   const {path,...init}=request;const response=await apiRaw(path,{...init,signal:AbortSignal.any([controller.signal,AbortSignal.timeout(action==='probe'?210000:60000)])});
   let ids:string[]|undefined;
   if(response.status!==204){const result=await response.json();
    if(action==='connect'){providerRows([result]);ids=modelIds(result.models,secret);if(result.provider!==row.provider||!ids.includes(result.model))throw new Error('model_response_invalid')}
    if(action==='select'){providerRows([result]);if(result.provider!==row.provider||result.model!==chosen)throw new Error('model_response_invalid')}
    if(action==='catalogue'){ids=modelIds(result.models);if(result.provider!==row.provider)throw new Error('model_response_invalid')}
    if(action==='default'){providerRows([result]);if(result.provider!==row.provider||!result.is_default)throw new Error('model_response_invalid')}
    if(action==='probe'&&(result.ok!==true||result.provider!==row.provider||result.model!==row.model))throw new Error('model_response_invalid');
   }
   if(ticket!==epoch.current||controller.signal.aborted)return;
   if(!await read(ticket,controller))return;
   if(ids)setCatalogues({[row.provider]:ids});
   window.dispatchEvent(new Event('pao:ai-resources'));
   setNotice(action==='probe'?'Lượt suy luận AI vừa phản hồi; chưa chứng minh hoạt động ổn định lâu dài hoặc nghiệm thu vận hành thật.':action==='disconnect'?`Đã xóa khóa ${row.name} khỏi bản lưu PAO. Thu hồi khóa tại nhà cung cấp riêng; quyền và việc cũ không tự sống lại.`:action==='connect'?`Đã lưu cấu hình ${row.name} và đọc lại trạng thái. Chưa xác minh suy luận AI hoặc cấp quyền công cụ.`:'Đã xác nhận trạng thái mới. Danh mục không chứng minh suy luận AI hoặc quyền công cụ.');
  }catch(reason){if(ticket===epoch.current){clear();setRows([]);setConfirmed(false);setError(modelSettingsError((reason as Error).message))}}
  finally{secret='';if(ticket===epoch.current){lock.current=false;setBusy(false)}}
 }
 return <section className="cm-settings" aria-label="Cài đặt mô hình đám mây">
  <header className="cm-heading"><div><h2>Kết nối qua API</h2><p>Cấu hình riêng cho {member?.name}. Mỗi ô là một nhà cung cấp; API tính phí riêng với gói Client.</p></div><button type="button" disabled={busy} onClick={()=>{if(Object.values(keys).some(Boolean)&&!window.confirm('Đọc lại sẽ bỏ các khóa API chưa lưu. Tiếp tục?'))return;void refresh()}}>Đọc lại trạng thái mô hình</button></header>
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {!confirmed&&<p>Chưa có trạng thái xác nhận; thao tác bị khóa. Đọc lại không gọi nhà cung cấp và sẽ bỏ khóa/bản nháp. Nếu yêu cầu trước chưa kết thúc, một lần đọc GET chưa chắc xác định kết quả cuối; chờ rồi đối chiếu, không tự gửi lại.</p>}
  <div className="cm-grid">{rows.map(row=><article key={row.provider} aria-label={`mô hình ${row.provider}`}>
   <header className="cm-card-heading"><KeyRound size={19}/><h3>{row.provider==='anthropic'?'Claude (Anthropic)':row.name}</h3><span className="cm-key-status" data-saved={row.configured}>{modelKeyState(row,keys[row.provider]).label}</span></header>
   {row.is_default&&<small>Mặc định doanh nghiệp</small>}
   {manage?<fieldset disabled={busy||!confirmed}>
    <legend className="cm-visually-hidden">Quản lý {row.name} cho doanh nghiệp này</legend>
    <label>Khóa API<input aria-label={`Khóa API ${row.name}`} type="password" autoComplete="new-password" spellCheck={false} maxLength={4096} placeholder={row.configured?modelKeyState(row).masked+' · nhập khóa mới để thay':'Nhập khóa API của '+row.name} value={keys[row.provider]||''} onChange={event=>{setKeys(old=>({...old,[row.provider]:event.target.value}));setMetadataAck(old=>({...old,[row.provider]:false}))}}/></label>
    <div className="cm-card-actions"><button className="cm-save" type="button" disabled={!(keys[row.provider]||'').trim()} onClick={()=>void work(row,'connect')}><Save size={15}/>Lưu cấu hình</button><button className="cm-remove" type="button" disabled={!row.configured} onClick={()=>void work(row,'disconnect')}><Trash2 size={15}/>Xóa khóa</button></div>
    {row.configured&&<small className="cm-saved-hint" aria-label={'Khóa đã lưu '+row.name}>{modelKeyState(row).masked} · Khóa đã lưu được che, không tải lại khóa gốc.</small>}
    {!!keys[row.provider]&&<button type="button" className="cm-clear-draft" onClick={()=>setKeys(old=>({...old,[row.provider]:''}))}>Bỏ khóa chưa lưu</button>}
    {row.configured&&<details className="cm-advanced"><summary>Mô hình và tùy chọn nâng cao</summary>
     <p>Mô hình đã lưu: {row.model||'Chưa chọn'}. Các thao tác dưới đây độc lập với lưu khóa.</p>
     <label><input aria-label={`Đồng ý thông tin mô tả ${row.name}`} type="checkbox" checked={Boolean(metadataAck[row.provider])} onChange={event=>setMetadataAck(old=>({...old,[row.provider]:event.target.checked}))}/>Cho phép thao tác mô hình/danh mục cho doanh nghiệp này; có thể gọi nhà cung cấp, chưa chạy suy luận AI.</label>
     <button type="button" disabled={!metadataAck[row.provider]} onClick={()=>void work(row,'catalogue')}>Tải danh mục mô hình</button>
     <label>mô hình {row.name}<select aria-label={`Mô hình lựa chọn ${row.name}`} value={models[row.provider]||row.model||''} onChange={event=>{setModels(old=>({...old,[row.provider]:event.target.value}));setMetadataAck(old=>({...old,[row.provider]:false}));setProbeAck(old=>({...old,[row.provider]:false}))}}><option value={row.model||''}>{row.model||'Chọn mô hình'}</option>{(catalogues[row.provider]||[]).filter(id=>id!==row.model).map(id=><option key={id} value={id}>{id}</option>)}</select></label>
     <button type="button" disabled={!metadataAck[row.provider]||!catalogues[row.provider]?.includes(models[row.provider]||'')||models[row.provider]===row.model} onClick={()=>void work(row,'select')}>Lưu mô hình đã chọn</button>
     {!row.is_default&&<button type="button" disabled={!metadataAck[row.provider]} onClick={()=>void work(row,'default')}>Đặt mặc định doanh nghiệp</button>}
     <label><input aria-label={`Đồng ý suy luận AI ${row.name}`} type="checkbox" checked={Boolean(probeAck[row.provider])} onChange={event=>setProbeAck(old=>({...old,[row.provider]:event.target.checked}))}/>Tôi cho phép một lượt kiểm tra suy luận AI dùng token, có thể tính phí. Nguồn đã đăng ký quyền vẫn phải chạy qua tác vụ đúng quyền; kiểm tra này không bỏ qua chúng.</label>
     <button type="button" disabled={!probeAck[row.provider]} onClick={()=>void work(row,'probe')}>Kiểm tra suy luận AI có phí</button>
    </details>}
   </fieldset>:<p>Chỉ chủ doanh nghiệp/quản trị viên được cấu hình, tải danh mục và kiểm tra. Dùng mô hình theo quyền được cấp riêng.</p>}
   <details><summary>Hướng dẫn {row.name}</summary><p>{modelHelp[row.provider].text}</p><a href={modelHelp[row.provider].url} target="_blank" rel="noopener noreferrer">Mở tài liệu chính thức</a><p>Chỉ chủ doanh nghiệp/quản trị viên được quản lý khóa tại SME đang chọn. Lưu sẽ gọi danh mục, không tự kiểm tra suy luận AI. Khi lỗi, đọc lại trạng thái trước khi thử ý định mới. Đổi/thu hồi khóa ở nhà cung cấp; nút Xóa khóa chỉ xóa bản lưu PAO và ngắt kết nối này.</p><p>Khóa đã lưu không chứng minh quota hay khả năng chạy model. Không cần App ID, redirect hoặc webhook ở màn hình API key này.</p></details>
   <details><summary>Trạng thái và bằng chứng</summary><ConnectionEvidence kind={row.provider} record={row}/><p>Thời điểm kiểm tra đã lưu: {row.last_checked_at?new Date(row.last_checked_at).toLocaleString('vi-VN'):'Chưa có'}. Thời điểm này không chứng minh đã chạy suy luận AI.</p></details>
  </article>)}</div>
  <p className="cm-footnote">Khóa đã nhập chưa được lưu cho đến khi máy chủ xác nhận. Không lưu khóa vào trình duyệt; khóa nháp được bỏ khi ẩn tab, rời trang, đổi doanh nghiệp hoặc có lỗi. Không tự bật API dự phòng, suy luận AI hoặc quyền công cụ.</p>
 </section>;
}
