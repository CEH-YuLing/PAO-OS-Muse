'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {usePao} from '@/lib/PaoRuntimeContext';
import {legacyPreview,legacyMapping,legacyRequest,legacyReason,legacyError,type LegacyPreview,type LegacyMapping} from '@/lib/telegram-legacy-mapping.mjs';
import './telegram-legacy-mapping.css';

export default function TelegramLegacyMappingPanel(){
 const {apiRaw,activeWorkspace:member}=usePao(),workspace=member?.id||'',owner=member?.role==='owner';
 const epoch=useRef(0),locked=useRef(false),abort=useRef<AbortController|null>(null);
 const [preview,setPreview]=useState<LegacyPreview|null>(null),[mapping,setMapping]=useState<LegacyMapping|null>(null),[known,setKnown]=useState(false),[busy,setBusy]=useState(false);
 const [dataAck,setDataAck]=useState(false),[historyAck,setHistoryAck]=useState(false),[revokeAck,setRevokeAck]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const clear=useCallback(()=>{setDataAck(false);setHistoryAck(false);setRevokeAck(false)},[]);
 const refresh=useCallback(async()=>{
  if(!owner||!workspace||locked.current)return;locked.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setBusy(true);setKnown(false);setPreview(null);setMapping(null);setError('');setNotice('');
  try{
   const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(15000)]),base='/v1/telegram/legacy/'+workspace;
   const stored=legacyMapping(await (await apiRaw(base+'/mapping',{signal})).json(),workspace);
   const proposed=stored?null:legacyPreview(await (await apiRaw(base+'/preview',{signal})).json(),workspace);
   if(ticket===epoch.current&&!controller.signal.aborted){setMapping(stored);setPreview(proposed);setKnown(true)}
  }catch{if(ticket===epoch.current)setError(legacyError())}
  finally{if(ticket===epoch.current){locked.current=false;setBusy(false)}}
 },[owner,workspace,apiRaw,clear]);
 useEffect(()=>{const currentEpoch=epoch,currentAbort=abort,currentLock=locked;void refresh();return()=>{currentEpoch.current++;currentAbort.current?.abort();currentLock.current=false}},[refresh]);
 useEffect(()=>{const hide=()=>{if(document.hidden)clear()};document.addEventListener('visibilitychange',hide);window.addEventListener('pagehide',clear);return()=>{document.removeEventListener('visibilitychange',hide);window.removeEventListener('pagehide',clear)}},[clear]);
 async function write(action:'apply'|'revoke'){
  if(!owner||!known||locked.current||(action==='apply'?(!preview?.eligible||!dataAck||!historyAck):(!mapping||mapping.status!=='staged'||!revokeAck)))return;
  const request=legacyRequest(workspace,action,action==='apply'?preview!:mapping!,crypto.randomUUID());
  locked.current=true;const ticket=++epoch.current,controller=new AbortController();abort.current=controller;
  clear();setBusy(true);setKnown(false);setPreview(null);setMapping(null);setError('');setNotice('');
  try{
   const {path,...init}=request,result=legacyMapping(await (await apiRaw(path,{...init,signal:AbortSignal.any([controller.signal,AbortSignal.timeout(30000)])})).json(),workspace);
   if(!result||result.status!==(action==='apply'?'staged':'revoked'))throw new Error('telegram_mapping_response_invalid');
   if(ticket===epoch.current&&!controller.signal.aborted){setMapping(result);setKnown(true);setNotice(action==='apply'?'Đã tạo kết nối đang tắt. Chưa gọi Telegram, chưa nhập token, chưa gửi tin.':'Đã thu hồi kết nối. Bot dùng chung vẫn bị chặn; không phát lại tin cũ.')}
  }catch{if(ticket===epoch.current)setError(legacyError())}
  finally{if(ticket===epoch.current){locked.current=false;setBusy(false)}}
 }
 return <section className="tg-legacy" aria-label="Chuyển đổi Telegram cũ">
  <h2>Chuyển Telegram cũ · {member?.name}</h2>
  <p>Chỉ chủ doanh nghiệp xác nhận chuyển bot dùng chung sang một doanh nghiệp. Đây là bước lưu dữ liệu, không bật bot hay gọi Telegram.</p>
  <p role="note">Sau khi chuyển, transport bot dùng chung bị chặn vĩnh viễn, kể cả khi thu hồi. Tạo peer/binding mới đang tắt; không sao chép token, kho tri thức, hội thoại, lịch sử hay hàng đợi. Tin đang chờ và tin không rõ đã gửi được giữ nguyên, không tự phát lại.</p>
  {!owner?<p>Bạn không phải chủ doanh nghiệp của doanh nghiệp này; không đọc dữ liệu chuyển đổi hoặc thực hiện thao tác.</p>:<>
   <button type="button" disabled={busy} onClick={()=>void refresh()}>Đọc lại chuyển đổi Telegram</button>
   {busy&&<p role="status">Đang đối chiếu chuyển đổi Telegram…</p>}{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
   {!known&&!busy&&<p>Chưa có trạng thái xác nhận; thao tác bị khóa.</p>}
   {known&&preview&&<><p>{legacyReason(preview.reason)}</p>{preview.eligible&&<>
    <p>{preview.peer_count} peer · {preview.binding_count} binding · {preview.held_delivery_count} lượt gửi cũ giữ nguyên</p>
    <ul aria-label="Peer Telegram cũ">{preview.peers.map(peer=><li key={peer.source_peer_id}>Telegram ID / private chat: {peer.telegram_user_id} · {peer.bound?'có binding':'chưa có binding'}</li>)}</ul>
    <fieldset disabled={busy}><legend>Xác nhận chuyển sang {member?.name}</legend>
     <label><input type="checkbox" aria-label="Chỉ chuyển dữ liệu đang tắt" checked={dataAck} onChange={e=>setDataAck(e.target.checked)}/>Tôi xác nhận doanh nghiệp này sở hữu toàn bộ peer trên; chỉ tạo kết nối đang tắt, chưa cấp quyền gửi.</label>
     <label><input type="checkbox" aria-label="Không phát lại lịch sử Telegram" checked={historyAck} onChange={e=>setHistoryAck(e.target.checked)}/>Tôi hiểu bot dùng chung bị chặn vĩnh viễn; không chuyển kho tri thức/hội thoại/token hoặc phát lại hàng đợi cũ.</label>
     <button type="button" disabled={!dataAck||!historyAck} onClick={()=>void write('apply')}>Xác nhận chuyển Telegram cũ</button>
    </fieldset></> }</>}
   {known&&mapping&&<><p>Kết nối: {mapping.status==='staged'?'ĐANG TẮT':'ĐÃ THU HỒI'} · phiên bản {mapping.version} · {mapping.peer_count} peer mới · không có token</p>
    {mapping.status==='staged'&&<fieldset disabled={busy}><legend>Thu hồi bản lưu</legend><label><input type="checkbox" aria-label="Thu hồi không bật lại bot cũ" checked={revokeAck} onChange={e=>setRevokeAck(e.target.checked)}/>Tôi hiểu thu hồi không bật lại bot dùng chung, không tự thu hồi token tại Telegram và không phát lại tin cũ.</label><button type="button" disabled={!revokeAck} onClick={()=>void write('revoke')}>Thu hồi chuyển đổi Telegram</button></fieldset>}
   </>}
   <p>Không nhập token ở bước này. BotFather/getMe, đích nhận tin và bật kết nối được triển khai ở S3.2–S3.3. <a href="https://core.telegram.org/bots/features#botfather" target="_blank" rel="noopener noreferrer">Hướng dẫn Telegram chính thức</a></p>
  </>}
 </section>;
}
